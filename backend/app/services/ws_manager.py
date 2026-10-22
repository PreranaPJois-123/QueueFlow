"""
In-process WebSocket connection manager, keyed by queue_id.

For a single-instance deployment (what this project ships with) an
in-memory dict is sufficient and simplest to explain. If QueueFlow were
scaled to multiple backend replicas, this would move to a Redis pub/sub
channel so a broadcast on one instance reaches sockets held by another —
the `broadcast_queue_state` call site would not need to change, only this
class's internals.
"""
import json
from typing import Dict, Set

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, queue_id: str, websocket: WebSocket):
        await websocket.accept()
        self._connections.setdefault(queue_id, set()).add(websocket)

    def disconnect(self, queue_id: str, websocket: WebSocket):
        conns = self._connections.get(queue_id)
        if conns and websocket in conns:
            conns.remove(websocket)
        if conns is not None and not conns:
            self._connections.pop(queue_id, None)

    async def broadcast(self, queue_id: str, payload: dict):
        conns = self._connections.get(queue_id, set())
        dead = []
        message = json.dumps(payload)
        for ws in tuple(conns):
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(queue_id, ws)


manager = ConnectionManager()
