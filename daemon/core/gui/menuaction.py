"""
The actions taken when each menubar option is clicked
"""

import logging
import os
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING

import grpc

from core.gui.appconfig import XMLS_PATH
from core.gui.dialogs.about import AboutDialog
from core.gui.dialogs.canvassizeandscale import SizeAndScaleDialog
from core.gui.dialogs.canvaswallpaper import CanvasWallpaperDialog
from core.gui.dialogs.hooks import HooksDialog
from core.gui.dialogs.observers import ObserverDialog
from core.gui.dialogs.preferences import PreferencesDialog
from core.gui.dialogs.servers import ServersDialog
from core.gui.dialogs.sessionoptions import SessionOptionsDialog
from core.gui.dialogs.sessions import SessionsDialog
from core.gui.dialogs.throughput import ThroughputDialog
from core.gui.task import BackgroundTask

if TYPE_CHECKING:
    from core.gui.app import Application


class MenuAction:
    def __init__(self, app: "Application", master: tk.Tk):
        self.master = master
        self.app = app
        self.canvas = app.canvas

    def cleanup_old_session(self, session_id: int):
        try:
            res = self.app.core.client.get_session(session_id)
            logging.debug("retrieve session(%s), %s", session_id, res)
            stop_response = self.app.core.stop_session()
            logging.debug("stop session(%s), result: %s", session_id, stop_response)
            delete_response = self.app.core.delete_session(session_id)
            logging.debug(
                "deleted session(%s), result: %s", session_id, delete_response
            )
        except grpc.RpcError:
            logging.debug("session is not alive")

    def prompt_save_running_session(self, quitapp: bool = False):
        """
        Prompt use to stop running session before application is closed
        """
        result = True
        if self.app.core.is_runtime():
            result = messagebox.askyesnocancel("Exit", "Stop the running session?")

        if result:
            callback = None
            if quitapp:
                callback = self.app.quit
            task = BackgroundTask(
                self.app,
                self.cleanup_old_session,
                callback,
                (self.app.core.session_id,),
            )
            task.start()
        elif quitapp:
            self.app.quit()

    def on_quit(self, event: tk.Event = None):
        """
        Prompt user whether so save running session, and then close the application
        """
        self.prompt_save_running_session(quitapp=True)

    def file_save_as_xml(self, event: tk.Event = None):
        init_dir = self.app.core.xml_dir
        if not init_dir:
            init_dir = str(XMLS_PATH)
        file_path = filedialog.asksaveasfilename(
            initialdir=init_dir,
            title="Save As",
            filetypes=(("EmulationScript XML files", "*.xml"), ("All files", "*")),
            defaultextension=".xml",
        )
        if file_path:
            self.app.core.save_xml(file_path)

    def file_open_xml(self, event: tk.Event = None):
        init_dir = self.app.core.xml_dir
        if not init_dir:
            init_dir = str(XMLS_PATH)
        file_path = filedialog.askopenfilename(
            initialdir=init_dir,
            title="Open",
            filetypes=(("XML Files", "*.xml"), ("All Files", "*")),
        )
        self.open_xml_task(file_path)

    def open_xml_task(self, filename):
        if filename:
            self.app.core.xml_file = filename
            self.app.core.xml_dir = str(os.path.dirname(filename))
            self.prompt_save_running_session()
            self.app.statusbar.progress_bar.start(5)
            task = BackgroundTask(self.app, self.app.core.open_xml, args=(filename,))
            task.start()

    def gui_preferences(self):
        dialog = PreferencesDialog(self.app, self.app)
        dialog.show()

    def canvas_size_and_scale(self):
        dialog = SizeAndScaleDialog(self.app, self.app)
        dialog.show()

    def canvas_set_wallpaper(self):
        dialog = CanvasWallpaperDialog(self.app, self.app)
        dialog.show()

    def help_core_github(self):
        webbrowser.open_new("https://github.com/coreemu/core")

    def help_core_documentation(self):
        webbrowser.open_new("http://coreemu.github.io/core/")

    def session_options(self):
        logging.debug("Click options")
        dialog = SessionOptionsDialog(self.app, self.app)
        if not dialog.has_error:
            dialog.show()

    def session_change_sessions(self):
        logging.debug("Click change sessions")
        dialog = SessionsDialog(self.app, self.app)
        dialog.show()

    def session_hooks(self):
        logging.debug("Click hooks")
        dialog = HooksDialog(self.app, self.app)
        dialog.show()

    def session_servers(self):
        logging.debug("Click emulation servers")
        dialog = ServersDialog(self.app, self.app)
        dialog.show()

    def edit_observer_widgets(self):
        dialog = ObserverDialog(self.app, self.app)
        dialog.show()

    def show_about(self):
        dialog = AboutDialog(self.app, self.app)
        dialog.show()

    def throughput(self):
        if not self.app.core.handling_throughputs:
            self.app.core.enable_throughputs()
        else:
            self.app.core.cancel_throughputs()

    def copy(self, event: tk.Event = None):
        self.app.canvas.copy()

    def paste(self, event: tk.Event = None):
        self.app.canvas.paste()

    def config_throughput(self):
        dialog = ThroughputDialog(self.app, self.app)
        dialog.show()
