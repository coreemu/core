from tkinter import messagebox


def show_grpc_error(e):
    title = [x.capitalize() for x in e.code().name.lower().split("_")]
    title = " ".join(title)
    title = f"GRPC {title}"
    messagebox.showerror(title, e.details())
