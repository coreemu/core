#
# CORE
# Copyright (c)2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# authors: Tom Goff <thomas.goff@boeing.com>
#
'''
event.py: event loop implementation using a heap queue and threads.
'''
import time
import threading
import heapq

class EventLoop(object):

    class Event(object):
        def __init__(self, eventnum, time, func, *args, **kwds):
            self.eventnum = eventnum
            self.time = time
            self.func = func
            self.args = args
            self.kwds = kwds
            self.canceled = False

        def __cmp__(self, other):
            tmp = cmp(self.time, other.time)
            if tmp == 0:
                tmp = cmp(self.eventnum, other.eventnum)
            return tmp

        def run(self):
            if self.canceled:
                return
            self.func(*self.args, **self.kwds)

        def cancel(self):
            self.canceled = True      # XXX not thread-safe

    def __init__(self):
        self.lock = threading.RLock()
        self.queue = []
        self.eventnum = 0
        self.timer = None
        self.running = False
        self.start = None

    def __del__(self):
        self.stop()

    def __run_events(self):
        schedule = False
        while True:
            with self.lock:
                if not self.running or not self.queue:
                    break
                now = time.time()
                if self.queue[0].time > now:
                    schedule = True
                    break
                event = heapq.heappop(self.queue)
            assert event.time <= now
            event.run()
        with self.lock:
            self.timer = None
            if schedule:
                self.__schedule_event()

    def __schedule_event(self):
        with self.lock:
            assert self.running
            if not self.queue:
                return
            delay = self.queue[0].time - time.time()
            assert self.timer is None
            self.timer = threading.Timer(delay, self.__run_events)
            self.timer.daemon = True
            self.timer.start()

    def run(self):
        with self.lock:
            if self.running:
                return
            self.running = True
            self.start = time.time()
            for event in self.queue:
                event.time += self.start
            self.__schedule_event()

    def stop(self):
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

    def add_event(self, delaysec, func, *args, **kwds):
        with self.lock:
            eventnum = self.eventnum
            self.eventnum += 1
            evtime = float(delaysec)
            if self.running:
                evtime += time.time()
            event = self.Event(eventnum, evtime, func, *args, **kwds)

            if self.queue:
                prevhead = self.queue[0]
            else:
                prevhead = None

            heapq.heappush(self.queue, event)
            head = self.queue[0]
            if prevhead is not None and prevhead != head:
                if self.timer is not None and not self.timer.is_alive():
                    self.timer.cancel()
                    self.timer = None

            if self.running and self.timer is None:
                self.__schedule_event()
        return event

def example():
    loop = EventLoop()

    def msg(arg):
        delta = time.time() - loop.start
        print delta, 'arg:', arg

    def repeat(interval, count):
        count -= 1
        msg('repeat: interval: %s; remaining: %s' % (interval, count))
        if count > 0:
            loop.add_event(interval, repeat, interval, count)

    def sleep(delay):
        msg('sleep %s' % delay)
        time.sleep(delay)
        msg('sleep done')

    def stop(arg):
        msg(arg)
        loop.stop()

    loop.add_event(0, msg, 'start')
    loop.add_event(0, msg, 'time zero')

    for delay in 5, 4, 10, -1, 0, 9, 3, 7, 3.14:
        loop.add_event(delay, msg, 'time %s' % delay)

    loop.run()

    loop.add_event(0, repeat, 1, 5)
    loop.add_event(12, sleep, 10)

    loop.add_event(15.75, stop, 'stop time: 15.75')
