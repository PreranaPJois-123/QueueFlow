from datetime import datetime, timedelta, timezone
from app.tests.conftest import register_and_login
from app.models.models import ServiceRecord, Ticket, TicketStatus
from app.services.prediction import predict_duration


def setup(client):
    staff = register_and_login(client, 'staff@example.com', role='STAFF')
    customer = register_and_login(client, 'customer@example.com', full_name='Queue Customer')
    service = client.post('/api/services', headers=staff, json={'name': 'Consultation'}).json()
    queue = client.post('/api/queues', headers=staff, json={'name': 'Main desk', 'service_id': service['id']}).json()
    return staff, customer, service, queue


def test_product_permissions_and_private_information(client):
    staff, customer, service, queue = setup(client)
    joined = client.post(f"/api/queues/{queue['id']}/join", headers=customer).json()
    assert joined['queue_name'] == 'Main desk'
    assert joined['service_name'] == 'Consultation'
    public = client.get('/api/product/queues').json()[0]
    assert public['waiting_count'] == 1
    assert 'customer_name' not in str(public)
    for path in ['/api/product/customers', '/api/product/trends', f"/api/product/queues/{queue['id']}/tickets"]:
        assert client.get(path, headers=customer).status_code == 403
        assert client.get(path).status_code == 401
    rows = client.get('/api/product/customers', headers=staff).json()
    assert rows[0]['full_name'] == 'Queue Customer'
    assert rows[0]['tickets'][0]['queue_name'] == 'Main desk'
    assert 'hashed_password' not in str(rows)
    other = register_and_login(client, 'other@example.com')
    assert client.get('/api/product/mine', headers=other).json()['tickets'] == []


def test_appointment_conflicts_and_availability(client):
    staff, customer, service, queue = setup(client)
    other = register_and_login(client, 'other@example.com')
    when = (datetime.now(timezone.utc)+timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    payload = {'service_id': service['id'], 'scheduled_time': when.isoformat()}
    booking = client.post('/api/appointments', headers=customer, json=payload)
    assert booking.status_code == 201
    assert client.post('/api/appointments', headers=other, json=payload).status_code == 409
    second_service = client.post('/api/services', headers=staff, json={'name': 'Second'}).json()
    assert client.post('/api/appointments', headers=customer, json={**payload,'service_id':second_service['id']}).status_code == 409
    near = {**payload,'scheduled_time':(when+timedelta(minutes=15)).isoformat()}
    assert client.post('/api/appointments', headers=other, json=near).status_code == 409
    available = client.get(f"/api/appointments/availability/{service['id']}?day={when.date()}", headers=other).json()
    assert when.isoformat() not in available['slots']
    assert (when+timedelta(minutes=30)).isoformat() in available['slots']
    assert client.post(f"/api/appointments/{booking.json()['id']}/cancel", headers=customer).status_code == 200
    assert client.post('/api/appointments', headers=other, json=payload).status_code == 201
    client.patch(f"/api/services/{service['id']}", headers=staff, json={'is_active':False})
    assert client.get(f"/api/appointments/availability/{service['id']}?day={when.date()}", headers=other).status_code == 404


def test_profile_validation_and_ownership(client):
    staff, customer, service, queue = setup(client)
    assert client.patch('/api/auth/me', headers=customer, json={'full_name':'  '}).status_code == 422
    result = client.patch('/api/auth/me', headers=customer, json={'full_name':' Updated Name ', 'role':'ADMIN'})
    assert result.status_code == 200
    assert result.json()['full_name'] == 'Updated Name'
    assert result.json()['role'] == 'CUSTOMER'
    assert client.get('/api/auth/me', headers=staff).json()['full_name'] != 'Updated Name'


def test_start_complete_and_notification_isolation(client):
    staff, customer, service, queue = setup(client)
    tid = client.post(f"/api/queues/{queue['id']}/join", headers=customer).json()['ticket']['id']
    start = f'/api/staff/tickets/{tid}/start'
    assert client.post(start, headers=customer).status_code == 403
    assert client.post(start, headers=staff).status_code == 409
    client.post(f"/api/staff/queues/{queue['id']}/next", headers=staff)
    assert client.post(start, headers=staff).json()['status'] == 'SERVING'
    assert client.post(start, headers=staff).status_code == 409
    notification = client.get('/api/product/mine', headers=customer).json()['notifications'][0]
    other = register_and_login(client, 'other@example.com')
    path = f"/api/product/notifications/{notification['id']}/read"
    assert client.post(path, headers=other).status_code == 404
    assert client.post(path, headers=customer).json()['is_read'] is True
    assert client.post(f'/api/staff/tickets/{tid}/serve', headers=staff).json()['status'] == 'SERVED'
    trends = client.get('/api/product/trends', headers=staff).json()
    assert trends['total_tickets'] == trends['total_served'] == 1
    assert trends['completion_rate'] == 100
    assert trends['daily'][-1]['served'] == 1


def test_prediction_learns_only_completed_real_history(client, db_session):
    staff, customer, service, queue = setup(client)
    assert predict_duration(db_session, queue['id'])['source'] == 'calculated_default'
    now = datetime.now(timezone.utc)
    customer_id = client.get("/api/auth/me", headers=customer).json()["id"]
    for i in range(20):
        ticket = Ticket(queue_id=queue['id'], customer_id=customer_id, token_number=i+1, token_label=f'A{i+1:03}', status=TicketStatus.SERVED)
        db_session.add(ticket); db_session.flush()
        db_session.add(ServiceRecord(ticket_id=ticket.id, queue_id=queue['id'], service_id=service['id'], wait_seconds=120, service_seconds=600, outcome=TicketStatus.SERVED, created_at=now-timedelta(days=i)))
    db_session.commit()
    learned = predict_duration(db_session, queue['id'])
    assert learned == {'service_minutes':10.0,'source':'ml_knn','sample_count':20}
    db_session.query(ServiceRecord).delete(); db_session.commit()
    assert predict_duration(db_session, queue['id'])['source'] == 'calculated_default'


def test_heartbeat_snapshot_contains_no_customer_details(client):
    staff, customer, service, queue = setup(client)
    with client.websocket_connect(f"/api/queues/{queue['id']}/ws") as socket:
        socket.receive_json()
        socket.send_text('ping')
        snapshot = socket.receive_json()
        assert snapshot['event'] == 'queue_state'
        assert 'customer' not in str(snapshot)


def test_postgres_concurrent_booking_and_join_are_serialized(client):
    import pytest
    from concurrent.futures import ThreadPoolExecutor
    from app.core.database import engine
    if engine.dialect.name != 'postgresql':
        pytest.skip('Row-lock concurrency requires PostgreSQL; exercised by GitHub CI')
    staff, customer, service, queue = setup(client)
    other = register_and_login(client, 'concurrent@example.com')
    when = (datetime.now(timezone.utc)+timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
    payload = {'service_id':service['id'], 'scheduled_time':when.isoformat()}
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(client.post, '/api/appointments', headers=h, json=payload) for h in (customer,other)]
        assert sorted(f.result().status_code for f in futures) == [201,409]
        futures = [workers.submit(client.post, f"/api/queues/{queue['id']}/join", headers=customer) for _ in range(2)]
        assert sorted(f.result().status_code for f in futures) == [201,409]


def test_blank_names_and_booking_horizon_are_rejected(client):
    staff, customer, service, queue = setup(client)
    assert client.post('/api/services', headers=staff, json={'name':'  '}).status_code == 422
    assert client.post('/api/queues', headers=staff, json={'name':'  ', 'service_id':service['id']}).status_code == 422
    response = client.post('/api/appointments', headers=customer, json={'service_id':service['id'], 'scheduled_time':(datetime.now(timezone.utc)+timedelta(days=91)).isoformat()})
    assert response.status_code == 422
