import logging
import tkinter as tk
from tkinter import messagebox, ttk
from typing import TYPE_CHECKING, Optional

import grpc

from core.api.grpc.wrappers import SessionState, SessionSummary
from core.gui import images
from core.gui.dialogs.dialog import Dialog
from core.gui.images import ImageEnum
from core.gui.task import ProgressTask
from core.gui.themes import PADX, PADY

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.gui.app import Application


class SessionsDialog(Dialog):
    def __init__(self, app: "Application", is_start_app: bool = False) -> None:
        super().__init__(app, "Sessions")
        self.is_start_app: bool = is_start_app
        self.selected_session: Optional[int] = None
        self.selected_id: Optional[int] = None
        self.tree: Optional[ttk.Treeview] = None
        self.connect_button: Optional[ttk.Button] = None
        self.delete_button: Optional[ttk.Button] = None
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.draw()

    def get_sessions(self) -> list[SessionSummary]:
        try:
            sessions = self.app.core.client.get_sessions()
            logger.info("sessions: %s", sessions)
            return sorted(sessions, key=lambda x: x.id)
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
        frame.grid(sticky=tk.NSEW, pady=PADY)
        self.tree = ttk.Treeview(
            frame,
            columns=("id", "state", "nodes"),
            show="headings",
            selectmode=tk.BROWSE,
        )
        style = ttk.Style()
        heading_size = int(self.app.guiconfig.scale * 10)
        style.configure("Treeview.Heading", font=(None, heading_size, "bold"))
        self.tree.grid(sticky=tk.NSEW)
        self.tree.column("id", stretch=tk.YES, anchor="center")
        self.tree.heading("id", text="ID")
        self.tree.column("state", stretch=tk.YES, anchor="center")
        self.tree.heading("state", text="State")
        self.tree.column("nodes", stretch=tk.YES, anchor="center")
        self.tree.heading("nodes", text="Node Count")
        self.draw_sessions()
        self.tree.bind("<Double-1>", self.double_click_join)
        self.tree.bind("<<TreeviewSelect>>", self.click_select)

        yscrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        yscrollbar.grid(row=0, column=1, sticky=tk.NS)
        self.tree.configure(yscrollcommand=yscrollbar.set)

        xscrollbar = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        xscrollbar.grid(row=1, sticky=tk.EW)
        self.tree.configure(xscrollcommand=xscrollbar.set)

    def draw_sessions(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for index, session in enumerate(self.get_sessions()):
            state_name = SessionState(session.state).name
            self.tree.insert(
                "",
                tk.END,
                text=str(session.id),
                values=(session.id, state_name, session.nodes),
            )

    def draw_buttons(self) -> None:
        frame = ttk.Frame(self.top)
        for i in range(4):
            frame.columnconfigure(i, weight=1)
        frame.grid(sticky=tk.EW)

        image = images.from_enum(ImageEnum.DOCUMENTNEW, width=images.BUTTON_SIZE)
        b = ttk.Button(
            frame, image=image, text="New", compound=tk.LEFT, command=self.click_new
        )
        b.image = image
        b.grid(row=0, padx=PADX, sticky=tk.EW)

        image = images.from_enum(ImageEnum.FILEOPEN, width=images.BUTTON_SIZE)
        self.connect_button = ttk.Button(
            frame,
            image=image,
            text="Connect",
            compound=tk.LEFT,
            command=self.click_connect,
            state=tk.DISABLED,
        )
        self.connect_button.image = image
        self.connect_button.grid(row=0, column=1, padx=PADX, sticky=tk.EW)

        image = images.from_enum(ImageEnum.DELETE, width=images.BUTTON_SIZE)
        self.delete_button = ttk.Button(
            frame,
            image=image,
            text="Delete",
            compound=tk.LEFT,
            command=self.click_delete,
            state=tk.DISABLED,
        )
        self.delete_button.image = image
        self.delete_button.grid(row=0, column=2, padx=PADX, sticky=tk.EW)

        image = images.from_enum(ImageEnum.CANCEL, width=images.BUTTON_SIZE)
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
        b.grid(row=0, column=3, sticky=tk.EW)

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
        logger.debug("selected session: %s", self.selected_session)

    def click_connect(self) -> None:
        if not self.selected_session:
            return
        self.join_session(self.selected_session)

    def join_session(self, session_id: int) -> None:
        self.destroy()
        task = ProgressTask(
            self.app, "Join", self.app.core.join_session, args=(session_id,)
        )
        task.start()

    def double_click_join(self, _event: tk.Event) -> None:
        item = self.tree.selection()
        if not item:
            return
        session_id = int(self.tree.item(item, "text"))
        self.join_session(session_id)

    def click_delete(self) -> None:
        if not self.selected_session:
            return
        logger.info("click delete session: %s", self.selected_session)
        self.tree.delete(self.selected_id)
        self.app.core.delete_session(self.selected_session)
        session_id = None
        if self.app.core.session:
            session_id = self.app.core.session.id
        if self.selected_session == session_id:
            self.app.core.session = None
            sessions = self.get_sessions()
            if not sessions:
                self.app.core.create_new_session()
                self.draw_sessions()
            else:
                session_id = sessions[0].id
                self.app.core.join_session(session_id)
        self.click_select()

    def click_exit(self) -> None:
        self.destroy()
        self.app.close()

    def on_closing(self) -> None:
        if self.is_start_app and messagebox.askokcancel("Exit", "Quit?", parent=self):
            self.click_exit()
        if not self.is_start_app:
            self.destroy()
