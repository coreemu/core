"""
The actions taken when each menubar option is clicked
"""

import logging
import webbrowser
from tkinter import filedialog, messagebox

from core.api.grpc import core_pb2
from coretk.appdirs import XML_PATH
from coretk.dialogs.canvasbackground import CanvasBackgroundDialog
from coretk.dialogs.canvassizeandscale import SizeAndScaleDialog
from coretk.dialogs.hooks import HooksDialog
from coretk.dialogs.observerwidgets import ObserverWidgetsDialog
from coretk.dialogs.servers import ServersDialog
from coretk.dialogs.sessionoptions import SessionOptionsDialog
from coretk.dialogs.sessions import SessionsDialog


class MenuAction:
    """
    Actions performed when choosing menu items
    """

    def __init__(self, app, master):
        self.master = master
        self.app = app

    def prompt_save_running_session(self):
        """
        Prompt use to stop running session before application is closed

        :return: nothing
        """
        logging.info(
            "menuaction.py: clean_nodes_links_and_set_configuration() Exiting the program"
        )
        state = self.app.core.get_session_state()

        if (
            state == core_pb2.SessionState.SHUTDOWN
            or state == core_pb2.SessionState.DEFINITION
        ):
            self.app.core.delete_session()
        else:
            msgbox = messagebox.askyesnocancel("stop", "Stop the running session?")

            if msgbox or msgbox is False:
                if msgbox:
                    self.app.core.stop_session()
                    self.app.core.delete_session()

    def on_quit(self, event=None):
        """
        Prompt user whether so save running session, and then close the application

        :return: nothing
        """
        self.prompt_save_running_session()
        self.app.quit()

    def file_save_as_xml(self, event=None):
        logging.info("menuaction.py file_save_as_xml()")
        file_path = filedialog.asksaveasfilename(
            initialdir=str(XML_PATH),
            title="Save As",
            filetypes=(("EmulationScript XML files", "*.xml"), ("All files", "*")),
            defaultextension=".xml",
        )
        if file_path:
            self.app.core.save_xml(file_path)

    def file_open_xml(self, event=None):
        logging.info("menuaction.py file_open_xml()")
        self.app.is_open_xml = True
        file_path = filedialog.askopenfilename(
            initialdir=str(XML_PATH),
            title="Open",
            filetypes=(("EmulationScript XML File", "*.xml"), ("All Files", "*")),
        )
        if file_path:
            logging.info("opening xml: %s", file_path)
            self.prompt_save_running_session()
            self.app.core.open_xml(file_path)

    def canvas_size_and_scale(self):
        dialog = SizeAndScaleDialog(self.app, self.app)
        dialog.show()

    def canvas_set_wallpaper(self):
        dialog = CanvasBackgroundDialog(self.app, self.app)
        dialog.show()

    def help_core_github(self):
        webbrowser.open_new("https://github.com/coreemu/core")

    def help_core_documentation(self):
        webbrowser.open_new("http://coreemu.github.io/core/")

    def session_options(self):
        logging.debug("Click session options")
        dialog = SessionOptionsDialog(self.app, self.app)
        dialog.show()

    def session_change_sessions(self):
        logging.debug("Click session change sessions")
        dialog = SessionsDialog(self.app, self.app)
        dialog.show()

    def session_hooks(self):
        logging.debug("Click session hooks")
        dialog = HooksDialog(self.app, self.app)
        dialog.show()

    def session_servers(self):
        logging.debug("Click session emulation servers")
        dialog = ServersDialog(self.app, self.app)
        dialog.show()

    def edit_observer_widgets(self):
        dialog = ObserverWidgetsDialog(self.app, self.app)
        dialog.show()
