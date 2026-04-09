"""
Log Stream WebSocket
====================

WebSocket handler that subscribes to a Redis pub/sub channel and forwards
every message to the connected browser client.

Each job has a dedicated Redis channel named ``job:{job_id}:logs``.  The
Celery task publishes JSON messages to this channel as the script runs;
this handler relays them to the frontend in real time.

Message shapes forwarded to the client:
    ``{"type": "status", "data": "running" | "success" | "failed"}``
    ``{"type": "log", "data": "<line>"}``

Usage:
    Mount via the FastAPI WebSocket decorator in ``api/main.py`` or a router:

    @app.websocket("/api/ws/jobs/{job_id}/logs")
    async def ws_job_logs(websocket: WebSocket, job_id: str) -> None:
        await log_stream_ws(websocket, job_id)
"""

import logging

import redis.asyncio as aioredis
from fastapi import WebSocket, WebSocketDisconnect

from api.config import get_settings

logger = logging.getLogger(__name__)


async def log_stream_ws(websocket: WebSocket, job_id: str) -> None:
    """Handle a WebSocket connection, streaming job logs from Redis pub/sub.

    Subscribes to the ``job:{job_id}:logs`` Redis channel and forwards
    every message to the connected browser client until the client
    disconnects or the channel is exhausted.

    The connection is accepted before subscriptions are set up, so the
    client immediately receives a 101 Switching Protocols response.  If
    Redis is unavailable, the connection is closed cleanly with a log
    warning rather than propagating an exception.

    Args:
        websocket: The active WebSocket connection from FastAPI.
        job_id: UUID string of the job whose logs to stream.
    """
    await websocket.accept()
    settings = get_settings()
    client = aioredis.from_url(settings.redis_url)
    pubsub = client.pubsub()

    try:
        await pubsub.subscribe(f"job:{job_id}:logs")
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                # Redis returns bytes; decode before forwarding.
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                await websocket.send_text(data)
    except WebSocketDisconnect:
        logger.debug("WebSocket client disconnected for job %s.", job_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("WebSocket error for job %s: %s", job_id, exc)
    finally:
        try:
            await pubsub.unsubscribe()
        except Exception:  # noqa: BLE001
            pass
        try:
            await client.aclose()
        except Exception:  # noqa: BLE001
            pass
