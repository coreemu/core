import logging
import threading
import time
from typing import TYPE_CHECKING, Any, Callable, Optional, Tuple

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
        self.app: "Application" = app
        self.title: str = title
        self.task: Callable = task
        self.callback: Callable = callback
        if args is None:
            args = ()
        self.args: Tuple[Any] = args
        self.time: Optional[float] = None

    def start(self) -> None:
        self.app.progress.grid(sticky="ew", columnspan=2)
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

    def complete(self) -> None:
        self.app.progress.stop()
        self.app.progress.grid_forget()
        total = time.perf_counter() - self.time
        self.time = None
        message = f"{self.title} ran for {total:.3f} seconds"
        self.app.statusbar.set_status(message)
