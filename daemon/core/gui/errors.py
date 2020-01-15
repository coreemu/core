from tkinter import messagebox
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import grpc


def show_grpc_error(e: "grpc.RpcError"):
    title = [x.capitalize() for x in e.code().name.lower().split("_")]
    title = " ".join(title)
    title = f"GRPC {title}"
    messagebox.showerror(title, e.details())
