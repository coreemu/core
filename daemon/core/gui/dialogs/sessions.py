import logging
import tkinter as tk
from tkinter import ttk

import grpc

from core.api.grpc import core_pb2
from core.gui.dialogs.dialog import Dialog
from core.gui.errors import show_grpc_error
from core.gui.images import ImageEnum, Images
from core.gui.task import BackgroundTask
from core.gui.themes import PADX, PADY


class SessionsDialog(Dialog):
    def __init__(self, master, app, is_start_app=False):
        super().__init__(master, app, "Sessions", modal=True)
        self.is_start_app = is_start_app
        self.selected = False
        self.selected_id = None
        self.tree = None
        self.sessions = self.get_sessions()
        self.draw()

    def get_sessions(self):
        try:
            response = self.app.core.client.get_sessions()
            logging.info("sessions: %s", response)
            return response.sessions
        except grpc.RpcError as e:
            show_grpc_error(e)
            self.destroy()

    def draw(self):
        self.top.columnconfigure(0, weight=1)
        self.top.rowconfigure(1, weight=1)
        self.draw_description()
        self.draw_tree()
        self.draw_buttons()

    def draw_description(self):
        """
        write a short description
        :return: nothing
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

    def draw_tree(self):
        frame = ttk.Frame(self.top)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        frame.grid(sticky="nsew", pady=PADY)
        self.tree = ttk.Treeview(
            frame, columns=("id", "state", "nodes"), show="headings"
        )
        self.tree.grid(sticky="nsew")
        self.tree.column("id", stretch=tk.YES)
        self.tree.heading("id", text="ID")
        self.tree.column("state", stretch=tk.YES)
        self.tree.heading("state", text="State")
        self.tree.column("nodes", stretch=tk.YES)
        self.tree.heading("nodes", text="Node Count")

        for index, session in enumerate(self.sessions):
            state_name = core_pb2.SessionState.Enum.Name(session.state)
            self.tree.insert(
                "",
                tk.END,
                text=str(session.id),
                values=(session.id, state_name, session.nodes),
            )
        self.tree.bind("<Double-1>", self.on_selected)
        self.tree.bind("<<TreeviewSelect>>", self.click_select)

        yscrollbar = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        yscrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=yscrollbar.set)

        xscrollbar = ttk.Scrollbar(frame, orient="horizontal", command=self.tree.xview)
        xscrollbar.grid(row=1, sticky="ew")
        self.tree.configure(xscrollcommand=xscrollbar.set)

    def draw_buttons(self):
        frame = ttk.Frame(self.top)
        for i in range(5):
            frame.columnconfigure(i, weight=1)
        frame.grid(sticky="ew")

        image = Images.get(ImageEnum.DOCUMENTNEW, 16)
        b = ttk.Button(
            frame, image=image, text="New", compound=tk.LEFT, command=self.click_new
        )
        b.image = image
        b.grid(row=0, padx=PADX, sticky="ew")

        image = Images.get(ImageEnum.FILEOPEN, 16)
        b = ttk.Button(
            frame,
            image=image,
            text="Connect",
            compound=tk.LEFT,
            command=self.click_connect,
        )
        b.image = image
        b.grid(row=0, column=1, padx=PADX, sticky="ew")

        image = Images.get(ImageEnum.SHUTDOWN, 16)
        b = ttk.Button(
            frame,
            image=image,
            text="Shutdown",
            compound=tk.LEFT,
            command=self.click_shutdown,
        )
        b.image = image
        b.grid(row=0, column=2, padx=PADX, sticky="ew")

        image = Images.get(ImageEnum.DELETE, 16)
        b = ttk.Button(
            frame,
            image=image,
            text="Delete",
            compound=tk.LEFT,
            command=self.click_delete,
        )
        b.image = image
        b.grid(row=0, column=3, padx=PADX, sticky="ew")

        image = Images.get(ImageEnum.CANCEL, 16)
        if self.is_start_app:
            b = ttk.Button(
                frame, image=image, text="Exit", compound=tk.LEFT, command=self.destroy
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
        b.grid(row=0, column=4, sticky="ew")

    def click_new(self):
        self.app.core.create_new_session()
        self.destroy()

    def click_select(self, event):
        item = self.tree.selection()
        session_id = int(self.tree.item(item, "text"))
        self.selected = True
        self.selected_id = session_id

    def click_connect(self):
        """
        if no session is selected yet, create a new one else join that session

        :return: nothing
        """
        if self.selected and self.selected_id is not None:
            self.join_session(self.selected_id)
        elif not self.selected and self.selected_id is None:
            self.click_new()
        else:
            logging.error("sessions invalid state")

    def click_shutdown(self):
        """
        if no session is currently selected create a new session else shut the selected
        session down.

        :return: nothing
        """
        if self.selected and self.selected_id is not None:
            self.shutdown_session(self.selected_id)
        elif not self.selected and self.selected_id is None:
            self.click_new()
        else:
            logging.error("querysessiondrawing.py invalid state")

    def join_session(self, session_id):
        self.app.statusbar.progress_bar.start(5)
        task = BackgroundTask(self.app, self.app.core.join_session, args=(session_id,))
        task.start()
        self.destroy()

    def on_selected(self, event):
        item = self.tree.selection()
        sid = int(self.tree.item(item, "text"))
        self.join_session(sid)

    def shutdown_session(self, sid):
        self.app.core.stop_session(sid)
        self.click_new()
        self.destroy()

    def click_delete(self):
        logging.debug("Click delete")
        item = self.tree.selection()
        if item:
            sid = int(self.tree.item(item, "text"))
            self.app.core.delete_session(sid)
            self.tree.delete(item[0])
            if sid == self.app.core.session_id:
                self.click_new()
