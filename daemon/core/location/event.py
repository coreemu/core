"""
event.py: event loop implementation using a heap queue and threads.
"""

import heapq
import threading
import time
from functools import total_ordering
from typing import Any, Callable, Dict, List, Optional, Tuple


class Timer(threading.Thread):
    """
    Based on threading.Timer but cancel() returns if the timer was
    already running.
    """

    def __init__(
        self,
        interval: float,
        func: Callable[..., None],
        args: Tuple[Any] = None,
        kwargs: Dict[Any, Any] = None,
    ) -> None:
        """
        Create a Timer instance.

        :param interval: time interval
        :param func: function to call when timer finishes
        :param args: function arguments
        :param kwargs: function keyword arguments
        """
        super().__init__()
        self.interval: float = interval
        self.func: Callable[..., None] = func
        self.finished: threading.Event = threading.Event()
        self._running: threading.Lock = threading.Lock()
        # validate arguments were provided
        if args is None:
            args = ()
        self.args: Tuple[Any] = args
        # validate keyword arguments were provided
        if kwargs is None:
            kwargs = {}
        self.kwargs: Dict[Any, Any] = kwargs

    def cancel(self) -> bool:
        """
        Stop the timer if it hasn't finished yet.  Return False if
        the timer was already running.

        :return: True if canceled, False otherwise
        """
        locked = self._running.acquire(False)
        if locked:
            self.finished.set()
            self._running.release()
        return locked

    def run(self) -> None:
        """
        Run the timer.

        :return: nothing
        """
        self.finished.wait(self.interval)
        with self._running:
            if not self.finished.is_set():
                self.func(*self.args, **self.kwargs)
            self.finished.set()


@total_ordering
class Event:
    """
    Provides event objects that can be used within the EventLoop class.
    """

    def __init__(
        self,
        eventnum: int,
        event_time: float,
        func: Callable[..., None],
        *args: Any,
        **kwds: Any
    ) -> None:
        """
        Create an Event instance.

        :param eventnum: event number
        :param event_time: event time
        :param func: event function
        :param args: function arguments
        :param kwds: function keyword arguments
        """
        self.eventnum: int = eventnum
        self.time: float = event_time
        self.func: Callable[..., None] = func
        self.args: Tuple[Any] = args
        self.kwds: Dict[Any, Any] = kwds
        self.canceled: bool = False

    def __lt__(self, other: "Event") -> bool:
        result = self.time < other.time
        if result:
            result = self.eventnum < other.eventnum
        return result

    def run(self) -> None:
        """
        Run an event.

        :return: nothing
        """
        if self.canceled:
            return
        self.func(*self.args, **self.kwds)

    def cancel(self) -> None:
        """
        Cancel event.

        :return: nothing
        """
        self.canceled = True


class EventLoop:
    """
    Provides an event loop for running events.
    """

    def __init__(self) -> None:
        """
        Creates a EventLoop instance.
        """
        self.lock: threading.RLock = threading.RLock()
        self.queue: List[Event] = []
        self.eventnum: int = 0
        self.timer: Optional[Timer] = None
        self.running: bool = False
        self.start: Optional[float] = None

    def _run_events(self) -> None:
        """
        Run events.

        :return: nothing
        """
        schedule = False
        while True:
            with self.lock:
                if not self.running or not self.queue:
                    break
                now = time.monotonic()
                if self.queue[0].time > now:
                    schedule = True
                    break
                event = heapq.heappop(self.queue)
            if event.time > now:
                raise ValueError("invalid event time: %s > %s", event.time, now)
            event.run()

        with self.lock:
            self.timer = None
            if schedule:
                self._schedule_event()

    def _schedule_event(self) -> None:
        """
        Schedule event.

        :return: nothing
        """
        with self.lock:
            if not self.running:
                raise ValueError("scheduling event while not running")
            if not self.queue:
                return
            delay = self.queue[0].time - time.monotonic()
            if self.timer:
                raise ValueError("timer was already set")
            self.timer = Timer(delay, self._run_events)
            self.timer.daemon = True
            self.timer.start()

    def run(self) -> None:
        """
        Start event loop.

        :return: nothing
        """
        with self.lock:
            if self.running:
                return
            self.running = True
            self.start = time.monotonic()
            for event in self.queue:
                event.time += self.start
            self._schedule_event()

    def stop(self) -> None:
        """
        Stop event loop.

        :return: nothing
        """
        with self.lock:
            if not self.running:
                return
            self.queue = []
            self.eventnum = 0
            if self.timer is not None:
                self.timer.cancel()
                self.timer = None
            self.running = False
            self.start = None

    def add_event(self, delaysec: float, func: Callable, *args: Any, **kwds: Any):
        """
        Add an event to the event loop.

        :param delaysec: delay in seconds for event
        :param func: event function
        :param args: event arguments
        :param kwds: event keyword arguments
        :return: created event
        """
        with self.lock:
            eventnum = self.eventnum
            self.eventnum += 1
            evtime = float(delaysec)
            if self.running:
                evtime += time.monotonic()
            event = Event(eventnum, evtime, func, *args, **kwds)

            if self.queue:
                prevhead = self.queue[0]
            else:
                prevhead = None

            heapq.heappush(self.queue, event)
            head = self.queue[0]
            if prevhead is not None and prevhead != head:
                if self.timer is not None and self.timer.cancel():
                    self.timer = None
            if self.running and self.timer is None:
                self._schedule_event()
        return event
