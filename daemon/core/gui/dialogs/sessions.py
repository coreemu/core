import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, List

import grpc

from core.api.grpc import core_pb2
from core.gui.dialogs.dialog import Dialog
from core.gui.images import ImageEnum, Images
from core.gui.task import ProgressTask
from core.gui.themes import PADX, PADY

if TYPE_CHECKING:
    from core.gui.app import Application


class SessionsDialog(Dialog):
    def __init__(
        self, master: "Application", app: "Application", is_start_app: bool = False
    ) -> None:
        super().__init__(master, app, "Sessions")
        self.is_start_app = is_start_app
        self.selected_session = None
        self.selected_id = None
        self.tree = None
        self.sessions = self.get_sessions()
        self.connect_button = None
        self.delete_button = None
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.draw()

    def get_sessions(self) -> List[core_pb2.SessionSummary]:
        try:
            response = self.app.core.client.get_sessions()
            logging.info("sessions: %s", response)
            return response.sessions
        except grpc.RpcError as e:
            self.app.show_grpc_exception("Get Sessions Error", e)
            self.destroy()

    def draw(self) -> None:
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(1, weight=1)
        self.draw_description()
        self.draw_tree()
        self.draw_buttons()

    def draw_description(self) -> None:
        """
        write a short description
        """
        label = ttk.Label(
            self.top,
            text="Below is a list of active CORE sessions. Double-click to \n"
            "connect to an existing session. Usually, only sessions in \n"
            "the RUNTIME state persist in the daemon, except for the \n"
            "one you might be concurrently editting.",
            justify=tk.CENTER,
        )
        label.grid(pady=PADY)

    def draw_tree(self) -> None:
        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        frame.grid(sticky="nsew", pady=PADY)
        self.tree = ttk.Treeview(
            frame,
            columns=("id", "state", "nodes"),
            show="headings",
            selectmode=tk.BROWSE,
        )
        style = ttk.Style()
        heading_size = int(self.app.guiconfig["scale"] * 10)
        style.configure("Treeview.Heading", font=(None, heading_size, "bold"))
        self.tree.grid(sticky="nsew")
        self.tree.column("id", stretch=tk.YES, anchor="center")
        self.tree.heading("id", text="ID")
        self.tree.column("state", stretch=tk.YES, anchor="center")
        self.tree.heading("state", text="State")
        self.tree.column("nodes", stretch=tk.YES, anchor="center")
        self.tree.heading("nodes", text="Node Count")

        for index, session in enumerate(self.sessions):
            state_name = core_pb2.SessionState.Enum.Name(session.state)
            self.tree.insert(
                "",
                tk.END,
                text=str(session.id),
                values=(session.id, state_name, session.nodes),
            )
        self.tree.bind("<Double-1>", self.double_click_join)
        self.tree.bind("<<TreeviewSelect>>", self.click_select)

        yscrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        yscrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=yscrollbar.set)

        xscrollbar = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        xscrollbar.grid(row=1, sticky="ew")
        self.tree.configure(xscrollcommand=xscrollbar.set)

    def draw_buttons(self) -> None:
        frame = ttk.Frame(self.top)
        for i in range(4):
            frame.columnconfigure(i, weight=1)
        frame.grid(sticky="ew")

        image = Images.get(ImageEnum.DOCUMENTNEW, 16)
        b = ttk.Button(
            frame, image=image, text="New", compound=tk.LEFT, command=self.click_new
        )
        b.image = image
        b.grid(row=0, padx=PADX, sticky="ew")

        image = Images.get(ImageEnum.FILEOPEN, 16)
        self.connect_button = ttk.Button(
            frame,
            image=image,
            text="Connect",
            compound=tk.LEFT,
            command=self.click_connect,
            state=tk.DISABLED,
        )
        self.connect_button.image = image
        self.connect_button.grid(row=0, column=1, padx=PADX, sticky="ew")

        image = Images.get(ImageEnum.DELETE, 16)
        self.delete_button = ttk.Button(
            frame,
            image=image,
            text="Delete",
            compound=tk.LEFT,
            command=self.click_delete,
            state=tk.DISABLED,
        )
        self.delete_button.image = image
        self.delete_button.grid(row=0, column=2, padx=PADX, sticky="ew")

        image = Images.get(ImageEnum.CANCEL, 16)
        if self.is_start_app:
            b = ttk.Button(
                frame,
                image=image,
                text="Exit",
                compound=tk.LEFT,
                command=self.click_exit,
            )
        else:
            b = ttk.Button(
                frame,
                image=image,
                text="Cancel",
                compound=tk.LEFT,
                command=self.destroy,
            )
        b.image = image
        b.grid(row=0, column=3, sticky="ew")

    def click_new(self) -> None:
        self.app.core.create_new_session()
        self.destroy()

    def click_select(self, _event: tk.Event = None) -> None:
        item = self.tree.selection()
        if item:
            self.selected_session = int(self.tree.item(item, "text"))
            self.selected_id = item
            self.delete_button.config(state=tk.NORMAL)
            self.connect_button.config(state=tk.NORMAL)
        else:
            self.selected_session = None
            self.selected_id = None
            self.delete_button.config(state=tk.DISABLED)
            self.connect_button.config(state=tk.DISABLED)
        logging.debug("selected session: %s", self.selected_session)

    def click_connect(self) -> None:
        if not self.selected_session:
            return
        self.join_session(self.selected_session)

    def join_session(self, session_id: int) -> None:
        self.destroy()
        if self.app.core.xml_file:
            self.app.core.xml_file = None
        task = ProgressTask(
            self.app, "Join", self.app.core.join_session, args=(session_id,)
        )
        task.start()

    def double_click_join(self, _event: tk.Event) -> None:
        item = self.tree.selection()
        if item is None:
            return
        session_id = int(self.tree.item(item, "text"))
        self.join_session(session_id)

    def click_delete(self) -> None:
        if not self.selected_session:
            return
        logging.debug("delete session: %s", self.selected_session)
        self.tree.delete(self.selected_id)
        self.app.core.delete_session(self.selected_session)
        if self.selected_session == self.app.core.session_id:
            self.click_new()
            self.destroy()
        self.click_select()

    def click_exit(self) -> None:
        self.destroy()
        self.app.close()

    def on_closing(self) -> None:
        if self.is_start_app and messagebox.askokcancel("Exit", "Quit?", parent=self):
            self.click_exit()
        if not self.is_start_app:
            self.destroy()
