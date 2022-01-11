import logging
import math
import tkinter as tk
from tkinter import PhotoImage, font, messagebox, ttk
from tkinter.ttk import Progressbar
from typing import Any, Dict, Optional, Type

import grpc

from core.gui import appconfig, images
from core.gui import nodeutils as nutils
from core.gui import themes
from core.gui.appconfig import GuiConfig
from core.gui.coreclient import CoreClient
from core.gui.dialogs.error import ErrorDialog
from core.gui.frames.base import InfoFrameBase
from core.gui.frames.default import DefaultInfoFrame
from core.gui.graph.manager import CanvasManager
from core.gui.images import ImageEnum
from core.gui.menubar import Menubar
from core.gui.statusbar import StatusBar
from core.gui.themes import PADY
from core.gui.toolbar import Toolbar

logger = logging.getLogger(__name__)
WIDTH: int = 1000
HEIGHT: int = 800


class Application(ttk.Frame):
    def __init__(self, proxy: bool, session_id: int = None) -> None:
        super().__init__()
        # load node icons
        nutils.setup()

        # widgets
        self.menubar: Optional[Menubar] = None
        self.toolbar: Optional[Toolbar] = None
        self.right_frame: Optional[ttk.Frame] = None
        self.manager: Optional[CanvasManager] = None
        self.statusbar: Optional[StatusBar] = None
        self.progress: Optional[Progressbar] = None
        self.infobar: Optional[ttk.Frame] = None
        self.info_frame: Optional[InfoFrameBase] = None
        self.show_infobar: tk.BooleanVar = tk.BooleanVar(value=False)

        # fonts
        self.fonts_size: Dict[str, int] = {}
        self.icon_text_font: Optional[font.Font] = None
        self.edge_font: Optional[font.Font] = None

        # setup
        self.guiconfig: GuiConfig = appconfig.read()
        self.app_scale: float = self.guiconfig.scale
        self.setup_scaling()
        self.style: ttk.Style = ttk.Style()
        self.setup_theme()
        self.core: CoreClient = CoreClient(self, proxy)
        self.setup_app()
        self.draw()
        self.core.setup(session_id)

    def setup_scaling(self) -> None:
        self.fonts_size = {name: font.nametofont(name)["size"] for name in font.names()}
        text_scale = self.app_scale if self.app_scale < 1 else math.sqrt(self.app_scale)
        themes.scale_fonts(self.fonts_size, self.app_scale)
        self.icon_text_font = font.Font(family="TkIconFont", size=int(12 * text_scale))
        self.edge_font = font.Font(
            family="TkDefaultFont", size=int(8 * text_scale), weight=font.BOLD
        )

    def setup_theme(self) -> None:
        themes.load(self.style)
        self.master.bind_class("Menu", "<<ThemeChanged>>", themes.theme_change_menu)
        self.master.bind("<<ThemeChanged>>", themes.theme_change)
        self.style.theme_use(self.guiconfig.preferences.theme)

    def setup_app(self) -> None:
        self.master.title("CORE")
        self.center()
        self.master.protocol("WM_DELETE_WINDOW", self.on_closing)
        image = images.from_enum(ImageEnum.CORE, width=images.DIALOG_SIZE)
        self.master.tk.call("wm", "iconphoto", self.master._w, image)
        self.master.option_add("*tearOff", tk.FALSE)
        self.setup_file_dialogs()

    def setup_file_dialogs(self) -> None:
        """
        Hack code that needs to initialize a bad dialog so that we can apply,
        global settings for dialogs to not show hidden files by default and display
        the hidden file toggle.

        :return: nothing
        """
        try:
            self.master.tk.call("tk_getOpenFile", "-foobar")
        except tk.TclError:
            pass
        self.master.tk.call("set", "::tk::dialog::file::showHiddenBtn", "1")
        self.master.tk.call("set", "::tk::dialog::file::showHiddenVar", "0")

    def center(self) -> None:
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        x = int((screen_width / 2) - (WIDTH * self.app_scale / 2))
        y = int((screen_height / 2) - (HEIGHT * self.app_scale / 2))
        self.master.geometry(
            f"{int(WIDTH * self.app_scale)}x{int(HEIGHT * self.app_scale)}+{x}+{y}"
        )

    def draw(self) -> None:
        self.master.rowconfigure(0, weight=1)
        self.master.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.columnconfigure(1, weight=1)
        self.grid(sticky=tk.NSEW)
        self.toolbar = Toolbar(self)
        self.toolbar.grid(sticky=tk.NS)
        self.right_frame = ttk.Frame(self)
        self.right_frame.columnconfigure(0, weight=1)
        self.right_frame.rowconfigure(0, weight=1)
        self.right_frame.grid(row=0, column=1, sticky=tk.NSEW)
        self.draw_canvas()
        self.draw_infobar()
        self.draw_status()
        self.progress = Progressbar(self.right_frame, mode="indeterminate")
        self.menubar = Menubar(self)
        self.master.config(menu=self.menubar)

    def draw_infobar(self) -> None:
        self.infobar = ttk.Frame(self.right_frame, padding=5, relief=tk.RAISED)
        self.infobar.columnconfigure(0, weight=1)
        self.infobar.rowconfigure(1, weight=1)
        label_font = font.Font(weight=font.BOLD, underline=tk.TRUE)
        label = ttk.Label(
            self.infobar, text="Details", anchor=tk.CENTER, font=label_font
        )
        label.grid(sticky=tk.EW, pady=PADY)

    def draw_canvas(self) -> None:
        self.manager = CanvasManager(self.right_frame, self, self.core)
        self.manager.notebook.grid(sticky=tk.NSEW)

    def draw_status(self) -> None:
        self.statusbar = StatusBar(self.right_frame, self)
        self.statusbar.grid(sticky=tk.EW, columnspan=2)

    def display_info(self, frame_class: Type[InfoFrameBase], **kwargs: Any) -> None:
        if not self.show_infobar.get():
            return
        self.clear_info()
        self.info_frame = frame_class(self.infobar, **kwargs)
        self.info_frame.draw()
        self.info_frame.grid(sticky=tk.NSEW)

    def clear_info(self) -> None:
        if self.info_frame:
            self.info_frame.destroy()
            self.info_frame = None

    def default_info(self) -> None:
        self.clear_info()
        self.display_info(DefaultInfoFrame, app=self)

    def show_info(self) -> None:
        self.default_info()
        self.infobar.grid(row=0, column=1, sticky=tk.NSEW)

    def hide_info(self) -> None:
        self.infobar.grid_forget()

    def show_grpc_exception(
        self, message: str, e: grpc.RpcError, blocking: bool = False
    ) -> None:
        logger.exception("app grpc exception", exc_info=e)
        dialog = ErrorDialog(self, "GRPC Exception", message, e.details())
        if blocking:
            dialog.show()
        else:
            self.after(0, lambda: dialog.show())

    def show_exception(self, message: str, e: Exception) -> None:
        logger.exception("app exception", exc_info=e)
        self.after(
            0, lambda: ErrorDialog(self, "App Exception", message, str(e)).show()
        )

    def show_exception_data(self, title: str, message: str, details: str) -> None:
        self.after(0, lambda: ErrorDialog(self, title, message, details).show())

    def show_error(self, title: str, message: str, blocking: bool = False) -> None:
        if blocking:
            messagebox.showerror(title, message, parent=self)
        else:
            self.after(0, lambda: messagebox.showerror(title, message, parent=self))

    def on_closing(self) -> None:
        if self.toolbar.picker:
            self.toolbar.picker.destroy()
        self.menubar.prompt_save_running_session(True)

    def save_config(self) -> None:
        appconfig.save(self.guiconfig)

    def joined_session_update(self) -> None:
        if self.core.is_runtime():
            self.menubar.set_state(is_runtime=True)
            self.toolbar.set_runtime()
        else:
            self.menubar.set_state(is_runtime=False)
            self.toolbar.set_design()

    def get_enum_icon(self, image_enum: ImageEnum, *, width: int) -> PhotoImage:
        return images.from_enum(image_enum, width=width, scale=self.app_scale)

    def get_file_icon(self, file_path: str, *, width: int) -> PhotoImage:
        return images.from_file(file_path, width=width, scale=self.app_scale)

    def close(self) -> None:
        self.master.destroy()
