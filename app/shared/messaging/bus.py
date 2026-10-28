"""RabbitMQ topic exchange client used by every AfterCare service.

Publishing wraps a Pydantic event in a JSON envelope. Consuming hands the same
envelope to a handler and propagates its correlation ID into the log context so
one discharge intake is traceable end to end.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

import aio_pika
from pydantic import BaseModel

from app.shared.core.config import get_settings
from app.shared.core.logging import correlation_id_var, get_logger

logger = get_logger("event_bus")

EXCHANGE_NAME = "aftercare"
CONNECT_ATTEMPTS = 12
CONNECT_BACKOFF_SECONDS = 1.5

EventHandler = Callable[[dict[str, Any]], Awaitable[None]]


class EventBus:
    """Robust connection + topic exchange for publishing and subscribing."""

    def __init__(self) -> None:
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None
        self._exchange: aio_pika.abc.AbstractExchange | None = None

    async def connect(self) -> None:
        """Connect with retries so services can start before RabbitMQ is warm."""
        url = get_settings().rabbitmq_url
        last_error: Exception | None = None

        for attempt in range(CONNECT_ATTEMPTS):
            try:
                self._connection = await aio_pika.connect_robust(url)
                break
            except Exception as exc:  # noqa: BLE001 - retried below
                last_error = exc
                logger.warning(
                    "event_bus_connect_retry",
                    attempt=attempt + 1,
                    host=url.split("@")[-1],
                )
                await asyncio.sleep(CONNECT_BACKOFF_SECONDS)
        else:
            assert last_error is not None
            raise last_error

        self._channel = await self._connection.channel()
        self._exchange = await self._channel.declare_exchange(
            EXCHANGE_NAME,
            aio_pika.ExchangeType.TOPIC,
            durable=True,
        )
        logger.info("event_bus_connected", exchange=EXCHANGE_NAME)

    async def disconnect(self) -> None:
        if self._channel:
            await self._channel.close()
        if self._connection:
            await self._connection.close()
        logger.info("event_bus_disconnected")

    @property
    def exchange(self) -> aio_pika.abc.AbstractExchange:
        if not self._exchange:
            raise RuntimeError("Event bus is not connected; call connect() first.")
        return self._exchange

    @property
    def channel(self) -> aio_pika.abc.AbstractChannel:
        if not self._channel:
            raise RuntimeError("Event bus is not connected; call connect() first.")
        return self._channel

    async def publish(
        self,
        event_name: str,
        payload: BaseModel,
        correlation_id: str | None = None,
        source_service: str = "unknown",
    ) -> None:
        """Publish `payload` on the topic matching `event_name`."""
        cid = correlation_id or correlation_id_var.get() or str(uuid.uuid4())
        envelope = {
            "event_type": event_name,
            "correlation_id": cid,
            "source_service": source_service,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "payload": payload.model_dump(mode="json"),
        }
        message = aio_pika.Message(
            body=json.dumps(envelope).encode(),
            content_type="application/json",
            headers={"correlation_id": cid},
        )
        await self.exchange.publish(message, routing_key=event_name)
        logger.info("event_published", event_type=event_name, correlation_id=cid)

    async def subscribe(
        self,
        event_name: str,
        handler: EventHandler,
        queue_name: str | None = None,
    ) -> None:
        """Bind a durable queue to `event_name` and dispatch each message to `handler`."""
        queue_label = queue_name or f"{event_name}_queue"
        queue = await self.channel.declare_queue(queue_label, durable=True)
        await queue.bind(self.exchange, routing_key=event_name)

        async def _handle(message: aio_pika.abc.AbstractIncomingMessage) -> None:
            async with message.process():
                try:
                    envelope = json.loads(message.body.decode())
                    cid = envelope.get("correlation_id", "")
                    correlation_id_var.set(cid)
                    logger.info("event_received", event_type=event_name, correlation_id=cid)
                    await handler(envelope)
                except Exception:  # noqa: BLE001 - never kill the consumer loop
                    logger.exception("event_handler_error", event_type=event_name)

        await queue.consume(_handle)
        logger.info("event_subscribed", event_type=event_name, queue=queue_label)


event_bus = EventBus()
