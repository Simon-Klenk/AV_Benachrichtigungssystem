# async_queue.py
#
# This file provides an asynchronous queue implementation (AsyncQueue)
# designed for MicroPython environments, offering awaitable put and get operations.
# It mimics the behavior of asyncio.Queue but is optimized for resource-constrained devices.
#
# Author: Simon Klenk 2025
# License: MIT - See the LICENSE file in the project directory for the full license text.
import uasyncio as asyncio
from collections import deque
import sys

class AsyncQueue:
    """
    An asynchronous queue implementation similar to asyncio.Queue,
    designed for MicroPython environments.
    It supports a maximum size and provides awaitable put and get operations.
    """
    def __init__(self, maxsize=10): # Default maxsize is now 10 as requested.
        """
        Initializes the AsyncQueue.
        :param maxsize: The maximum number of items allowed in the queue.
                        If maxsize is 0, the queue size is infinite (conceptually).
                        If maxsize is > 0, the queue will block when full.
                        Must be non-negative.
        """
        if not isinstance(maxsize, int) or maxsize < 0:
            raise ValueError("maxsize must be a non-negative integer")

        self._maxsize = maxsize
        
        # Determine the internal maxlen for the collections.deque.
        # This is important for MicroPython where a truly unbounded deque might be problematic.
        if maxsize > 0:
            deque_internal_maxlen = maxsize
        elif maxsize == 0:
            deque_internal_maxlen = 20 # A practical default for MicroPython.
            print(f"Warning: AsyncQueue initialized with maxsize=0. Using internal deque maxlen of {deque_internal_maxlen} due to MicroPython considerations.")

        self._queue = deque((), deque_internal_maxlen) 
        
        # Events to signal when items are available (for get) or space is available (for put).
        self._get_event = asyncio.Event()
        self._put_event = asyncio.Event()

    async def put(self, item):
        """
        Puts an item into the queue.
        If the queue is full (and maxsize > 0), this coroutine will wait until space is available.
        :param item: The item to put into the queue.
        """
        # If maxsize is greater than 0 and the queue is full, wait for space.
        while self._maxsize > 0 and len(self._queue) >= self._maxsize:
            self._put_event.clear() # Clear the event to wait for space
            await self._put_event.wait() # Wait until an item is removed
        
        self._queue.append(item) # Add the item to the deque
        self._get_event.set() # Signal that an item is available for 'get'

    async def get(self):
        """
        Removes and returns an item from the queue.
        If the queue is empty, this coroutine will wait until an item is available.
        :return: The item removed from the queue.
        """
        # If the queue is empty, wait for an item to be put.
        while not self._queue:
            self._get_event.clear() # Clear the event to wait for an item
            await self._get_event.wait() # Wait until an item is available
        
        item = self._queue.popleft() # Remove the oldest item from the deque
        self._put_event.set() # Signal that space is available for 'put'
        return item

    def qsize(self):
        """
        Returns the number of items currently in the queue.
        :return: The current size of the queue.
        """
        return len(self._queue)

    def empty(self):
        """
        Returns True if the queue is empty, False otherwise.
        :return: True if empty, False otherwise.
        """
        return len(self._queue) == 0

    def full(self):
        """
        Returns True if the queue has maxsize items in it.
        If the queue was initialized with maxsize=0, then full() is never True.
        :return: True if full, False otherwise.
        """
        return self._maxsize > 0 and len(self._queue) >= self._maxsize

# --- Example Usage ---

async def producer(queue, name, count):
    """
    A producer coroutine that puts a specified number of items into the queue.
    :param queue: The AsyncQueue instance.
    :param name: Name of the producer for logging.
    :param count: Number of items to produce.
    """
    for i in range(count):
        item = f"Message {i} from {name}"
        print(f"[{name}] Producing: {item}")
        await queue.put(item) # Put item into the queue, waiting if full
        await asyncio.sleep_ms(100 + i * 10) # Simulate work

async def consumer(queue, name):
    """
    A consumer coroutine that continuously gets items from the queue.
    :param queue: The AsyncQueue instance.
    :param name: Name of the consumer for logging.
    """
    while True:
        item = await queue.get() # Get item from the queue, waiting if empty
        print(f"[{name}] Consuming: {item}")
        await asyncio.sleep_ms(200) # Simulate work

async def main():
    """
    Main asynchronous function to set up and run producers and consumers.
    """
    # Initialize AsyncQueue. By default, maxsize is 10.
    # To explicitly set a different size, use e.g., AsyncQueue(maxsize=5)
    q = AsyncQueue() # Using the new default maxsize of 10

    print(f"Queue initialized with maxsize: {q._maxsize}")

    # Start producer and consumer tasks
    producer_task1 = asyncio.create_task(producer(q, "Prod A", 10))
    producer_task2 = asyncio.create_task(producer(q, "Prod B", 8))
    consumer_task1 = asyncio.create_task(consumer(q, "Cons 1"))
    consumer_task2 = asyncio.create_task(consumer(q, "Cons 2"))

    # Wait until all producers have finished their work
    await asyncio.gather(producer_task1, producer_task2)

    print("\nAll producers have finished. Waiting for consumers to process remaining items...")
    # Optional: In a real application, you might want a mechanism to signal consumers to stop
    # (e.g., by putting a sentinel value in the queue) or cancel their tasks.
    # For this example, we'll let them run for a bit longer to clear the queue.
    await asyncio.sleep(5) # Give consumers time to process remaining items
    print("Exiting program.")
    
    # Cancel consumer tasks to properly shut down
    consumer_task1.cancel()
    consumer_task2.cancel()
    try:
        await asyncio.gather(consumer_task1, consumer_task2, return_exceptions=True)
    except asyncio.CancelledError:
        pass # Expected when cancelling tasks

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program manually terminated.")
    except Exception as e:
        print(f"An error occurred: {e}")