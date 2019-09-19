import logging
import tkinter as tk

import coretk.menuaction as action
from coretk.graph import CanvasGraph
from coretk.images import Images


class Application(tk.Frame):
    def __init__(self, master=None):
        super().__init__(master)
        self.load_images()
        self.setup_app()
        self.menubar = None
        self.create_menu()
        self.create_widgets()

    def load_images(self):
        Images.load("switch", "switch.png")
        Images.load("core", "core-icon.png")

    def setup_app(self):
        self.master.title("CORE")
        self.master.geometry("800x600")
        image = Images.get("core")
        self.master.tk.call("wm", "iconphoto", self.master._w, image)
        self.pack(fill=tk.BOTH, expand=True)

    def create_file_menu(self):
        """
        Create file menu

        :return: nothing
        """
        file_menu = tk.Menu(self.master)
        file_menu.add_command(
            label="New", command=action.file_new, accelerator="Ctrl+N"
        )
        file_menu.add_command(
            label="Open...", command=action.file_open, accelerator="Ctrl+O"
        )
        file_menu.add_command(label="Reload", command=action.file_reload)
        file_menu.add_command(
            label="Save", command=action.file_save, accelerator="Ctrl+S"
        )
        file_menu.add_command(label="Save As XML...", command=action.file_save_as_xml)
        file_menu.add_command(label="Save As imn...", command=action.file_save_as_imn)

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
        file_menu.add_command(label="Print...", command=action.file_print)
        file_menu.add_command(
            label="Save screenshot...", command=action.file_save_screenshot
        )

        file_menu.add_separator()

        file_menu.add_command(
            label="/home/ncs/.core/configs/sample1.imn",
            command=action.file_example_link,
        )

        file_menu.add_separator()

        file_menu.add_command(label="Quit", command=self.master.quit)
        self.menubar.add_cascade(label="File", menu=file_menu)

    def create_edit_menu(self):
        """
        Create edit menu

        :return: nothing
        """
        edit_menu = tk.Menu(self.master)
        edit_menu.add_command(
            label="Undo", command=action.edit_undo, accelerator="Ctrl+Z"
        )
        edit_menu.add_command(
            label="Redo", command=action.edit_redo, accelerator="Ctrl+Y"
        )

        edit_menu.add_separator()

        edit_menu.add_command(
            label="Cut", command=action.edit_cut, accelerator="Ctrl+X"
        )
        edit_menu.add_command(
            label="Copy", command=action.edit_copy, accelerator="Ctrl+C"
        )
        edit_menu.add_command(
            label="Paste", command=action.edit_paste, accelerator="Ctrl+V"
        )

        edit_menu.add_separator()

        edit_menu.add_command(
            label="Select all", command=action.edit_select_all, accelerator="Ctrl+A"
        )
        edit_menu.add_command(
            label="Select Adjacent",
            command=action.edit_select_adjacent,
            accelerator="Ctrl+J",
        )

        edit_menu.add_separator()

        edit_menu.add_command(
            label="Find...", command=action.edit_find, accelerator="Ctrl+F"
        )
        edit_menu.add_command(label="Clear marker", command=action.edit_clear_marker)
        edit_menu.add_command(label="Preferences...", command=action.edit_preferences)

        self.menubar.add_cascade(label="Edit", menu=edit_menu)

    def create_canvas_menu(self):
        """
        Create canvas menu

        :return: nothing
        """
        canvas_menu = tk.Menu(self.master)
        canvas_menu.add_command(label="New", command=action.canvas_new)
        canvas_menu.add_command(label="Manage...", command=action.canvas_manage)
        canvas_menu.add_command(label="Delete", command=action.canvas_delete)

        canvas_menu.add_separator()

        canvas_menu.add_command(label="Size/scale...", command=action.canvas_size_scale)
        canvas_menu.add_command(label="Wallpaper...", command=action.canvas_wallpaper)

        canvas_menu.add_separator()

        canvas_menu.add_command(
            label="Previous", command=action.canvas_previous, accelerator="PgUp"
        )
        canvas_menu.add_command(
            label="Next", command=action.canvas_next, accelerator="PgDown"
        )
        canvas_menu.add_command(
            label="First", command=action.canvas_first, accelerator="Home"
        )
        canvas_menu.add_command(
            label="Last", command=action.canvas_last, accelerator="End"
        )

        self.menubar.add_cascade(label="Canvas", menu=canvas_menu)

    def create_show_menu(self, view_menu):
        """
        Create the menu items in View/Show

        :param tkinter.Menu view_menu: the view menu
        :return: nothing
        """
        show_menu = tk.Menu(self.master)
        show_menu.add_command(label="All")
        show_menu.add_command(label="None")
        show_menu.add_separator()
        show_menu.add_command(label="Interface Names")
        show_menu.add_command(label="IPv4 Addresses")
        show_menu.add_command(label="IPv6 Addresses")
        show_menu.add_command(label="Node Labels")
        show_menu.add_command(label="Annotations")
        show_menu.add_command(label="Grid")
        show_menu.add_command(label="API Messages")

        view_menu.add_cascade(label="Show", menu=show_menu)

    def create_view_menu(self):
        """
        Create view menu

        :return: nothing
        """
        view_menu = tk.Menu(self.master)
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
        view_menu.add_command(
            label="Zoom out", command=action.view_zoom_out, accelerator="-"
        )

        self.menubar.add_cascade(label="View", menu=view_menu)

    def create_experimental_menu(self, tools_menu):
        experimental_menu = tk.Menu(self.master)
        experimental_menu.add_command(label="Plugins...")
        experimental_menu.add_command(label="ns2immunes converter...")
        experimental_menu.add_command(label="Topology partitioning...")

        tools_menu.add_cascade(label="Experimental", menu=experimental_menu)

    def create_random_menu(self, topology_generator_menu):
        """
        Create random menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        random_menu = tk.Menu(self.master)
        random_menu.add_command(label="R(1)")
        random_menu.add_command(label="R(5)")
        random_menu.add_command(label="R(10)")
        random_menu.add_command(label="R(15)")
        random_menu.add_command(label="R(20)")
        random_menu.add_command(label="R(30)")
        random_menu.add_command(label="R(40)")
        random_menu.add_command(label="R(50)")
        random_menu.add_command(label="R(75)")
        random_menu.add_command(label="R(100)")

        topology_generator_menu.add_cascade(label="Random", menu=random_menu)

    def create_grid_menu(self, topology_generator_menu):
        """
        Create grid menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology_generator_menu
        :return: nothing
        """
        grid_menu = tk.Menu(self.master)
        grid_menu.add_command(label="G(1)")
        grid_menu.add_command(label="G(5)")
        grid_menu.add_command(label="G(10)")
        grid_menu.add_command(label="G(15)")
        grid_menu.add_command(label="G(20)")
        grid_menu.add_command(label="G(25)")
        grid_menu.add_command(label="G(30)")
        grid_menu.add_command(label="G(35)")
        grid_menu.add_command(label="G(40)")
        grid_menu.add_command(label="G(50)")
        grid_menu.add_command(label="G(60)")
        grid_menu.add_command(label="G(70)")
        grid_menu.add_command(label="G(80)")
        grid_menu.add_command(label="G(90)")
        grid_menu.add_command(label="G(100)")

        topology_generator_menu.add_cascade(label="Grid", menu=grid_menu)

    # TODO do later
    def create_connected_grid_menu(self, topology_generator_menu):
        """
        Create connected grid menu items and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        return

    def create_chain_menu(self, topology_generator_menu):
        """
        Create chain menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        chain_menu = tk.Menu(self.master)
        chain_menu.add_command(label="P(2)")
        chain_menu.add_command(label="P(3)")
        chain_menu.add_command(label="P(4)")
        chain_menu.add_command(label="P(5)")
        chain_menu.add_command(label="P(6)")
        chain_menu.add_command(label="P(7)")
        chain_menu.add_command(label="P(8)")
        chain_menu.add_command(label="P(9)")
        chain_menu.add_command(label="P(10)")
        chain_menu.add_command(label="P(11)")
        chain_menu.add_command(label="P(12)")
        chain_menu.add_command(label="P(13)")
        chain_menu.add_command(label="P(14)")
        chain_menu.add_command(label="P(15)")
        chain_menu.add_command(label="P(16)")
        chain_menu.add_command(label="P(17)")
        chain_menu.add_command(label="P(18)")
        chain_menu.add_command(label="P(19)")
        chain_menu.add_command(label="P(20)")
        chain_menu.add_command(label="P(21)")
        chain_menu.add_command(label="P(22)")
        chain_menu.add_command(label="P(23)")
        chain_menu.add_command(label="P(24)")
        chain_menu.add_command(label="P(32)")
        chain_menu.add_command(label="P(64)")
        chain_menu.add_command(label="P(128)")
        topology_generator_menu.add_cascade(label="Chain", menu=chain_menu)

    def create_star_menu(self, topology_generator_menu):
        """
        Create star menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        star_menu = tk.Menu(self.master)
        for i in range(3, 26, 1):
            the_label = "C(" + str(i) + ")"
            star_menu.add_command(label=the_label)

        topology_generator_menu.add_cascade(label="Star", menu=star_menu)

    def create_cycle_menu(self, topology_generator_menu):
        """
        Create cycle menu item and the sub items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        cycle_menu = tk.Menu(self.master)
        for i in range(3, 25, 1):
            the_label = "C(" + str(i) + ")"
            cycle_menu.add_command(label=the_label)

        topology_generator_menu.add_cascade(label="Cycle", menu=cycle_menu)

    def create_wheel_menu(self, topology_generator_menu):
        """
        Create wheel menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        wheel_menu = tk.Menu(self.master)
        for i in range(4, 26, 1):
            the_label = "W(" + str(i) + ")"
            wheel_menu.add_command(label=the_label)

        topology_generator_menu.add_cascade(label="Wheel", menu=wheel_menu)

    def create_cube_menu(self, topology_generator_menu):
        """
        Create cube menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        cube_menu = tk.Menu(self.master)
        for i in range(2, 7, 1):
            the_label = "Q(" + str(i) + ")"
            cube_menu.add_command(label=the_label)

        topology_generator_menu.add_cascade(label="Cube", menu=cube_menu)

    def create_clique_menu(self, topology_generator_menu):
        """
        Create clique menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology generator menu
        :return: nothing
        """
        clique_menu = tk.Menu(self.master)
        for i in range(3, 25, 1):
            the_label = "K(" + str(i) + ")"
            clique_menu.add_command(label=the_label)

        topology_generator_menu.add_cascade(label="Clique", menu=clique_menu)

    # TODO do later
    def create_bipartite_menu(self, topology_generator_menu):
        """
        Create bipartite menu item and the sub menu items inside

        :param tkinter.Menu topology_generator_menu: topology_generator_menu
        :return: nothing
        """
        # bipartite_menu = tk.Menu(self.master)
        return

    def create_topology_generator_menu(self, tools_menu):
        """
        Create topology menu item and its sub menu items

        :param tkinter.Menu tools_menu: tools menu

        :return: nothing
        """
        topology_generator_menu = tk.Menu(self.master)
        # topology_generator_menu.add_command(label="Random")
        self.create_random_menu(topology_generator_menu)
        # topology_generator_menu.add_command(label="Grid")
        self.create_grid_menu(topology_generator_menu)
        topology_generator_menu.add_command(label="Connected Grid")
        self.create_chain_menu(topology_generator_menu)
        # topology_generator_menu.add_command(label="Chain")
        # topology_generator_menu.add_command(label="Star")
        self.create_star_menu(topology_generator_menu)
        # topology_generator_menu.add_command(label="Cycle")
        self.create_cycle_menu(topology_generator_menu)
        # topology_generator_menu.add_command(label="Wheel")
        self.create_wheel_menu(topology_generator_menu)
        # topology_generator_menu.add_command(label="Cube")
        self.create_cube_menu(topology_generator_menu)
        # topology_generator_menu.add_command(label="Clique")
        self.create_clique_menu(topology_generator_menu)
        topology_generator_menu.add_command(label="Bipartite")

        tools_menu.add_cascade(label="Topology generator", menu=topology_generator_menu)

    def create_tools_menu(self):
        """
        Create tools menu

        :return: nothing
        """

        tools_menu = tk.Menu(self.master)
        tools_menu.add_command(
            label="Auto rearrange all", command=action.tools_auto_rearrange_all
        )
        tools_menu.add_command(
            label="Auto rearrange selected",
            command=action.tools_auto_rearrange_selected,
        )
        tools_menu.add_separator()

        tools_menu.add_command(
            label="Align to grid", command=action.tools_align_to_grid
        )

        tools_menu.add_separator()

        tools_menu.add_command(label="Traffic...", command=action.tools_traffic)
        tools_menu.add_command(
            label="IP addresses...", command=action.tools_ip_addresses
        )
        tools_menu.add_command(
            label="MAC addresses...", command=action.tools_mac_addresses
        )
        tools_menu.add_command(
            label="Build hosts file...", command=action.tools_build_hosts_file
        )
        tools_menu.add_command(
            label="Renumber nodes...", command=action.tools_renumber_nodes
        )
        self.create_experimental_menu(tools_menu)
        self.create_topology_generator_menu(tools_menu)
        tools_menu.add_command(label="Debugger...", command=action.tools_debugger)

        self.menubar.add_cascade(label="Tools", menu=tools_menu)

    def create_observer_widgets_menu(self, widget_menu):
        """
        Create observer widget menu item and create the sub menu items inside

        :param tkinter.Menu widget_menu: widget_menu
        :return: nothing
        """
        observer_widget_menu = tk.Menu(self.master)
        observer_widget_menu.add_command(label="None")
        observer_widget_menu.add_command(label="processes")
        observer_widget_menu.add_command(label="ifconfig")
        observer_widget_menu.add_command(label="IPv4 routes")
        observer_widget_menu.add_command(label="IPv6 routes")
        observer_widget_menu.add_command(label="OSPFv2 neighbors")
        observer_widget_menu.add_command(label="OSPFv3 neighbors")
        observer_widget_menu.add_command(label="Listening sockets")
        observer_widget_menu.add_command(label="IPv4 MFC entries")
        observer_widget_menu.add_command(label="IPv6 MFC entries")
        observer_widget_menu.add_command(label="firewall rules")
        observer_widget_menu.add_command(label="IPsec policies")
        observer_widget_menu.add_command(label="docker logs")
        observer_widget_menu.add_command(label="OSPFv3 MDR level")
        observer_widget_menu.add_command(label="PIM neighbors")
        observer_widget_menu.add_command(label="Edit...")

        widget_menu.add_cascade(label="Observer Widgets", menu=observer_widget_menu)

    def create_adjacency_menu(self, widget_menu):
        """
        Create adjacency menu item and the sub menu items inside

        :param tkinter.Menu widget_menu: widget menu
        :return: nothing
        """
        adjacency_menu = tk.Menu(self.master)
        adjacency_menu.add_command(label="OSPFv2")
        adjacency_menu.add_command(label="OSPFv3")
        adjacency_menu.add_command(label="OSLR")
        adjacency_menu.add_command(label="OSLRv2")

        widget_menu.add_cascade(label="Adjacency", menu=adjacency_menu)

    def create_widgets_menu(self):
        """
        Create widget menu

        :return: nothing
        """
        widget_menu = tk.Menu(self.master)
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

        self.menubar.add_cascade(label="Widgets", menu=widget_menu)

    def create_session_menu(self):
        """
        Create session menu

        :return: nothing
        """
        session_menu = tk.Menu(self.master)
        session_menu.add_command(label="Start", command=action.session_start)
        session_menu.add_command(
            label="Change sessions...", command=action.session_change_sessions
        )

        session_menu.add_separator()

        session_menu.add_command(
            label="Node types...", command=action.session_node_types
        )
        session_menu.add_command(label="Comments...", command=action.session_comments)
        session_menu.add_command(label="Hooks...", command=action.session_hooks)
        session_menu.add_command(
            label="Reset node positions", command=action.session_reset_node_positions
        )
        session_menu.add_command(
            label="Emulation servers...", command=action.session_emulation_servers
        )
        session_menu.add_command(label="Options...", command=action.session_options)

        self.menubar.add_cascade(label="Session", menu=session_menu)

    def create_help_menu(self):
        """
        Create help menu

        :return: nothing
        """
        help_menu = tk.Menu(self.master)
        help_menu.add_command(
            label="Core Github (www)", command=action.help_core_github
        )
        help_menu.add_command(
            label="Core Documentation (www)", command=action.help_core_documentation
        )
        help_menu.add_command(label="About", command=action.help_about)

        self.menubar.add_cascade(label="Help", menu=help_menu)

    def bind_menubar_shortcut(self):
        self.bind_all("<Control-n>", action.file_new_shortcut)
        self.bind_all("<Control-o>", action.file_open_shortcut)
        self.bind_all("<Control-s>", action.file_save_shortcut)
        self.bind_all("<Control-z>", action.edit_undo_shortcut)
        self.bind_all("<Control-y>", action.edit_redo_shortcut)
        self.bind_all("<Control-x>", action.edit_cut_shortcut)
        self.bind_all("<Control-c>", action.edit_copy_shortcut)
        self.bind_all("<Control-v>", action.edit_paste_shortcut)
        self.bind_all("<Control-a>", action.edit_select_all_shortcut)
        self.bind_all("<Control-j>", action.edit_select_adjacent_shortcut)
        self.bind_all("<Control-f>", action.edit_find_shortcut)
        self.bind_all("<Prior>", action.canvas_previous_shortcut)
        self.bind_all("<Next>", action.canvas_next_shortcut)
        self.bind_all("<Home>", action.canvas_first_shortcut)
        self.bind_all("<End>", action.canvas_last_shortcut)
        self.bind_all("<Control-Shift-plus>", action.view_zoom_in_shortcut)
        self.bind_all("<Control-minus>", action.view_zoom_out_shortcut)

    def create_menu(self):
        self.master.option_add("*tearOff", tk.FALSE)
        self.menubar = tk.Menu(self.master)
        self.create_file_menu()
        self.create_edit_menu()
        self.create_canvas_menu()
        self.create_view_menu()
        self.create_tools_menu()
        self.create_widgets_menu()
        self.create_session_menu()
        self.create_help_menu()

        self.master.config(menu=self.menubar)
        self.bind_menubar_shortcut()

    def create_widgets(self):
        image = Images.get("switch")
        edit_frame = tk.Frame(self)
        edit_frame.pack(side=tk.LEFT, fill=tk.Y, ipadx=2, ipady=2)
        radio_value = tk.IntVar()
        b = tk.Radiobutton(
            edit_frame, indicatoron=False, variable=radio_value, value=1, image=image
        )
        b.pack(side=tk.TOP, pady=1)
        b = tk.Radiobutton(
            edit_frame, indicatoron=False, variable=radio_value, value=2, image=image
        )
        b.pack(side=tk.TOP, pady=1)
        b = tk.Radiobutton(
            edit_frame, indicatoron=False, variable=radio_value, value=3, image=image
        )
        b.pack(side=tk.TOP, pady=1)
        b = tk.Radiobutton(
            edit_frame, indicatoron=False, variable=radio_value, value=4, image=image
        )
        b.pack(side=tk.TOP, pady=1)
        b = tk.Radiobutton(
            edit_frame, indicatoron=False, variable=radio_value, value=5, image=image
        )
        b.pack(side=tk.TOP, pady=1)

        self.canvas = CanvasGraph(
            self, background="#cccccc", scrollregion=(0, 0, 1000, 1000)
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        scroll_x = tk.Scrollbar(
            self.canvas, orient=tk.HORIZONTAL, command=self.canvas.xview
        )
        scroll_x.pack(side=tk.BOTTOM, fill=tk.X)
        scroll_y = tk.Scrollbar(self.canvas, command=self.canvas.yview)
        scroll_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.configure(xscrollcommand=scroll_x.set)
        self.canvas.configure(yscrollcommand=scroll_y.set)

        status_bar = tk.Frame(self)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        b = tk.Button(status_bar, text="Button 1")
        b.pack(side=tk.LEFT, padx=1)
        b = tk.Button(status_bar, text="Button 2")
        b.pack(side=tk.LEFT, padx=1)
        b = tk.Button(status_bar, text="Button 3")
        b.pack(side=tk.LEFT, padx=1)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    app = Application()
    app.mainloop()
