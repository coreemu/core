import logging
import threading
from typing import Any, Callable

from core.gui.errors import show_grpc_response_exceptions


class BackgroundTask:
    def __init__(self, master: Any, task: Callable, callback: Callable = None, args=()):
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
        # if start session fails, a response with Result: False and a list of
        # exceptions is returned
        if not getattr(result, "result", True):
            if len(getattr(result, "exceptions", [])) > 0:
                self.master.after(
                    0,
                    show_grpc_response_exceptions,
                    *(
                        result.__class__.__name__,
                        result.exceptions,
                        self.master,
                        self.master,
                    )
                )
        if self.callback:
            if result is None:
                args = ()
            elif isinstance(result, (list, tuple)):
                args = result
            else:
                args = (result,)
            logging.info("calling callback: %s", args)
            self.master.after(0, self.callback, *args)
