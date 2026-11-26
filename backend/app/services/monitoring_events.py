import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from uuid import UUID

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

logger = logging.getLogger(__name__)


class MonitoringEventHub:
    def __init__(self) -> None:
        self._connections: dict[UUID, set[WebSocket]] = defaultdict(set)
        self._loop: asyncio.AbstractEventLoop | None = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def connect(self, project_id: UUID, websocket: WebSocket) -> None:
        self._connections[project_id].add(websocket)

    def disconnect(self, project_id: UUID, websocket: WebSocket) -> None:
        connections = self._connections.get(project_id)
        if connections is None:
            return
        connections.discard(websocket)
        if not connections:
            self._connections.pop(project_id, None)

    async def broadcast(self, project_id: UUID, event: dict) -> None:
        for websocket in tuple(self._connections.get(project_id, ())):
            try:
                await websocket.send_json(event)
            except WebSocketDisconnect:
                self.disconnect(project_id, websocket)
            except RuntimeError:
                logger.exception("Could not deliver monitoring event to a WebSocket client.")
                self.disconnect(project_id, websocket)

    def publish_from_worker(self, project_id: UUID, event: dict) -> None:
        loop = self._loop
        if loop is None or loop.is_closed():
            return
        try:
            future = asyncio.run_coroutine_threadsafe(self.broadcast(project_id, event), loop)
        except RuntimeError:
            logger.exception("Could not schedule monitoring WebSocket event delivery.")
            return
        future.add_done_callback(self._log_delivery_failure)

    @staticmethod
    def _log_delivery_failure(future) -> None:
        try:
            future.result()
        except Exception:
            logger.exception("Monitoring WebSocket event delivery failed.")


event_hub = MonitoringEventHub()


def alert_event(alert) -> dict:
    return {
        "event": "ALERT_CREATED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "alert": {
            "id": str(alert.id),
            "project_id": str(alert.project_id),
            "endpoint": alert.endpoint,
            "alert_type": alert.alert_type,
            "severity": alert.severity,
            "title": alert.title,
            "message": alert.message,
            "status": alert.status,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
            "metrics": alert.metrics,
            "recommendation": alert.recommendation,
        },
    }
