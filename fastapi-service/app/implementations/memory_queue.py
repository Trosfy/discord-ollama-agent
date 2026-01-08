"""In-memory queue implementation with SQS-like visibility timeout."""
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict
from uuid import uuid4

from app.interfaces.queue import QueueInterface
from app.config import settings


class MemoryQueue(QueueInterface):
    """In-memory FIFO queue with visibility timeout and retry logic."""

    def __init__(self):
        self.queue = asyncio.Queue(maxsize=settings.MAX_QUEUE_SIZE)
        self.in_flight: Dict[str, Dict] = {}  # request_id -> (request, deadline)
        self.completed: Dict[str, Dict] = {}  # request_id -> result
        self.failed: Dict[str, Dict] = {}  # request_id -> error info
        self._monitor_task: Optional[asyncio.Task] = None

    async def start(self):
        """Start background monitoring for visibility timeouts."""
        self._monitor_task = asyncio.create_task(self._monitor_visibility_timeouts())

    async def stop(self):
        """Stop background monitoring."""
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

    async def enqueue(self, request: Dict) -> str:
        """Add request to queue."""
        if self.is_full():
            raise Exception("Queue is full")

        request_id = str(uuid4())
        request['request_id'] = request_id
        request['enqueued_at'] = datetime.utcnow()
        request['attempt'] = 0
        request['state'] = 'queued'

        await self.queue.put(request)
        return request_id

    async def dequeue(self) -> Optional[Dict]:
        """Get next request and mark as in-flight."""
        try:
            request = await asyncio.wait_for(self.queue.get(), timeout=0.1)
            request_id = request['request_id']

            # Check if request was cancelled
            if request_id in self.failed and self.failed[request_id].get('cancelled'):
                return None

            # Mark as in-flight with visibility timeout
            deadline = datetime.utcnow() + timedelta(
                seconds=settings.VISIBILITY_TIMEOUT
            )
            self.in_flight[request_id] = {
                'request': request,
                'deadline': deadline
            }

            request['state'] = 'processing'
            return request

        except asyncio.TimeoutError:
            return None

    async def get_status(self, request_id: str) -> Dict:
        """Get current status of a request."""
        # Check in-flight
        if request_id in self.in_flight:
            return {
                'status': 'processing',
                'request_id': request_id
            }

        # Check completed
        if request_id in self.completed:
            return {
                'status': 'completed',
                'request_id': request_id,
                'result': self.completed[request_id]
            }

        # Check failed
        if request_id in self.failed:
            return {
                'status': 'failed',
                'request_id': request_id,
                'error': self.failed[request_id]
            }

        # Check if still in queue
        return {'status': 'queued', 'request_id': request_id}

    async def get_position(self, request_id: str) -> int:
        """Get queue position."""
        # If not in queue, return 0
        if request_id in self.in_flight:
            return 0  # Being processed
        if request_id in self.completed or request_id in self.failed:
            return 0  # Done

        # Count items in queue (approximate - queue doesn't support peeking easily)
        return self.queue.qsize()

    async def mark_complete(self, request_id: str, result: Dict) -> None:
        """Mark request as completed."""
        if request_id in self.in_flight:
            del self.in_flight[request_id]

        self.completed[request_id] = result

        # Clean up old completed requests (keep last 100)
        if len(self.completed) > 100:
            oldest_keys = list(self.completed.keys())[:50]
            for key in oldest_keys:
                del self.completed[key]

    async def mark_failed(self, request_id: str, error: str) -> bool:
        """Mark request as failed and handle retry logic."""
        if request_id not in self.in_flight:
            return False

        request_data = self.in_flight[request_id]['request']
        request_data['attempt'] += 1

        # Check if we should retry
        if request_data['attempt'] < settings.MAX_RETRIES:
            # Re-queue with delay
            del self.in_flight[request_id]
            await asyncio.sleep(settings.RETRY_DELAY)
            await self.queue.put(request_data)
            return True
        else:
            # Max retries exceeded
            del self.in_flight[request_id]
            self.failed[request_id] = {
                'error': error,
                'attempts': request_data['attempt'],
                'timestamp': datetime.utcnow().isoformat()
            }
            return False

    async def cancel(self, request_id: str) -> bool:
        """Cancel a queued request."""
        # Can't cancel if already processing
        if request_id in self.in_flight:
            return False

        # Mark as cancelled (pseudo-cancel since we can't remove from asyncio.Queue)
        # We'll filter it out when dequeuing
        if request_id in self.completed or request_id in self.failed:
            return False

        # Add to failed with cancelled status
        self.failed[request_id] = {
            'error': 'Cancelled by user',
            'cancelled': True,
            'timestamp': datetime.utcnow().isoformat()
        }
        return True

    def size(self) -> int:
        """Get current queue size."""
        return self.queue.qsize()

    def is_full(self) -> bool:
        """Check if queue is at capacity."""
        return self.queue.full()

    async def _monitor_visibility_timeouts(self):
        """Background task to check for timed-out requests."""
        while True:
            await asyncio.sleep(10)  # Check every 10 seconds

            now = datetime.utcnow()
            expired = [
                req_id
                for req_id, data in self.in_flight.items()
                if now > data['deadline']
            ]

            for req_id in expired:
                # Requeue expired requests
                await self.mark_failed(
                    req_id,
                    "Request timed out (visibility timeout expired)"
                )
