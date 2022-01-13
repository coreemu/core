import logging
import threading
import time
import tkinter as tk
from typing import TYPE_CHECKING, Any, Callable, Optional, Tuple

logger = logging.getLogger(__name__)

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
        self.app.progress.grid(sticky=tk.EW, columnspan=2)
        self.app.progress.start()
        self.time = time.perf_counter()
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()

    def run(self) -> None:
        try:
            values = self.task(*self.args)
            if values is None:
                values = ()
            elif values is not None and not isinstance(values, tuple):
                values = (values,)
            if self.callback:
                self.app.after(0, self.callback, *values)
        except Exception as e:
            logger.exception("progress task exception")
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
