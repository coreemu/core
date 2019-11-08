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


def sub_menu_items():
    logging.debug("Click on sub menu items")


def file_new(event=None):
    logging.debug("Click file New")


def file_reload():
    logging.debug("Click file Reload")


def file_export_python_script():
    logging.debug("Click file export python script")


def file_execute_xml_or_python_script():
    logging.debug("Execute XML or Python script")


def file_execute_python_script_with_options():
    logging.debug("Click execute Python script with options")


def file_open_current_file_in_editor():
    logging.debug("Click file open current in editor")


def file_print():
    logging.debug("Click file Print")


def file_save_screenshot():
    logging.debug("Click file save screenshot")


def edit_undo(event=None):
    logging.debug("Click edit undo")


def edit_redo(event=None):
    logging.debug("Click edit redo")


def edit_cut(event=None):
    logging.debug("Click edit cut")


def edit_copy(event=None):
    logging.debug("Click edit copy")


def edit_paste(event=None):
    logging.debug("Click edit paste")


def edit_select_all(event=None):
    logging.debug("Click edit select all")


def edit_select_adjacent(event=None):
    logging.debug("Click edit select adjacent")


def edit_find(event=None):
    logging.debug("CLick edit find")


def edit_clear_marker():
    logging.debug("Click edit clear marker")


def edit_preferences():
    logging.debug("Click preferences")


def canvas_new():
    logging.debug("Click canvas new")


def canvas_manage():
    logging.debug("Click canvas manage")


def canvas_delete():
    logging.debug("Click canvas delete")


def canvas_previous(event=None):
    logging.debug("Click canvas previous")


def canvas_next(event=None):
    logging.debug("Click canvas next")


def canvas_first(event=None):
    logging.debug("CLick canvas first")


def canvas_last(event=None):
    logging.debug("CLick canvas last")


def view_show():
    logging.debug("Click view show")


def view_show_hidden_nodes():
    logging.debug("Click view show hidden nodes")


def view_locked():
    logging.debug("Click view locked")


def view_3d_gui():
    logging.debug("CLick view 3D GUI")


def view_zoom_in(event=None):
    logging.debug("Click view zoom in")


def view_zoom_out(event=None):
    logging.debug("Click view zoom out")


def tools_auto_rearrange_all():
    logging.debug("Click tools, auto rearrange all")


def tools_auto_rearrange_selected():
    logging.debug("CLick tools auto rearrange selected")


def tools_align_to_grid():
    logging.debug("Click tools align to grid")


def tools_traffic():
    logging.debug("Click tools traffic")


def tools_ip_addresses():
    logging.debug("Click tools ip addresses")


def tools_mac_addresses():
    logging.debug("Click tools mac addresses")


def tools_build_hosts_file():
    logging.debug("Click tools build hosts file")


def tools_renumber_nodes():
    logging.debug("Click tools renumber nodes")


def tools_experimental():
    logging.debug("Click tools experimental")


def tools_topology_generator():
    logging.debug("Click tools topology generator")


def tools_debugger():
    logging.debug("Click tools debugger")


def widgets_observer_widgets():
    logging.debug("Click widgets observer widgets")


def widgets_adjacency():
    logging.debug("Click widgets adjacency")


def widgets_throughput():
    logging.debug("Click widgets throughput")


def widgets_configure_adjacency():
    logging.debug("Click widgets configure adjacency")


def widgets_configure_throughput():
    logging.debug("Click widgets configure throughput")


def session_node_types():
    logging.debug("Click session node types")


def session_comments():
    logging.debug("Click session comments")


def session_reset_node_positions():
    logging.debug("Click session reset node positions")


def help_about():
    logging.debug("Click help About")


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

    def on_quit(self):
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
