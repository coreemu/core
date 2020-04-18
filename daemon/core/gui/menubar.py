import logging
import os
import tkinter as tk
from functools import partial
from typing import TYPE_CHECKING

import core.gui.menuaction as action
from core.gui.coreclient import OBSERVERS
from core.gui.dialogs.executepython import ExecutePythonDialog

if TYPE_CHECKING:
    from core.gui.app import Application


class Menubar(tk.Menu):
    """
    Core menubar
    """

    def __init__(self, master: tk.Tk, app: "Application", cnf={}, **kwargs):
        """
        Create a CoreMenubar instance
        """
        super().__init__(master, cnf, **kwargs)
        self.master.config(menu=self)
        self.app = app
        self.menuaction = action.MenuAction(app, master)
        self.recent_menu = None
        self.edit_menu = None
        self.draw()

    def draw(self):
        """
        Create core menubar and bind the hot keys to their matching command
        """
        self.draw_file_menu()
        self.draw_edit_menu()
        self.draw_canvas_menu()
        self.draw_view_menu()
        self.draw_tools_menu()
        self.draw_widgets_menu()
        self.draw_session_menu()
        self.draw_help_menu()

    def draw_file_menu(self):
        """
        Create file menu
        """
        menu = tk.Menu(self)
        menu.add_command(
            label="New Session",
            accelerator="Ctrl+N",
            command=self.menuaction.new_session,
        )
        self.app.bind_all("<Control-n>", lambda e: self.app.core.create_new_session())
        menu.add_command(label="Save", accelerator="Ctrl+S", command=self.save)
        self.app.bind_all("<Control-s>", self.save)
        menu.add_command(label="Save As...", command=self.menuaction.file_save_as_xml)
        menu.add_command(
            label="Open...", command=self.menuaction.file_open_xml, accelerator="Ctrl+O"
        )
        self.app.bind_all("<Control-o>", self.menuaction.file_open_xml)
        self.recent_menu = tk.Menu(menu)
        for i in self.app.guiconfig["recentfiles"]:
            self.recent_menu.add_command(
                label=i, command=partial(self.open_recent_files, i)
            )
        menu.add_cascade(label="Recent Files", menu=self.recent_menu)
        menu.add_separator()
        menu.add_command(label="Execute Python Script...", command=self.execute_python)
        menu.add_separator()
        menu.add_command(
            label="Quit", accelerator="Ctrl+Q", command=self.menuaction.on_quit
        )
        self.app.bind_all("<Control-q>", self.menuaction.on_quit)
        self.add_cascade(label="File", menu=menu)

    def draw_edit_menu(self):
        """
        Create edit menu
        """
        menu = tk.Menu(self)
        menu.add_command(label="Preferences", command=self.menuaction.gui_preferences)
        menu.add_command(label="Undo", accelerator="Ctrl+Z", state=tk.DISABLED)
        menu.add_command(label="Redo", accelerator="Ctrl+Y", state=tk.DISABLED)
        menu.add_separator()
        menu.add_command(label="Cut", accelerator="Ctrl+X", state=tk.DISABLED)
        menu.add_command(
            label="Copy", accelerator="Ctrl+C", command=self.menuaction.copy
        )
        menu.add_command(
            label="Paste", accelerator="Ctrl+V", command=self.menuaction.paste
        )
        menu.add_command(
            label="Delete", accelerator="Ctrl+D", command=self.menuaction.delete
        )
        self.add_cascade(label="Edit", menu=menu)

        self.app.master.bind_all("<Control-c>", self.menuaction.copy)
        self.app.master.bind_all("<Control-v>", self.menuaction.paste)
        self.app.master.bind_all("<Control-d>", self.menuaction.delete)
        self.edit_menu = menu

    def draw_canvas_menu(self):
        """
        Create canvas menu
        """
        menu = tk.Menu(self)
        menu.add_command(
            label="Size / Scale", command=self.menuaction.canvas_size_and_scale
        )
        menu.add_command(
            label="Wallpaper", command=self.menuaction.canvas_set_wallpaper
        )
        self.add_cascade(label="Canvas", menu=menu)

    def draw_view_menu(self):
        """
        Create view menu
        """
        menu = tk.Menu(self)
        menu.add_command(label="All", state=tk.DISABLED)
        menu.add_command(label="None", state=tk.DISABLED)
        menu.add_separator()
        menu.add_command(label="Interface Names", state=tk.DISABLED)
        menu.add_command(label="IPv4 Addresses", state=tk.DISABLED)
        menu.add_command(label="IPv6 Addresses", state=tk.DISABLED)
        menu.add_command(label="Node Labels", state=tk.DISABLED)
        menu.add_command(label="Annotations", state=tk.DISABLED)
        menu.add_command(label="Grid", state=tk.DISABLED)
        self.add_cascade(label="View", menu=menu)

    def draw_tools_menu(self):
        """
        Create tools menu
        """
        menu = tk.Menu(self)
        menu.add_command(label="Auto Grid", state=tk.DISABLED)
        menu.add_command(label="IP Addresses", state=tk.DISABLED)
        menu.add_command(label="MAC Addresses", state=tk.DISABLED)
        self.add_cascade(label="Tools", menu=menu)

    def create_observer_widgets_menu(self, widget_menu: tk.Menu):
        """
        Create observer widget menu item and create the sub menu items inside
        """
        var = tk.StringVar(value="none")
        menu = tk.Menu(widget_menu)
        menu.var = var
        menu.add_command(
            label="Edit Observers", command=self.menuaction.edit_observer_widgets
        )
        menu.add_separator()
        menu.add_radiobutton(
            label="None",
            variable=var,
            value="none",
            command=lambda: self.app.core.set_observer(None),
        )
        for name in sorted(OBSERVERS):
            cmd = OBSERVERS[name]
            menu.add_radiobutton(
                label=name,
                variable=var,
                value=name,
                command=partial(self.app.core.set_observer, cmd),
            )
        for name in sorted(self.app.core.custom_observers):
            observer = self.app.core.custom_observers[name]
            menu.add_radiobutton(
                label=name,
                variable=var,
                value=name,
                command=partial(self.app.core.set_observer, observer.cmd),
            )
        widget_menu.add_cascade(label="Observer Widgets", menu=menu)

    def create_adjacency_menu(self, widget_menu: tk.Menu):
        """
        Create adjacency menu item and the sub menu items inside
        """
        menu = tk.Menu(widget_menu)
        menu.add_command(label="Configure Adjacency", state=tk.DISABLED)
        menu.add_command(label="Enable OSPFv2?", state=tk.DISABLED)
        menu.add_command(label="Enable OSPFv3?", state=tk.DISABLED)
        menu.add_command(label="Enable OSLR?", state=tk.DISABLED)
        menu.add_command(label="Enable OSLRv2?", state=tk.DISABLED)
        widget_menu.add_cascade(label="Adjacency", menu=menu)

    def create_throughput_menu(self, widget_menu: tk.Menu):
        menu = tk.Menu(widget_menu)
        menu.add_command(
            label="Configure Throughput", command=self.menuaction.config_throughput
        )
        menu.add_checkbutton(
            label="Enable Throughput?", command=self.menuaction.throughput
        )
        widget_menu.add_cascade(label="Throughput", menu=menu)

    def draw_widgets_menu(self):
        """
        Create widget menu
        """
        menu = tk.Menu(self)
        self.create_observer_widgets_menu(menu)
        self.create_adjacency_menu(menu)
        self.create_throughput_menu(menu)
        self.add_cascade(label="Widgets", menu=menu)

    def draw_session_menu(self):
        """
        Create session menu
        """
        menu = tk.Menu(self)
        menu.add_command(
            label="Sessions", command=self.menuaction.session_change_sessions
        )
        menu.add_command(label="Servers", command=self.menuaction.session_servers)
        menu.add_command(label="Options", command=self.menuaction.session_options)
        menu.add_command(label="Hooks", command=self.menuaction.session_hooks)
        self.add_cascade(label="Session", menu=menu)

    def draw_help_menu(self):
        """
        Create help menu
        """
        menu = tk.Menu(self)
        menu.add_command(
            label="Core GitHub (www)", command=self.menuaction.help_core_github
        )
        menu.add_command(
            label="Core Documentation (www)",
            command=self.menuaction.help_core_documentation,
        )
        menu.add_command(label="About", command=self.menuaction.show_about)
        self.add_cascade(label="Help", menu=menu)

    def open_recent_files(self, filename: str):
        if os.path.isfile(filename):
            logging.debug("Open recent file %s", filename)
            self.menuaction.open_xml_task(filename)
        else:
            logging.warning("File does not exist %s", filename)

    def update_recent_files(self):
        self.recent_menu.delete(0, tk.END)
        for i in self.app.guiconfig["recentfiles"]:
            self.recent_menu.add_command(
                label=i, command=partial(self.open_recent_files, i)
            )

    def save(self, event=None):
        xml_file = self.app.core.xml_file
        if xml_file:
            self.app.core.save_xml(xml_file)
        else:
            self.menuaction.file_save_as_xml()

    def execute_python(self):
        dialog = ExecutePythonDialog(self.app, self.app)
        dialog.show()

    def change_menubar_item_state(self, is_runtime: bool):
        for i in range(self.edit_menu.index("end")):
            try:
                label_name = self.edit_menu.entrycget(i, "label")
                if label_name in ["Copy", "Paste"]:
                    if is_runtime:
                        self.edit_menu.entryconfig(i, state="disabled")
                    else:
                        self.edit_menu.entryconfig(i, state="normal")
            except tk.TclError:
                logging.debug("Ignore separators")
