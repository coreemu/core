import logging
import threading
import time
from typing import TYPE_CHECKING, Any, Callable, Tuple

if TYPE_CHECKING:
    from core.gui.app import Application


class ProgressTask:
    def __init__(
        self,
        app: "Application",
        title: str,
        task: Callable,
        callback: Callable = None,
        args: Tuple[Any] = None,
    ):
        self.app = app
        self.title = title
        self.task = task
        self.callback = callback
        self.args = args
        if self.args is None:
            self.args = ()
        self.time = None

    def start(self) -> None:
        self.app.progress.grid(sticky="ew")
        self.app.progress.start()
        self.time = time.perf_counter()
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
            self.app.after(0, self.complete)

    def complete(self):
        self.app.progress.stop()
        self.app.progress.grid_forget()
        total = time.perf_counter() - self.time
        self.time = None
        message = f"{self.title} ran for {total:.3f} seconds"
        self.app.statusbar.set_status(message)
