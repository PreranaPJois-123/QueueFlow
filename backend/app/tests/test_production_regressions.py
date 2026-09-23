from datetime import datetime, timedelta, timezone

import pytest
from starlette.websockets import WebSocketDisconnect

from app.tests.conftest import register_and_login
from app.core.config import Settings
from app.core.redis_client import redis_client
from app.models.models import Ticket, ServiceRecord
from app.services import queue_service


def setup_queue(client):
    staff = register_and_login(client, 'operator@example.com', role='STAFF')
    customer = register_and_login(client, 'visitor@example.com')
    service = client.post('/api/services', headers=staff, json={'name': 'Desk'}).json()
    queue = client.post('/api/queues', headers=staff, json={'name': 'Line', 'service_id': service['id']}).json()
    return staff, customer, service, queue


@pytest.mark.parametrize('role', ['STAFF', 'ADMIN'])
def test_public_registration_cannot_grant_privileges(client, role):
    response = client.post('/api/auth/register', json={
        'email': 'attacker@example.com', 'password': 'testpass123', 'full_name': 'Test', 'role': role})
    assert response.status_code == 403
    assert client.post('/api/auth/login', json={'email': 'attacker@example.com', 'password': 'testpass123'}).status_code == 401


def test_multibyte_password_returns_validation_error(client):
    response = client.post('/api/auth/register', json={
        'email': 'unicode@example.com', 'password': '😀' * 30, 'full_name': 'Test'})
    assert response.status_code == 422


def test_redis_outage_is_unhealthy(client, monkeypatch):
    def unavailable():
        raise ConnectionError('unavailable')
    monkeypatch.setattr(redis_client, 'ping', unavailable)
    response = client.get('/api/health')
    assert response.status_code == 503
    assert response.json()['redis'] == 'down'


def test_database_outage_is_unhealthy(client, monkeypatch):
    from app.core.database import engine
    def unavailable():
        raise ConnectionError('unavailable')
    monkeypatch.setattr(engine, 'connect', unavailable)
    monkeypatch.setattr(redis_client, 'ping', lambda: True)
    response = client.get('/api/health')
    assert response.status_code == 503
    assert response.json()['database'] == 'down'


def test_missing_queue_and_service_return_404(client):
    staff = register_and_login(client, 'operator@example.com', role='STAFF')
    assert client.get('/api/staff/queues/missing/state', headers=staff).status_code == 404
    assert client.get('/api/staff/queues/missing/waiting', headers=staff).status_code == 404
    assert client.post('/api/queues', headers=staff, json={'name':'Line', 'service_id':'missing'}).status_code == 404
    assert client.post('/api/appointments', headers=staff, json={
        'service_id':'missing', 'scheduled_time': (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()}).status_code == 404


def test_appointment_validation_and_cancellation(client):
    staff, customer, service, queue = setup_queue(client)
    base = {'service_id':service['id']}
    for when in [datetime.now(timezone.utc) - timedelta(days=1), datetime.now() + timedelta(days=1)]:
        assert client.post('/api/appointments', headers=customer, json={**base, 'scheduled_time':when.isoformat()}).status_code == 422
    response = client.post('/api/appointments', headers=customer, json={**base, 'scheduled_time':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()})
    assert response.status_code == 201
    path = f"/api/appointments/{response.json()['id']}/cancel"
    assert client.post(path, headers=customer).status_code == 200
    assert client.post(path, headers=customer).status_code == 409


def test_websocket_initial_snapshot_and_actual_updates(client):
    staff, customer, service, queue = setup_queue(client)
    qid = queue['id']
    with client.websocket_connect(f'/api/queues/{qid}/ws', headers={'origin': 'http://localhost:5173'}) as socket:
        assert socket.receive_json()['data']['waiting_count'] == 0
        joined = client.post(f'/api/queues/{qid}/join', headers=customer)
        assert joined.status_code == 201
        ticket_id = joined.json()['ticket']['id']
        assert socket.receive_json()['data']['waiting_labels'] == ['A001']
        assert client.post(f'/api/staff/queues/{qid}/next', headers=staff).status_code == 200
        assert socket.receive_json()['data']['current_serving_label'] == 'A001'
        detail = client.get(f'/api/tickets/{ticket_id}', headers=customer).json()
        assert detail['ticket']['status'] == 'CALLED'
        assert detail['current_serving_label'] == 'A001'
        assert client.post(f'/api/staff/tickets/{ticket_id}/serve', headers=staff).status_code == 200
        assert socket.receive_json()['data']['now_serving_ticket_id'] is None
    with client.websocket_connect(f'/api/queues/{qid}/ws') as socket:
        assert socket.receive_json()['data']['waiting_count'] == 0


def test_websocket_rejects_missing_queue_and_untrusted_origin(client):
    staff, customer, service, queue = setup_queue(client)
    for qid, origin in [('missing', 'http://localhost:5173'), (queue['id'], 'https://evil.example')]:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(f'/api/queues/{qid}/ws', headers={'origin':origin}):
                pass


def test_cors_restricts_browser_origins(client):
    headers = {'origin':'http://localhost:5173', 'access-control-request-method':'POST', 'access-control-request-headers':'authorization,content-type'}
    response = client.options('/api/queues', headers=headers)
    assert response.status_code == 200
    assert response.headers['access-control-allow-origin'] == headers['origin']
    headers['origin'] = 'https://evil.example'
    response = client.options('/api/queues', headers=headers)
    assert response.status_code == 400
    assert 'access-control-allow-origin' not in response.headers


def test_cannot_close_queue_with_active_tickets(client):
    staff, customer, service, queue = setup_queue(client)
    client.post(f"/api/queues/{queue['id']}/join", headers=customer)
    assert client.post(f"/api/staff/queues/{queue['id']}/close", headers=staff).status_code == 409


def test_serving_ticket_blocks_next_and_remains_visible(client, db_session):
    staff, customer, service, queue = setup_queue(client)
    ticket_id = client.post(f"/api/queues/{queue['id']}/join", headers=customer).json()['ticket']['id']
    client.post(f"/api/staff/queues/{queue['id']}/next", headers=staff)
    queue_service.start_serving(db_session, ticket_id)
    assert client.post(f"/api/staff/queues/{queue['id']}/next", headers=staff).status_code == 409
    state = client.get(f"/api/staff/queues/{queue['id']}/state", headers=staff).json()
    assert state['now_serving_ticket_id'] == ticket_id


def test_service_duration_uses_call_time(client, db_session):
    staff, customer, service, queue = setup_queue(client)
    ticket_id = client.post(f"/api/queues/{queue['id']}/join", headers=customer).json()['ticket']['id']
    client.post(f"/api/staff/queues/{queue['id']}/next", headers=staff)
    ticket = db_session.get(Ticket, ticket_id)
    ticket.called_at = datetime.now(timezone.utc) - timedelta(seconds=120)
    db_session.commit()
    assert client.post(f'/api/staff/tickets/{ticket_id}/serve', headers=staff).status_code == 200
    record = db_session.query(ServiceRecord).filter_by(ticket_id=ticket_id).one()
    assert record.service_seconds >= 120


def test_fifo_uses_token_sequence_not_clock(client, db_session):
    staff, customer, service, queue = setup_queue(client)
    first = client.post(f"/api/queues/{queue['id']}/join", headers=customer).json()['ticket']
    second_user = register_and_login(client, 'second@example.com')
    second = client.post(f"/api/queues/{queue['id']}/join", headers=second_user).json()['ticket']
    db_session.get(Ticket, second['id']).created_at = datetime.now(timezone.utc) - timedelta(days=1)
    db_session.commit()
    assert client.post(f"/api/staff/queues/{queue['id']}/next", headers=staff).json()['id'] == first['id']


def test_inactive_service_cannot_be_joined(client):
    staff, customer, service, queue = setup_queue(client)
    client.patch(f"/api/services/{service['id']}", headers=staff, json={'is_active':False})
    assert client.post(f"/api/queues/{queue['id']}/join", headers=customer).status_code == 409


def test_production_rejects_placeholder_secret_and_wildcard():
    valid = dict(ENV='production', DATABASE_URL='postgres://user:password@db/queueflow',
                 REDIS_URL='redis://cache:6379', JWT_SECRET_KEY='x'*40, CORS_ORIGINS='https://app.example.com')
    assert Settings(_env_file=None, **valid).sync_database_url.startswith('postgresql://')
    for key, value in [('JWT_SECRET_KEY','changeme'), ('CORS_ORIGINS','*'), ('DATABASE_URL','sqlite://')]:
        with pytest.raises(ValueError):
            Settings(_env_file=None, **{**valid, key:value})


def test_expired_and_incomplete_jwt_rejected(client):
    from jose import jwt
    from app.core.config import settings
    for payload in [{'sub':'missing'}, {'exp':datetime.now(timezone.utc)+timedelta(minutes=5)},
                    {'sub':'missing', 'exp':datetime.now(timezone.utc)-timedelta(minutes=1)}]:
        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        assert client.get('/api/auth/me', headers={'Authorization':f'Bearer {token}'}).status_code == 401


def test_websocket_multiple_clients_disconnect_and_reconnect(client):
    staff, customer, service, queue = setup_queue(client)
    qid = queue['id']
    path = f'/api/queues/{qid}/ws'
    with client.websocket_connect(path) as first:
        assert first.receive_json()['data']['waiting_count'] == 0
        with client.websocket_connect(path) as second:
            assert second.receive_json()['data']['waiting_count'] == 0
            joined = client.post(f'/api/queues/{qid}/join', headers=customer)
            assert joined.status_code == 201
            ticket_id = joined.json()['ticket']['id']
            for socket in (first, second):
                assert socket.receive_json()['data']['waiting_labels'] == ['A001']
        # Closing one connection must not remove the other subscriber.
        assert client.post(f'/api/staff/queues/{qid}/pause', headers=staff).status_code == 200
        assert first.receive_json()['data']['status'] == 'PAUSED'
        with client.websocket_connect(path) as reconnected:
            snapshot = reconnected.receive_json()['data']
            assert snapshot['status'] == 'PAUSED'
            assert snapshot['waiting_count'] == 1
            assert client.post(f'/api/staff/queues/{qid}/resume', headers=staff).status_code == 200
            for socket in (first, reconnected):
                assert socket.receive_json()['data']['status'] == 'OPEN'
            assert client.post(f'/api/tickets/{ticket_id}/cancel', headers=customer).status_code == 200
            for socket in (first, reconnected):
                assert socket.receive_json()['data']['waiting_count'] == 0
