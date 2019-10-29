import logging
import tkinter as tk
from tkinter.ttk import Scrollbar, Treeview

from coretk.images import ImageEnum, Images


class SessionTable:
    def __init__(self, grpc, master):
        """
        create session table instance
        :param coretk.coregrpc.CoreGrpc grpc: coregrpc
        :param root.master master:
        """
        self.grpc = grpc
        self.selected = False
        self.selected_sid = None
        self.master = master
        self.top = tk.Toplevel(self.master)
        self.description_definition()
        self.top.title("CORE sessions")

        self.tree = Treeview(self.top)
        # self.tree.pack(side=tk.TOP)
        self.tree.grid(row=1, column=0, columnspan=2)
        self.draw_scrollbar()
        self.draw()

    def description_definition(self):
        """
        write a short description
        :return: nothing
        """
        lable = tk.Label(
            self.top,
            text="Below is a list of active CORE sessions. Double-click to "
            "\nconnect to an existing session. Usually, only sessions in "
            "\nthe RUNTIME state persist in the daemon, except for the "
            "\none you might be concurrently editting.",
        )
        lable.grid(sticky=tk.W)

    def column_definition(self):
        # self.tree["columns"] = ("name", "nodecount", "filename", "date")
        self.tree["columns"] = "nodecount"
        self.tree.column("#0", width=300, minwidth=30)
        # self.tree.column("name", width=72, miwidth=30)
        self.tree.column("nodecount", width=300, minwidth=30)
        # self.tree.column("filename", width=92, minwidth=30)
        # self.tree.column("date", width=170, minwidth=30)

    def draw_scrollbar(self):
        yscrollbar = Scrollbar(self.top, orient="vertical", command=self.tree.yview)
        yscrollbar.grid(row=1, column=3, sticky=tk.N + tk.S + tk.W)
        self.tree.configure(yscrollcommand=yscrollbar.set)

        xscrollbar = Scrollbar(self.top, orient="horizontal", command=self.tree.xview)
        xscrollbar.grid(row=2, columnspan=2, sticky=tk.E + tk.W + tk.S)
        self.tree.configure(xscrollcommand=xscrollbar.set)

    def heading_definition(self):
        self.tree.heading("#0", text="ID", anchor=tk.W)
        # self.tree.heading("name", text="Name", anchor=tk.CENTER)
        self.tree.heading("nodecount", text="Node Count", anchor=tk.W)
        # self.tree.heading("filename", text="Filename", anchor=tk.CENTER)
        # self.tree.heading("date", text="Date", anchor=tk.CENTER)

    def enter_session(self, sid):
        self.top.destroy()
        response = self.grpc.core.get_session(sid)
        self.grpc.session_id = sid
        self.grpc.core.events(sid, self.grpc.log_event)
        logging.info("Entering session_id %s.... Result: %s", sid, response)

    def new_session(self):
        self.top.destroy()
        self.grpc.create_new_session()

    def on_selected(self, event):
        item = self.tree.selection()
        sid = int(self.tree.item(item, "text"))
        self.enter_session(sid)

    def click_select(self, event):
        # logging.debug("Click on %s ", event)
        item = self.tree.selection()
        sid = int(self.tree.item(item, "text"))
        self.selected = True
        self.selected_sid = sid

    def session_definition(self):
        response = self.grpc.core.get_sessions()
        # logging.info("querysessiondrawing.py Get all sessions %s", response)
        index = 1
        for session in response.sessions:
            self.tree.insert(
                "", index, None, text=str(session.id), values=(str(session.nodes))
            )
            index = index + 1
        self.tree.bind("<Double-1>", self.on_selected)
        self.tree.bind("<<TreeviewSelect>>", self.click_select)

    def click_connect(self):
        """
        if no session is selected yet, create a new one else join that session

        :return: nothing
        """
        if self.selected and self.selected_sid is not None:
            self.enter_session(self.selected_sid)
        elif not self.selected and self.selected_sid is None:
            self.new_session()
        else:
            logging.error("querysessiondrawing.py invalid state")

    def shutdown_session(self, sid):
        self.grpc.terminate_session(sid)
        self.new_session()
        self.top.destroy()

    def click_shutdown(self):
        """
        if no session is currently selected create a new session else shut the selected session down

        :return: nothing
        """
        if self.selected and self.selected_sid is not None:
            self.shutdown_session(self.selected_sid)
        elif not self.selected and self.selected_sid is None:
            self.new_session()
        else:
            logging.error("querysessiondrawing.py invalid state")
        # if self.selected and self.selected_sid is not None:

    def draw_buttons(self):
        f = tk.Frame(self.top)
        f.grid(row=3, sticky=tk.W)

        b = tk.Button(
            f,
            image=Images.get(ImageEnum.DOCUMENTNEW.value),
            text="New",
            compound=tk.LEFT,
            command=self.new_session,
        )
        b.pack(side=tk.LEFT, padx=3, pady=4)
        b = tk.Button(
            f,
            image=Images.get(ImageEnum.FILEOPEN.value),
            text="Connect",
            compound=tk.LEFT,
            command=self.click_connect,
        )
        b.pack(side=tk.LEFT, padx=3, pady=4)
        b = tk.Button(
            f,
            image=Images.get(ImageEnum.EDITDELETE.value),
            text="Shutdown",
            compound=tk.LEFT,
            command=self.click_shutdown,
        )
        b.pack(side=tk.LEFT, padx=3, pady=4)
        b = tk.Button(f, text="Cancel", command=self.new_session)
        b.pack(side=tk.LEFT, padx=3, pady=4)

    def center(self):
        window_width = self.master.winfo_width()
        window_height = self.master.winfo_height()
        self.top.update()
        top_level_width = self.top.winfo_width()
        top_level_height = self.top.winfo_height()
        x = window_width / 2 - top_level_width / 2
        y = window_height / 2 - top_level_height / 2

        self.top.geometry("+%d+%d" % (x, y))

    def draw(self):
        self.column_definition()
        self.heading_definition()
        self.session_definition()
        self.draw_buttons()
        self.center()
        self.top.wait_window()
