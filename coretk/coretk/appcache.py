"""
stores some information helpful for setting starting values for some tables
like size and scale, set wallpaper, etc
"""
import tkinter as tk


def cache_variable(application):
    # for menubar
    application.is_open_xml = False

    application.size_and_scale = None
    application.set_wallpaper = None

    # set wallpaper variables

    # canvas id of the wallpaper
    application.wallpaper_id = None

    # current image for wallpaper
    application.current_wallpaper = None

    # wallpaper option
    application.radiovar = tk.IntVar()
    application.radiovar.set(1)

    # show grid option
    application.show_grid_var = tk.IntVar()
    application.show_grid_var.set(1)

    # adjust canvas to image dimension variable
    application.adjust_to_dim_var = tk.IntVar()
    application.adjust_to_dim_var.set(0)
