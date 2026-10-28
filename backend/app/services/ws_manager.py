"""Walk-in queue board sockets, routed through the shared realtime hub so a
broadcast on one backend instance reaches sockets held by any instance."""
from fastapi import WebSocket
from starlette.concurrency import run_in_threadpool

from app.services import realtime


class ConnectionManager:
    async def connect(self, queue_id: str, websocket: WebSocket):
        await websocket.accept()
        realtime.hub.add(f"queue:{queue_id}", websocket)

    def disconnect(self, queue_id: str, websocket: WebSocket):
        realtime.hub.remove(f"queue:{queue_id}", websocket)

    async def broadcast(self, queue_id: str, payload: dict):
        await run_in_threadpool(realtime.publish, f"queue:{queue_id}", payload)


manager = ConnectionManager()
