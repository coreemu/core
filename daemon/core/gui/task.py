import logging
import threading
from typing import Callable, Optional


class BackgroundTask:
    def __init__(
        self, master, task: Callable, callback: Optional[Callable] = None, args=()
    ):
        self.master = master
        self.args = args
        self.task = task
        self.callback = callback
        self.thread = None

    def start(self):
        logging.info("starting task")
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self):
        result = self.task(*self.args)
        logging.info("task completed")
        if self.callback:
            if result is None:
                args = ()
            elif isinstance(result, (list, tuple)):
                args = result
            else:
                args = (result,)
            logging.info("calling callback: %s", args)
            self.master.after(0, self.callback, *args)
