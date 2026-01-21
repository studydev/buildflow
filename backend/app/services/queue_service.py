"""
Queue service for Azure Service Bus messaging.

Per tasks.md T110: Create queue_service.py for Service Bus.

Provides methods to:
- Send messages to topics
- Send with delay (for retry scheduling)
- Receive messages from subscriptions
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, TYPE_CHECKING

from app.config import get_settings
from app.schemas.pipeline import PipelineMessage

logger = logging.getLogger(__name__)


# Check if Azure SDK is available
AZURE_SDK_AVAILABLE = False
ServiceBusClient: Any = None
ServiceBusMessage: Any = None
ServiceBusError: Any = Exception

try:
    from azure.servicebus import ServiceBusClient as SBClient  # type: ignore[import-not-found]
    from azure.servicebus import ServiceBusMessage as SBMessage  # type: ignore[import-not-found]
    from azure.servicebus.exceptions import ServiceBusError as SBError  # type: ignore[import-not-found]
    AZURE_SDK_AVAILABLE = True
    ServiceBusClient = SBClient
    ServiceBusMessage = SBMessage
    ServiceBusError = SBError
except ImportError:
    pass


class QueueService:
    """
    Service for Azure Service Bus operations.
    
    Per tasks.md T110:
    - send_to_topic(): Send message to a topic
    - send_with_delay(): Send with scheduled delivery
    - receive_message(): Receive from subscription
    
    Falls back to mock implementation when:
    - Azure SDK not installed
    - No connection string configured
    - Running in local development mode
    """
    
    def __init__(self):
        self._client: Any = None
        self._settings = get_settings()
        self._mock_queues: dict[str, list[PipelineMessage]] = {}
    
    @property
    def is_mock(self) -> bool:
        """Check if using mock implementation."""
        if not AZURE_SDK_AVAILABLE:
            return True
        conn_str = os.environ.get("SERVICEBUS_CONNECTION_STRING") or getattr(
            self._settings, "servicebus_connection_string", None
        )
        return not conn_str
    
    @property
    def client(self) -> Any:
        """Lazy initialization of Service Bus client."""
        if self._client is None and not self.is_mock and ServiceBusClient is not None:
            conn_str = os.environ.get("SERVICEBUS_CONNECTION_STRING") or getattr(
                self._settings, "servicebus_connection_string", None
            )
            if conn_str:
                self._client = ServiceBusClient.from_connection_string(conn_str)
        return self._client
    
    async def send_to_topic(
        self,
        topic: str,
        message: PipelineMessage,
    ) -> None:
        """
        Send a pipeline message to a Service Bus topic.
        
        Args:
            topic: Topic name (e.g., "pipeline-triggers")
            message: PipelineMessage to send
        """
        if self.is_mock:
            await self._mock_send(topic, message)
            return
        
        try:
            with self.client.get_topic_sender(topic) as sender:
                # Create message with custom properties for filtering
                sb_message = ServiceBusMessage(
                    body=message.to_service_bus_message(),
                    application_properties={
                        "pipeline_type": message.pipeline_type.value if hasattr(message.pipeline_type, 'value') else message.pipeline_type,
                        "correlation_id": message.correlation_id,
                        "run_id": str(message.run_id),
                    },
                    correlation_id=message.correlation_id,
                )
                
                sender.send_messages(sb_message)
                
                logger.info(
                    "Message sent to Service Bus",
                    extra={
                        "topic": topic,
                        "run_id": str(message.run_id),
                        "pipeline_type": message.pipeline_type,
                        "correlation_id": message.correlation_id,
                    }
                )
                
        except ServiceBusError as e:
            logger.error(
                "Failed to send message to Service Bus",
                extra={
                    "topic": topic,
                    "run_id": str(message.run_id),
                    "error": str(e),
                }
            )
            raise
    
    async def send_with_delay(
        self,
        topic: str,
        message: PipelineMessage,
        delay_seconds: int,
    ) -> None:
        """
        Send a pipeline message with scheduled delivery.
        
        Used for retry scheduling with exponential backoff.
        
        Args:
            topic: Topic name
            message: PipelineMessage to send
            delay_seconds: Seconds to delay delivery
        """
        if self.is_mock:
            await self._mock_send(topic, message, delay_seconds)
            return
        
        try:
            scheduled_time = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
            
            with self.client.get_topic_sender(topic) as sender:
                sb_message = ServiceBusMessage(
                    body=message.to_service_bus_message(),
                    application_properties={
                        "pipeline_type": message.pipeline_type.value if hasattr(message.pipeline_type, 'value') else message.pipeline_type,
                        "correlation_id": message.correlation_id,
                        "run_id": str(message.run_id),
                        "attempt_number": message.attempt_number,
                    },
                    scheduled_enqueue_time_utc=scheduled_time,
                    correlation_id=message.correlation_id,
                )
                
                sender.send_messages(sb_message)
                
                logger.info(
                    "Scheduled message sent to Service Bus",
                    extra={
                        "topic": topic,
                        "run_id": str(message.run_id),
                        "delay_seconds": delay_seconds,
                        "scheduled_time": scheduled_time.isoformat(),
                        "correlation_id": message.correlation_id,
                    }
                )
                
        except ServiceBusError as e:
            logger.error(
                "Failed to send scheduled message to Service Bus",
                extra={
                    "topic": topic,
                    "run_id": str(message.run_id),
                    "delay_seconds": delay_seconds,
                    "error": str(e),
                }
            )
            raise
    
    async def receive_message(
        self,
        topic: str,
        subscription: str,
        timeout_seconds: int = 30,
    ) -> Optional[PipelineMessage]:
        """
        Receive a message from a Service Bus subscription.
        
        Typically used by the pipeline runner, but Container Apps Jobs
        receive messages via environment variable instead.
        
        Args:
            topic: Topic name
            subscription: Subscription name
            timeout_seconds: How long to wait for a message
            
        Returns:
            PipelineMessage if received, None on timeout
        """
        if self.is_mock:
            return await self._mock_receive(topic, subscription)
        
        try:
            with self.client.get_subscription_receiver(
                topic_name=topic,
                subscription_name=subscription,
                max_wait_time=timeout_seconds,
            ) as receiver:
                messages = receiver.receive_messages(max_message_count=1)
                
                if messages:
                    msg = messages[0]
                    body = str(msg)
                    
                    # Complete the message
                    receiver.complete_message(msg)
                    
                    return PipelineMessage.from_service_bus_message(body)
                
                return None
                
        except ServiceBusError as e:
            logger.error(
                "Failed to receive message from Service Bus",
                extra={
                    "topic": topic,
                    "subscription": subscription,
                    "error": str(e),
                }
            )
            raise
    
    # =========================================================================
    # Mock Implementation for Local Development
    # =========================================================================
    
    async def _mock_send(
        self,
        topic: str,
        message: PipelineMessage,
        delay_seconds: int = 0,
    ) -> None:
        """Mock send for local development."""
        queue_key = f"{topic}"
        if queue_key not in self._mock_queues:
            self._mock_queues[queue_key] = []
        
        self._mock_queues[queue_key].append(message)
        
        logger.info(
            "[MOCK] Message queued",
            extra={
                "topic": topic,
                "run_id": str(message.run_id),
                "pipeline_type": message.pipeline_type,
                "delay_seconds": delay_seconds,
                "queue_depth": len(self._mock_queues[queue_key]),
            }
        )
    
    async def _mock_receive(
        self,
        topic: str,
        subscription: str,
    ) -> Optional[PipelineMessage]:
        """Mock receive for local development."""
        queue_key = f"{topic}"
        if queue_key not in self._mock_queues or not self._mock_queues[queue_key]:
            return None
        
        message = self._mock_queues[queue_key].pop(0)
        
        logger.info(
            "[MOCK] Message received",
            extra={
                "topic": topic,
                "subscription": subscription,
                "run_id": str(message.run_id),
                "pipeline_type": message.pipeline_type,
            }
        )
        
        return message
    
    def close(self) -> None:
        """Close the Service Bus client."""
        if self._client:
            self._client.close()
            self._client = None


# Singleton instance
_queue_service: Optional[QueueService] = None


def get_queue_service() -> QueueService:
    """Get or create the queue service singleton."""
    global _queue_service
    if _queue_service is None:
        _queue_service = QueueService()
    return _queue_service
