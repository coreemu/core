import logging
import time

from core.misc.event import EventLoop


def main():
    loop = EventLoop()

    def msg(arg):
        delta = time.time() - loop.start
        logging.debug("%s arg: %s", delta, arg)

    def repeat(interval, count):
        count -= 1
        msg("repeat: interval: %s; remaining: %s" % (interval, count))
        if count > 0:
            loop.add_event(interval, repeat, interval, count)

    def sleep(delay):
        msg("sleep %s" % delay)
        time.sleep(delay)
        msg("sleep done")

    def stop(arg):
        msg(arg)
        loop.stop()

    loop.add_event(0, msg, "start")
    loop.add_event(0, msg, "time zero")

    for delay in 5, 4, 10, -1, 0, 9, 3, 7, 3.14:
        loop.add_event(delay, msg, "time %s" % delay)

    loop.run()

    loop.add_event(0, repeat, 1, 5)
    loop.add_event(12, sleep, 10)

    loop.add_event(15.75, stop, "stop time: 15.75")


if __name__ == "__main__":
    main()
