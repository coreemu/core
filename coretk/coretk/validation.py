"""
input validation
"""
import logging
import tkinter as tk


def validate_command(master, func):
    return master.register(func)


def check_positive_int(s):
    logging.debug("int validation...")
    try:
        int_value = int(s)
        if int_value >= 0:
            return True
        return False
    except ValueError:
        return False


def check_positive_float(s):
    logging.debug("float validation...")
    try:
        float_value = float(s)
        if float_value >= 0.0:
            return True
        return False
    except ValueError:
        return False


def check_node_name(name):
    logging.debug("node name validation...")
    if len(name) <= 0:
        return False
    for char in name:
        if not char.isalnum() and char != "_":
            return False
    return True


def check_canvas_int(s):
    logging.debug("int validation...")
    if len(s) == 0:
        return True
    try:
        int_value = int(s)
        if int_value >= 0:
            return True
        return False
    except ValueError:
        return False


def check_canvas_float(s):
    logging.debug("canvas float validation")
    if not s:
        return True
    try:
        float_value = float(s)
        if float_value >= 0.0:
            return True
        return False
    except ValueError:
        return False


def check_interface(name):
    logging.debug("interface name validation...")
    if len(name) <= 0:
        return False, "Interface name cannot be an empty string"
    for char in name:
        if not char.isalnum() and char != "_":
            return (
                False,
                "Interface name can only contain alphanumeric letter (a-z) and (0-9) or underscores (_)",
            )
    return True, ""


def combine_message(key, current_validation, current_message, res, msg):
    if not res:
        current_validation = res
        current_message = current_message + key + ": " + msg + "\n\n"
    return current_validation, current_message


def check_wlan_config(config):
    result = True
    message = ""
    checks = ["bandwidth", "delay", "error", "jitter", "range"]
    for check in checks:
        if check in ["bandwidth", "delay", "jitter"]:
            res, msg = check_positive_int(config[check].value)
            result, message = combine_message(check, result, message, res, msg)
        elif check in ["range", "error"]:
            res, msg = check_positive_float(config[check].value)
            result, message = combine_message(check, result, message, res, msg)
    return result, message


def check_size_and_scale(dialog):
    result = True
    message = ""
    try:
        pixel_width = dialog.pixel_width.get()
        if pixel_width < 0:
            result, message = combine_message(
                "pixel width", result, message, False, "cannot be negative"
            )
    except tk.TclError:
        result, message = combine_message(
            "pixel width",
            result,
            message,
            False,
            "invalid value, input non-negative float",
        )
    try:
        pixel_height = dialog.pixel_height.get()
        if pixel_height < 0:
            result, message = combine_message(
                "pixel height", result, message, False, "cannot be negative"
            )
    except tk.TclError:
        result, message = combine_message(
            "pixel height",
            result,
            message,
            False,
            "invalid value, input non-negative float",
        )
    try:
        scale = dialog.scale.get()
        if scale <= 0:
            result, message = combine_message(
                "scale", result, message, False, "cannot be negative"
            )
    except tk.TclError:
        result, message = combine_message(
            "scale", result, message, False, "invalid value, input non-negative float"
        )
    # pixel_height = dialog.pixel_height.get()
    # print(pixel_width, pixel_height)
    # res, msg = check_positive_int(pixel_width)
    # result, message = combine_message("pixel width", result, message, res, msg)
    # res, msg = check_positive_int(pixel_height)
    # result, message = combine_message("pixel height", result, message, res, msg)
    return result, message
