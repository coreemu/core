import logging
import threading
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from core.gui.app import Application


class BackgroundTask:
    def __init__(
        self, master: "Application", task: Callable, callback: Callable = None, args=()
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
