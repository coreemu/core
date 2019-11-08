import tkinter as tk

import coretk.menuaction as action


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
        file_menu = tk.Menu(self)
        file_menu.add_command(
            label="New Session",
            command=action.file_new,
            accelerator="Ctrl+N",
            underline=0,
        )
        self.app.bind_all("<Control-n>", action.file_new)
        file_menu.add_command(
            label="Open...",
            command=self.menuaction.file_open_xml,
            accelerator="Ctrl+O",
            underline=0,
        )
        self.app.bind_all("<Control-o>", self.menuaction.file_open_xml)
        file_menu.add_command(label="Reload", command=action.file_reload, underline=0)
        file_menu.add_command(
            label="Save", accelerator="Ctrl+S", command=self.menuaction.file_save_as_xml
        )
        self.app.bind_all("<Control-s>", self.menuaction.file_save_as_xml)
        file_menu.add_separator()
        file_menu.add_command(
            label="Export Python script...", command=action.file_export_python_script
        )
        file_menu.add_command(
            label="Execute XML or Python script...",
            command=action.file_execute_xml_or_python_script,
        )
        file_menu.add_command(
            label="Execute Python script with options...",
            command=action.file_execute_python_script_with_options,
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Open current file in editor...",
            command=action.file_open_current_file_in_editor,
        )
        file_menu.add_command(label="Print...", command=action.file_print, underline=0)
        file_menu.add_command(
            label="Save screenshot...", command=action.file_save_screenshot
        )
        file_menu.add_separator()
        file_menu.add_command(
            label="Quit", command=self.menuaction.on_quit, underline=0
        )
        self.add_cascade(label="File", menu=file_menu, underline=0)

    def draw_edit_menu(self):
        """
        Create edit menu

        :return: nothing
        """
        edit_menu = tk.Menu(self)
        edit_menu.add_command(
            label="Undo", command=action.edit_undo, accelerator="Ctrl+Z", underline=0
        )
        self.app.bind_all("<Control-z>", action.edit_undo)
        edit_menu.add_command(
            label="Redo", command=action.edit_redo, accelerator="Ctrl+Y", underline=0
        )
        self.app.bind_all("<Control-y>", action.edit_redo)
        edit_menu.add_separator()
        edit_menu.add_command(
            label="Cut", command=action.edit_cut, accelerator="Ctrl+X", underline=0
        )
        self.app.bind_all("<Control-x>", action.edit_cut)
        edit_menu.add_command(
            label="Copy", command=action.edit_copy, accelerator="Ctrl+C", underline=0
        )
        self.app.bind_all("<Control-c>", action.edit_copy)
        edit_menu.add_command(
            label="Paste", command=action.edit_paste, accelerator="Ctrl+V", underline=0
        )
        self.app.bind_all("<Control-v>", action.edit_paste)
        edit_menu.add_separator()
        edit_menu.add_command(
            label="Select all", command=action.edit_select_all, accelerator="Ctrl+A"
        )
        self.app.bind_all("<Control-a>", action.edit_select_all)
        edit_menu.add_command(
            label="Select Adjacent",
            command=action.edit_select_adjacent,
            accelerator="Ctrl+J",
        )
        self.app.bind_all("<Control-j>", action.edit_select_adjacent)
        edit_menu.add_separator()
        edit_menu.add_command(
            label="Find...", command=action.edit_find, accelerator="Ctrl+F", underline=0
        )
        self.app.bind_all("<Control-f>", action.edit_find)
        edit_menu.add_command(label="Clear marker", command=action.edit_clear_marker)
        edit_menu.add_command(label="Preferences...", command=action.edit_preferences)
        self.add_cascade(label="Edit", menu=edit_menu, underline=0)

    def draw_canvas_menu(self):
        """
        Create canvas menu

        :return: nothing
        """
        canvas_menu = tk.Menu(self)
        canvas_menu.add_command(label="New", command=action.canvas_new)
        canvas_menu.add_command(label="Manage...", command=action.canvas_manage)
        canvas_menu.add_command(label="Delete", command=action.canvas_delete)
        canvas_menu.add_separator()
        canvas_menu.add_command(
            label="Size/scale...", command=self.menuaction.canvas_size_and_scale
        )
        canvas_menu.add_command(
            label="Wallpaper...", command=self.menuaction.canvas_set_wallpaper
        )
        canvas_menu.add_separator()
        canvas_menu.add_command(
            label="Previous", command=action.canvas_previous, accelerator="PgUp"
        )
        self.app.bind_all("<Prior>", action.canvas_previous)
        canvas_menu.add_command(
            label="Next", command=action.canvas_next, accelerator="PgDown"
        )
        self.app.bind_all("<Next>", action.canvas_next)
        canvas_menu.add_command(
            label="First", command=action.canvas_first, accelerator="Home"
        )
        self.app.bind_all("<Home>", action.canvas_first)
        canvas_menu.add_command(
            label="Last", command=action.canvas_last, accelerator="End"
        )
        self.app.bind_all("<End>", action.canvas_last)
        self.add_cascade(label="Canvas", menu=canvas_menu, underline=0)

    def create_show_menu(self, view_menu):
        """
        Create the menu items in View/Show

        :param tkinter.Menu view_menu: the view menu
        :return: nothing
        """
        show_menu = tk.Menu(view_menu)
        show_menu.add_command(label="All", command=action.sub_menu_items)
        show_menu.add_command(label="None", command=action.sub_menu_items)
        show_menu.add_separator()
        show_menu.add_command(label="Interface Names", command=action.sub_menu_items)
        show_menu.add_command(label="IPv4 Addresses", command=action.sub_menu_items)
        show_menu.add_command(label="IPv6 Addresses", command=action.sub_menu_items)
        show_menu.add_command(label="Node Labels", command=action.sub_menu_items)
        show_menu.add_command(label="Annotations", command=action.sub_menu_items)
        show_menu.add_command(label="Grid", command=action.sub_menu_items)
        show_menu.add_command(label="API Messages", command=action.sub_menu_items)
        view_menu.add_cascade(label="Show", menu=show_menu)

    def draw_view_menu(self):
        """
        Create view menu

        :return: nothing
        """
        view_menu = tk.Menu(self)
        self.create_show_menu(view_menu)
        view_menu.add_command(
            label="Show hidden nodes", command=action.view_show_hidden_nodes
        )
        view_menu.add_command(label="Locked", command=action.view_locked)
        view_menu.add_command(label="3D GUI...", command=action.view_3d_gui)
        view_menu.add_separator()
        view_menu.add_command(
            label="Zoom in", command=action.view_zoom_in, accelerator="+"
        )
        self.app.bind_all("<Control-Shift-plus>", action.view_zoom_in)
        view_menu.add_command(
            label="Zoom out", command=action.view_zoom_out, accelerator="-"
        )
        self.app.bind_all("<Control-minus>", action.view_zoom_out)
        self.add_cascade(label="View", menu=view_menu, underline=0)

    def create_experimental_menu(self, tools_menu):
        """
        Create experimental menu item and the sub menu items inside

        :param tkinter.Menu tools_menu: tools menu
        :return: nothing
        """
        experimental_menu = tk.Menu(tools_menu)
        experimental_menu.add_command(
            label="Plugins...", command=action.sub_menu_items, underline=0
        )
        experimental_menu.add_command(
            label="ns2immunes converter...", command=action.sub_menu_items, underline=0
        )
        experimental_menu.add_command(
            label="Topology partitioning...", command=action.sub_menu_items
        )
        tools_menu.add_cascade(
            label="Experimental", menu=experimental_menu, underline=0
        )

    def create_random_menu(self, topology_generator_menu):
        """
        Create random menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        random_menu = tk.Menu(topology_generator_menu)
        # list of number of random nodes to create
        nums = [1, 5, 10, 15, 20, 30, 40, 50, 75, 100]
        for i in nums:
            the_label = "R(" + str(i) + ")"
            random_menu.add_command(label=the_label, command=action.sub_menu_items)
        topology_generator_menu.add_cascade(
            label="Random", menu=random_menu, underline=0
        )

    def create_grid_menu(self, topology_generator_menu):
        """
        Create grid menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology_generator_menu
        :return: nothing
        """
        grid_menu = tk.Menu(topology_generator_menu)
        # list of number of nodes to create
        nums = [1, 5, 10, 15, 20, 25, 30, 35, 40, 50, 60, 70, 80, 90, 100]
        for i in nums:
            the_label = "G(" + str(i) + ")"
            grid_menu.add_command(label=the_label, command=action.sub_menu_items)
        topology_generator_menu.add_cascade(label="Grid", menu=grid_menu, underline=0)

    def create_connected_grid_menu(self, topology_generator_menu):
        """
        Create connected grid menu items and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        grid_menu = tk.Menu(topology_generator_menu)
        for i in range(1, 11, 1):
            i_n_menu = tk.Menu(grid_menu)
            for j in range(1, 11, 1):
                i_j_label = str(i) + " X " + str(j)
                i_n_menu.add_command(label=i_j_label, command=action.sub_menu_items)
            i_n_label = str(i) + " X N"
            grid_menu.add_cascade(label=i_n_label, menu=i_n_menu)
        topology_generator_menu.add_cascade(
            label="Connected Grid", menu=grid_menu, underline=0
        )

    def create_chain_menu(self, topology_generator_menu):
        """
        Create chain menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        chain_menu = tk.Menu(topology_generator_menu)
        # number of nodes to create
        nums = list(range(2, 25, 1)) + [32, 64, 128]
        for i in nums:
            the_label = "P(" + str(i) + ")"
            chain_menu.add_command(label=the_label, command=action.sub_menu_items)
        topology_generator_menu.add_cascade(label="Chain", menu=chain_menu, underline=0)

    def create_star_menu(self, topology_generator_menu):
        """
        Create star menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        star_menu = tk.Menu(topology_generator_menu)
        for i in range(3, 26, 1):
            the_label = "C(" + str(i) + ")"
            star_menu.add_command(label=the_label, command=action.sub_menu_items)
        topology_generator_menu.add_cascade(label="Star", menu=star_menu, underline=0)

    def create_cycle_menu(self, topology_generator_menu):
        """
        Create cycle menu item and the sub items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        cycle_menu = tk.Menu(topology_generator_menu)
        for i in range(3, 25, 1):
            the_label = "C(" + str(i) + ")"
            cycle_menu.add_command(label=the_label, command=action.sub_menu_items)
        topology_generator_menu.add_cascade(label="Cycle", menu=cycle_menu, underline=0)

    def create_wheel_menu(self, topology_generator_menu):
        """
        Create wheel menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        wheel_menu = tk.Menu(topology_generator_menu)
        for i in range(4, 26, 1):
            the_label = "W(" + str(i) + ")"
            wheel_menu.add_command(label=the_label, command=action.sub_menu_items)
        topology_generator_menu.add_cascade(label="Wheel", menu=wheel_menu, underline=0)

    def create_cube_menu(self, topology_generator_menu):
        """
        Create cube menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        cube_menu = tk.Menu(topology_generator_menu)
        for i in range(2, 7, 1):
            the_label = "Q(" + str(i) + ")"
            cube_menu.add_command(label=the_label, command=action.sub_menu_items)
        topology_generator_menu.add_cascade(label="Cube", menu=cube_menu, underline=0)

    def create_clique_menu(self, topology_generator_menu):
        """
        Create clique menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        clique_menu = tk.Menu(topology_generator_menu)
        for i in range(3, 25, 1):
            the_label = "K(" + str(i) + ")"
            clique_menu.add_command(label=the_label, command=action.sub_menu_items)
        topology_generator_menu.add_cascade(
            label="Clique", menu=clique_menu, underline=0
        )

    def create_bipartite_menu(self, topology_generator_menu):
        """
        Create bipartite menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology_generator_menu
        :return: nothing
        """
        bipartite_menu = tk.Menu(topology_generator_menu)
        temp = 24
        for i in range(1, 13, 1):
            i_n_menu = tk.Menu(bipartite_menu)
            for j in range(i, temp, 1):
                i_j_label = "K(" + str(i) + " X " + str(j) + ")"
                i_n_menu.add_command(label=i_j_label, command=action.sub_menu_items)
            i_n_label = "K(" + str(i) + " X N)"
            bipartite_menu.add_cascade(label=i_n_label, menu=i_n_menu)
            temp = temp - 1
        topology_generator_menu.add_cascade(
            label="Bipartite", menu=bipartite_menu, underline=0
        )

    def create_topology_generator_menu(self, tools_menu):
        """
        Create topology menu item and its sub menu items

        :param tkinter.Menu tools_menu: tools menu

        :return: nothing
        """
        topology_generator_menu = tk.Menu(tools_menu)
        self.create_random_menu(topology_generator_menu)
        self.create_grid_menu(topology_generator_menu)
        self.create_connected_grid_menu(topology_generator_menu)
        self.create_chain_menu(topology_generator_menu)
        self.create_star_menu(topology_generator_menu)
        self.create_cycle_menu(topology_generator_menu)
        self.create_wheel_menu(topology_generator_menu)
        self.create_cube_menu(topology_generator_menu)
        self.create_clique_menu(topology_generator_menu)
        self.create_bipartite_menu(topology_generator_menu)
        tools_menu.add_cascade(
            label="Topology generator", menu=topology_generator_menu, underline=0
        )

    def draw_tools_menu(self):
        """
        Create tools menu

        :return: nothing
        """
        tools_menu = tk.Menu(self)
        tools_menu.add_command(
            label="Auto rearrange all",
            command=action.tools_auto_rearrange_all,
            underline=0,
        )
        tools_menu.add_command(
            label="Auto rearrange selected",
            command=action.tools_auto_rearrange_selected,
            underline=0,
        )
        tools_menu.add_separator()
        tools_menu.add_command(
            label="Align to grid", command=action.tools_align_to_grid, underline=0
        )
        tools_menu.add_separator()
        tools_menu.add_command(label="Traffic...", command=action.tools_traffic)
        tools_menu.add_command(
            label="IP addresses...", command=action.tools_ip_addresses, underline=0
        )
        tools_menu.add_command(
            label="MAC addresses...", command=action.tools_mac_addresses, underline=0
        )
        tools_menu.add_command(
            label="Build hosts file...",
            command=action.tools_build_hosts_file,
            underline=0,
        )
        tools_menu.add_command(
            label="Renumber nodes...", command=action.tools_renumber_nodes, underline=0
        )
        self.create_experimental_menu(tools_menu)
        self.create_topology_generator_menu(tools_menu)
        tools_menu.add_command(label="Debugger...", command=action.tools_debugger)
        self.add_cascade(label="Tools", menu=tools_menu, underline=0)

    def create_observer_widgets_menu(self, widget_menu):
        """
        Create observer widget menu item and create the sub menu items inside

        :param tkinter.Menu widget_menu: widget_menu
        :return: nothing
        """
        observer_widget_menu = tk.Menu(widget_menu)
        observer_widget_menu.add_command(label="None", command=action.sub_menu_items)
        observer_widget_menu.add_command(
            label="processes", command=action.sub_menu_items
        )
        observer_widget_menu.add_command(
            label="ifconfig", command=action.sub_menu_items
        )
        observer_widget_menu.add_command(
            label="IPv4 routes", command=action.sub_menu_items
        )
        observer_widget_menu.add_command(
            label="IPv6 routes", command=action.sub_menu_items
        )
        observer_widget_menu.add_command(
            label="OSPFv2 neighbors", command=action.sub_menu_items
        )
        observer_widget_menu.add_command(
            label="OSPFv3 neighbors", command=action.sub_menu_items
        )
        observer_widget_menu.add_command(
            label="Listening sockets", command=action.sub_menu_items
        )
        observer_widget_menu.add_command(
            label="IPv4 MFC entries", command=action.sub_menu_items
        )
        observer_widget_menu.add_command(
            label="IPv6 MFC entries", command=action.sub_menu_items
        )
        observer_widget_menu.add_command(
            label="firewall rules", command=action.sub_menu_items
        )
        observer_widget_menu.add_command(
            label="IPsec policies", command=action.sub_menu_items
        )
        observer_widget_menu.add_command(
            label="docker logs", command=action.sub_menu_items
        )
        observer_widget_menu.add_command(
            label="OSPFv3 MDR level", command=action.sub_menu_items
        )
        observer_widget_menu.add_command(
            label="PIM neighbors", command=action.sub_menu_items
        )
        observer_widget_menu.add_command(
            label="Edit...", command=self.menuaction.edit_observer_widgets
        )
        widget_menu.add_cascade(label="Observer Widgets", menu=observer_widget_menu)

    def create_adjacency_menu(self, widget_menu):
        """
        Create adjacency menu item and the sub menu items inside

        :param tkinter.Menu widget_menu: widget menu
        :return: nothing
        """
        adjacency_menu = tk.Menu(widget_menu)
        adjacency_menu.add_command(label="OSPFv2", command=action.sub_menu_items)
        adjacency_menu.add_command(label="OSPFv3", command=action.sub_menu_items)
        adjacency_menu.add_command(label="OSLR", command=action.sub_menu_items)
        adjacency_menu.add_command(label="OSLRv2", command=action.sub_menu_items)
        widget_menu.add_cascade(label="Adjacency", menu=adjacency_menu)

    def draw_widgets_menu(self):
        """
        Create widget menu

        :return: nothing
        """
        widget_menu = tk.Menu(self)
        self.create_observer_widgets_menu(widget_menu)
        self.create_adjacency_menu(widget_menu)
        widget_menu.add_command(label="Throughput", command=action.widgets_throughput)
        widget_menu.add_separator()
        widget_menu.add_command(
            label="Configure Adjacency...", command=action.widgets_configure_adjacency
        )
        widget_menu.add_command(
            label="Configure Throughput...", command=action.widgets_configure_throughput
        )
        self.add_cascade(label="Widgets", menu=widget_menu, underline=0)

    def draw_session_menu(self):
        """
        Create session menu

        :return: nothing
        """
        session_menu = tk.Menu(self)
        session_menu.add_command(
            label="Change sessions...",
            command=self.menuaction.session_change_sessions,
            underline=0,
        )
        session_menu.add_separator()
        session_menu.add_command(
            label="Node types...", command=action.session_node_types, underline=0
        )
        session_menu.add_command(
            label="Comments...", command=action.session_comments, underline=0
        )
        session_menu.add_command(
            label="Hooks...", command=self.menuaction.session_hooks, underline=0
        )
        session_menu.add_command(
            label="Reset node positions",
            command=action.session_reset_node_positions,
            underline=0,
        )
        session_menu.add_command(
            label="Emulation servers...",
            command=self.menuaction.session_servers,
            underline=0,
        )
        session_menu.add_command(
            label="Options...", command=self.menuaction.session_options, underline=0
        )
        self.add_cascade(label="Session", menu=session_menu, underline=0)

    def draw_help_menu(self):
        """
        Create help menu

        :return: nothing
        """
        help_menu = tk.Menu(self)
        help_menu.add_command(
            label="Core Github (www)", command=self.menuaction.help_core_github
        )
        help_menu.add_command(
            label="Core Documentation (www)",
            command=self.menuaction.help_core_documentation,
        )
        help_menu.add_command(label="About", command=action.help_about)
        self.add_cascade(label="Help", menu=help_menu)
