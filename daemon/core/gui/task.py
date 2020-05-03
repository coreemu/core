import logging
import threading
from typing import Any, Callable, Tuple


class ProgressTask:
    def __init__(
        self, task: Callable, callback: Callable = None, args: Tuple[Any] = None
    ):
        self.app = None
        self.task = task
        self.callback = callback
        self.args = args
        if self.args is None:
            self.args = ()

    def start(self) -> None:
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()

    def run(self) -> None:
        logging.info("running task")
        try:
            values = self.task(*self.args)
            if values is None:
                values = ()
            elif values and not isinstance(values, tuple):
                values = (values,)
            if self.callback:
                logging.info("calling callback")
                self.app.after(0, self.callback, *values)
        except Exception as e:
            logging.exception("progress task exception")
            self.app.show_exception("Task Error", e)
        finally:
            self.app.after(0, self.app.progress_task_complete)
