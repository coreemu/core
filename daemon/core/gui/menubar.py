import tkinter as tk
from functools import partial

import core.gui.menuaction as action
from core.gui.coreclient import OBSERVERS


class Menubar(tk.Menu):
    """
    Core menubar
    """

    def __init__(self, master, app, cnf={}, **kwargs):
        """
        Create a CoreMenubar instance

        :param master:
        :param tkinter.Menu menubar: menubar object
        :param coretk.app.Application app: application object
        """
        super().__init__(master, cnf, **kwargs)
        self.master.config(menu=self)
        self.app = app
        self.menuaction = action.MenuAction(app, master)
        self.draw()

    def draw(self):
        """
        Create core menubar and bind the hot keys to their matching command

        :return: nothing
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

        :return: nothing
        """
        menu = tk.Menu(self)
        menu.add_command(
            label="New Session",
            accelerator="Ctrl+N",
            command=self.app.core.create_new_session,
        )
        self.app.bind_all("<Control-n>", lambda e: self.app.core.create_new_session())
        menu.add_command(
            label="Open...", command=self.menuaction.file_open_xml, accelerator="Ctrl+O"
        )
        self.app.bind_all("<Control-o>", self.menuaction.file_open_xml)
        menu.add_command(
            label="Save", accelerator="Ctrl+S", command=self.menuaction.file_save_as_xml
        )
        menu.add_command(label="Reload", underline=0, state=tk.DISABLED)
        self.app.bind_all("<Control-s>", self.menuaction.file_save_as_xml)
        menu.add_separator()
        menu.add_command(label="Export Python script...", state=tk.DISABLED)
        menu.add_command(label="Execute XML or Python script...", state=tk.DISABLED)
        menu.add_command(
            label="Execute Python script with options...", state=tk.DISABLED
        )
        menu.add_separator()
        menu.add_command(label="Open current file in editor...", state=tk.DISABLED)
        menu.add_command(label="Print...", underline=0, state=tk.DISABLED)
        menu.add_command(label="Save screenshot...", state=tk.DISABLED)
        menu.add_separator()
        menu.add_command(
            label="Quit", accelerator="Ctrl+Q", command=self.menuaction.on_quit
        )
        self.app.bind_all("<Control-q>", self.menuaction.on_quit)
        self.add_cascade(label="File", menu=menu)

    def draw_edit_menu(self):
        """
        Create edit menu

        :return: nothing
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
        menu.add_separator()
        menu.add_command(label="Select all", accelerator="Ctrl+A", state=tk.DISABLED)
        menu.add_command(
            label="Select Adjacent", accelerator="Ctrl+J", state=tk.DISABLED
        )
        menu.add_separator()
        menu.add_command(label="Find...", accelerator="Ctrl+F", state=tk.DISABLED)
        menu.add_command(label="Clear marker", state=tk.DISABLED)
        self.add_cascade(label="Edit", menu=menu)

        self.app.master.bind_all("<Control-c>", self.menuaction.copy)
        self.app.master.bind_all("<Control-v>", self.menuaction.paste)

    def draw_canvas_menu(self):
        """
        Create canvas menu

        :return: nothing
        """
        menu = tk.Menu(self)
        menu.add_command(
            label="Size/scale...", command=self.menuaction.canvas_size_and_scale
        )
        menu.add_command(
            label="Wallpaper...", command=self.menuaction.canvas_set_wallpaper
        )
        menu.add_separator()
        menu.add_command(label="New", state=tk.DISABLED)
        menu.add_command(label="Manage...", state=tk.DISABLED)
        menu.add_command(label="Delete", state=tk.DISABLED)
        menu.add_separator()
        menu.add_command(label="Previous", accelerator="PgUp", state=tk.DISABLED)
        menu.add_command(label="Next", accelerator="PgDown", state=tk.DISABLED)
        menu.add_command(label="First", accelerator="Home", state=tk.DISABLED)
        menu.add_command(label="Last", accelerator="End", state=tk.DISABLED)
        self.add_cascade(label="Canvas", menu=menu)

    def draw_view_menu(self):
        """
        Create view menu

        :return: nothing
        """
        view_menu = tk.Menu(self)
        self.create_show_menu(view_menu)
        view_menu.add_command(label="Show hidden nodes", state=tk.DISABLED)
        view_menu.add_command(label="Locked", state=tk.DISABLED)
        view_menu.add_command(label="3D GUI...", state=tk.DISABLED)
        view_menu.add_separator()
        view_menu.add_command(label="Zoom in", accelerator="+", state=tk.DISABLED)
        view_menu.add_command(label="Zoom out", accelerator="-", state=tk.DISABLED)
        self.add_cascade(label="View", menu=view_menu)

    def create_show_menu(self, view_menu):
        """
        Create the menu items in View/Show

        :param tkinter.Menu view_menu: the view menu
        :return: nothing
        """
        menu = tk.Menu(view_menu)
        menu.add_command(label="All", state=tk.DISABLED)
        menu.add_command(label="None", state=tk.DISABLED)
        menu.add_separator()
        menu.add_command(label="Interface Names", state=tk.DISABLED)
        menu.add_command(label="IPv4 Addresses", state=tk.DISABLED)
        menu.add_command(label="IPv6 Addresses", state=tk.DISABLED)
        menu.add_command(label="Node Labels", state=tk.DISABLED)
        menu.add_command(label="Annotations", state=tk.DISABLED)
        menu.add_command(label="Grid", state=tk.DISABLED)
        menu.add_command(label="API Messages", state=tk.DISABLED)
        view_menu.add_cascade(label="Show", menu=menu)

    def create_experimental_menu(self, tools_menu):
        """
        Create experimental menu item and the sub menu items inside

        :param tkinter.Menu tools_menu: tools menu
        :return: nothing
        """
        menu = tk.Menu(tools_menu)
        menu.add_command(label="Plugins...", state=tk.DISABLED)
        menu.add_command(label="ns2immunes converter...", state=tk.DISABLED)
        menu.add_command(label="Topology partitioning...", state=tk.DISABLED)
        tools_menu.add_cascade(label="Experimental", menu=menu)

    def create_random_menu(self, topology_generator_menu):
        """
        Create random menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        menu = tk.Menu(topology_generator_menu)
        # list of number of random nodes to create
        nums = [1, 5, 10, 15, 20, 30, 40, 50, 75, 100]
        for i in nums:
            label = f"R({i})"
            menu.add_command(label=label, state=tk.DISABLED)
        topology_generator_menu.add_cascade(label="Random", menu=menu)

    def create_grid_menu(self, topology_generator_menu):
        """
        Create grid menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology_generator_menu
        :return: nothing
        """
        menu = tk.Menu(topology_generator_menu)
        # list of number of nodes to create
        nums = [1, 5, 10, 15, 20, 25, 30, 35, 40, 50, 60, 70, 80, 90, 100]
        for i in nums:
            label = f"G({i})"
            menu.add_command(label=label, state=tk.DISABLED)
        topology_generator_menu.add_cascade(label="Grid", menu=menu)

    def create_connected_grid_menu(self, topology_generator_menu):
        """
        Create connected grid menu items and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        menu = tk.Menu(topology_generator_menu)
        for i in range(1, 11, 1):
            submenu = tk.Menu(menu)
            for j in range(1, 11, 1):
                label = f"{i} X {j}"
                submenu.add_command(label=label, state=tk.DISABLED)
            label = str(i) + " X N"
            menu.add_cascade(label=label, menu=submenu)
        topology_generator_menu.add_cascade(label="Connected Grid", menu=menu)

    def create_chain_menu(self, topology_generator_menu):
        """
        Create chain menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        menu = tk.Menu(topology_generator_menu)
        # number of nodes to create
        nums = list(range(2, 25, 1)) + [32, 64, 128]
        for i in nums:
            label = f"P({i})"
            menu.add_command(label=label, state=tk.DISABLED)
        topology_generator_menu.add_cascade(label="Chain", menu=menu)

    def create_star_menu(self, topology_generator_menu):
        """
        Create star menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        menu = tk.Menu(topology_generator_menu)
        for i in range(3, 26, 1):
            label = f"C({i})"
            menu.add_command(label=label, state=tk.DISABLED)
        topology_generator_menu.add_cascade(label="Star", menu=menu)

    def create_cycle_menu(self, topology_generator_menu):
        """
        Create cycle menu item and the sub items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        menu = tk.Menu(topology_generator_menu)
        for i in range(3, 25, 1):
            label = f"C({i})"
            menu.add_command(label=label, state=tk.DISABLED)
        topology_generator_menu.add_cascade(label="Cycle", menu=menu)

    def create_wheel_menu(self, topology_generator_menu):
        """
        Create wheel menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        menu = tk.Menu(topology_generator_menu)
        for i in range(4, 26, 1):
            label = f"W({i})"
            menu.add_command(label=label, state=tk.DISABLED)
        topology_generator_menu.add_cascade(label="Wheel", menu=menu)

    def create_cube_menu(self, topology_generator_menu):
        """
        Create cube menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        menu = tk.Menu(topology_generator_menu)
        for i in range(2, 7, 1):
            label = f"Q({i})"
            menu.add_command(label=label, state=tk.DISABLED)
        topology_generator_menu.add_cascade(label="Cube", menu=menu)

    def create_clique_menu(self, topology_generator_menu):
        """
        Create clique menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        menu = tk.Menu(topology_generator_menu)
        for i in range(3, 25, 1):
            label = f"K({i})"
            menu.add_command(label=label, state=tk.DISABLED)
        topology_generator_menu.add_cascade(label="Clique", menu=menu)

    def create_bipartite_menu(self, topology_generator_menu):
        """
        Create bipartite menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology_generator_menu
        :return: nothing
        """
        menu = tk.Menu(topology_generator_menu)
        temp = 24
        for i in range(1, 13, 1):
            submenu = tk.Menu(menu)
            for j in range(i, temp, 1):
                label = f"K({i} X {j})"
                submenu.add_command(label=label, state=tk.DISABLED)
            label = f"K({i})"
            menu.add_cascade(label=label, menu=submenu)
            temp = temp - 1
        topology_generator_menu.add_cascade(label="Bipartite", menu=menu)

    def create_topology_generator_menu(self, tools_menu):
        """
        Create topology menu item and its sub menu items

        :param tkinter.Menu tools_menu: tools menu

        :return: nothing
        """
        menu = tk.Menu(tools_menu)
        self.create_random_menu(menu)
        self.create_grid_menu(menu)
        self.create_connected_grid_menu(menu)
        self.create_chain_menu(menu)
        self.create_star_menu(menu)
        self.create_cycle_menu(menu)
        self.create_wheel_menu(menu)
        self.create_cube_menu(menu)
        self.create_clique_menu(menu)
        self.create_bipartite_menu(menu)
        tools_menu.add_cascade(label="Topology generator", menu=menu)

    def draw_tools_menu(self):
        """
        Create tools menu

        :return: nothing
        """
        menu = tk.Menu(self)
        menu.add_command(label="Auto rearrange all", state=tk.DISABLED)
        menu.add_command(label="Auto rearrange selected", state=tk.DISABLED)
        menu.add_separator()
        menu.add_command(label="Align to grid", state=tk.DISABLED)
        menu.add_separator()
        menu.add_command(label="Traffic...", state=tk.DISABLED)
        menu.add_command(label="IP addresses...", state=tk.DISABLED)
        menu.add_command(label="MAC addresses...", state=tk.DISABLED)
        menu.add_command(label="Build hosts file...", state=tk.DISABLED)
        menu.add_command(label="Renumber nodes...", state=tk.DISABLED)
        self.create_experimental_menu(menu)
        self.create_topology_generator_menu(menu)
        menu.add_command(label="Debugger...", state=tk.DISABLED)
        self.add_cascade(label="Tools", menu=menu)

    def create_observer_widgets_menu(self, widget_menu):
        """
        Create observer widget menu item and create the sub menu items inside

        :param tkinter.Menu widget_menu: widget_menu
        :return: nothing
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

    def create_adjacency_menu(self, widget_menu):
        """
        Create adjacency menu item and the sub menu items inside

        :param tkinter.Menu widget_menu: widget menu
        :return: nothing
        """
        menu = tk.Menu(widget_menu)
        menu.add_command(label="OSPFv2", state=tk.DISABLED)
        menu.add_command(label="OSPFv3", state=tk.DISABLED)
        menu.add_command(label="OSLR", state=tk.DISABLED)
        menu.add_command(label="OSLRv2", state=tk.DISABLED)
        widget_menu.add_cascade(label="Adjacency", menu=menu)

    def draw_widgets_menu(self):
        """
        Create widget menu

        :return: nothing
        """
        menu = tk.Menu(self)
        self.create_observer_widgets_menu(menu)
        self.create_adjacency_menu(menu)
        menu.add_checkbutton(label="Throughput", command=self.menuaction.throughput)
        menu.add_separator()
        menu.add_command(label="Configure Adjacency...", state=tk.DISABLED)
        menu.add_command(
            label="Configure Throughput...", command=self.menuaction.config_throughput
        )
        self.add_cascade(label="Widgets", menu=menu)

    def draw_session_menu(self):
        """
        Create session menu

        :return: nothing
        """
        menu = tk.Menu(self)
        menu.add_command(
            label="Sessions...", command=self.menuaction.session_change_sessions
        )
        menu.add_separator()
        menu.add_command(label="Options...", command=self.menuaction.session_options)
        menu.add_command(label="Servers...", command=self.menuaction.session_servers)
        menu.add_command(label="Hooks...", command=self.menuaction.session_hooks)
        menu.add_command(label="Reset Nodes", state=tk.DISABLED)
        menu.add_command(label="Comments...", state=tk.DISABLED)
        self.add_cascade(label="Session", menu=menu)

    def draw_help_menu(self):
        """
        Create help menu

        :return: nothing
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
