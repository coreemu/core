"""
Miscellaneous utility functions, wrappers around some subprocess procedures.
"""

import fcntl
import importlib
import inspect
import logging
import os
import shlex
import subprocess
import sys
from past.builtins import basestring

from core import CoreCommandError

DEVNULL = open(os.devnull, "wb")


def _detach_init():
    """
    Fork a child process and exit.

    :return: nothing
    """
    if os.fork():
        # parent exits
        os._exit(0)
    os.setsid()


def _valid_module(path, file_name):
    """
    Check if file is a valid python module.

    :param str path: path to file
    :param str file_name: file name to check
    :return: True if a valid python module file, False otherwise
    :rtype: bool
    """
    file_path = os.path.join(path, file_name)
    if not os.path.isfile(file_path):
        return False

    if file_name.startswith("_"):
        return False

    if not file_name.endswith(".py"):
        return False

    return True


def _is_class(module, member, clazz):
    """
    Validates if a module member is a class and an instance of a CoreService.

    :param module: module to validate for service
    :param member: member to validate for service
    :param clazz: clazz type to check for validation
    :return: True if a valid service, False otherwise
    :rtype: bool
    """
    if not inspect.isclass(member):
        return False

    if not issubclass(member, clazz):
        return False

    if member.__module__ != module.__name__:
        return False

    return True


def _is_exe(file_path):
    """
    Check if a given file path exists and is an executable file.

    :param str file_path: file path to check
    :return: True if the file is considered and executable file, False otherwise
    :rtype: bool
    """
    return os.path.isfile(file_path) and os.access(file_path, os.X_OK)


def close_onexec(fd):
    """
    Close on execution of a shell process.

    :param fd: file descriptor to close
    :return: nothing
    """
    fdflags = fcntl.fcntl(fd, fcntl.F_GETFD)
    fcntl.fcntl(fd, fcntl.F_SETFD, fdflags | fcntl.FD_CLOEXEC)


def check_executables(executables):
    """
    Check executables, verify they exist and are executable.

    :param list[str] executables: executable to check
    :return: nothing
    :raises EnvironmentError: when an executable doesn't exist or is not executable
    """
    for executable in executables:
        if not _is_exe(executable):
            raise EnvironmentError("executable not found: %s" % executable)


def make_tuple(obj):
    """
    Create a tuple from an object, or return the object itself.

    :param obj: object to convert to a tuple
    :return: converted tuple or the object itself
    :rtype: tuple
    """
    if hasattr(obj, "__iter__"):
        return tuple(obj)
    else:
        return obj,


def make_tuple_fromstr(s, value_type):
    """
    Create a tuple from a string.

    :param str s: string to convert to a tuple
    :param value_type: type of values to be contained within tuple
    :return: tuple from string
    :rtype: tuple
    """
    # remove tuple braces and strip commands and space from all values in the tuple string
    values = []
    for x in s.strip("(), ").split(","):
        x = x.strip("' ")
        if x:
            values.append(x)
    return tuple(value_type(i) for i in values)


def split_args(args):
    """
    Convenience method for splitting potential string commands into a shell-like syntax list.

    :param list/str args: command list or string
    :return: shell-like syntax list
    :rtype: list
    """
    if isinstance(args, basestring):
        args = shlex.split(args)
    return args


def mute_detach(args, **kwargs):
    """
    Run a muted detached process by forking it.

    :param list[str]|str args: arguments for the command
    :param dict kwargs: keyword arguments for the command
    :return: process id of the command
    :rtype: int
    """
    args = split_args(args)
    kwargs["preexec_fn"] = _detach_init
    kwargs["stdout"] = DEVNULL
    kwargs["stderr"] = subprocess.STDOUT
    return subprocess.Popen(args, **kwargs).pid


def cmd(args, wait=True):
    """
    Runs a command on and returns the exit status.

    :param list[str]|str args: command arguments
    :param bool wait: wait for command to end or not
    :return: command status
    :rtype: int
    """
    args = split_args(args)
    logging.debug("command: %s", args)
    try:
        p = subprocess.Popen(args)
        if not wait:
            return 0
        return p.wait()
    except OSError:
        raise CoreCommandError(-1, args)


def cmd_output(args):
    """
    Execute a command on the host and return a tuple containing the exit status and result string. stderr output
    is folded into the stdout result string.

    :param list[str]|str args: command arguments
    :return: command status and stdout
    :rtype: tuple[int, str]
    :raises CoreCommandError: when the file to execute is not found
    """
    args = split_args(args)
    logging.debug("command: %s", args)
    try:
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        stdout, _ = p.communicate()
        status = p.wait()
        return status, stdout.decode("utf-8").strip()
    except OSError:
        raise CoreCommandError(-1, args)


def check_cmd(args, **kwargs):
    """
    Execute a command on the host and return a tuple containing the exit status and result string. stderr output
    is folded into the stdout result string.

    :param list[str]|str args: command arguments
    :param dict kwargs: keyword arguments to pass to subprocess.Popen
    :return: combined stdout and stderr
    :rtype: str
    :raises CoreCommandError: when there is a non-zero exit status or the file to execute is not found
    """
    kwargs["stdout"] = subprocess.PIPE
    kwargs["stderr"] = subprocess.STDOUT
    args = split_args(args)
    logging.debug("command: %s", args)
    try:
        p = subprocess.Popen(args, **kwargs)
        stdout, _ = p.communicate()
        status = p.wait()
        if status != 0:
            raise CoreCommandError(status, args, stdout)
        return stdout.decode("utf-8").strip()
    except OSError:
        raise CoreCommandError(-1, args)


def hex_dump(s, bytes_per_word=2, words_per_line=8):
    """
    Hex dump of a string.

    :param str s: string to hex dump
    :param bytes_per_word: number of bytes per word
    :param words_per_line: number of words per line
    :return: hex dump of string
    """
    dump = ""
    count = 0
    total_bytes = bytes_per_word * words_per_line

    while s:
        line = s[:total_bytes]
        s = s[total_bytes:]
        tmp = map(lambda x: ("%02x" * bytes_per_word) % x, zip(*[iter(map(ord, line))] * bytes_per_word))
        if len(line) % 2:
            tmp.append("%x" % ord(line[-1]))
        dump += "0x%08x: %s\n" % (count, " ".join(tmp))
        count += len(line)
    return dump[:-1]


def file_munge(pathname, header, text):
    """
    Insert text at the end of a file, surrounded by header comments.

    :param str pathname: file path to add text to
    :param str header: header text comments
    :param str text: text to append to file
    :return: nothing
    """
    # prevent duplicates
    file_demunge(pathname, header)

    with open(pathname, "a") as append_file:
        append_file.write("# BEGIN %s\n" % header)
        append_file.write(text)
        append_file.write("# END %s\n" % header)


def file_demunge(pathname, header):
    """
    Remove text that was inserted in a file surrounded by header comments.

    :param str pathname: file path to open for removing a header
    :param str header: header text to target for removal
    :return: nothing
    """
    with open(pathname, "r") as read_file:
        lines = read_file.readlines()

    start = None
    end = None

    for i, line in enumerate(lines):
        if line == "# BEGIN %s\n" % header:
            start = i
        elif line == "# END %s\n" % header:
            end = i + 1

    if start is None or end is None:
        return

    with open(pathname, "w") as write_file:
        lines = lines[:start] + lines[end:]
        write_file.write("".join(lines))


def expand_corepath(pathname, session=None, node=None):
    """
    Expand a file path given session information.

    :param str pathname: file path to expand
    :param core.emulator.session.Session session: core session object to expand path with
    :param core.nodes.base.CoreNode node: node to expand path with
    :return: expanded path
    :rtype: str
    """
    if session is not None:
        pathname = pathname.replace("~", "/home/%s" % session.user)
        pathname = pathname.replace("%SESSION%", str(session.id))
        pathname = pathname.replace("%SESSION_DIR%", session.session_dir)
        pathname = pathname.replace("%SESSION_USER%", session.user)

    if node is not None:
        pathname = pathname.replace("%NODE%", str(node.id))
        pathname = pathname.replace("%NODENAME%", node.name)

    return pathname


def sysctl_devname(devname):
    """
    Translate a device name to the name used with sysctl.

    :param str devname: device name to translate
    :return: translated device name
    :rtype: str
    """
    if devname is None:
        return None
    return devname.replace(".", "/")


def load_config(filename, d):
    """
    Read key=value pairs from a file, into a dict. Skip comments; strip newline characters and spacing.

    :param str filename: file to read into a dictionary
    :param dict d: dictionary to read file into
    :return: nothing
    """
    with open(filename, "r") as f:
        lines = f.readlines()

    for line in lines:
        if line[:1] == "#":
            continue

        try:
            key, value = line.split("=", 1)
            d[key] = value.strip()
        except ValueError:
            logging.exception("error reading file to dict: %s", filename)


def load_classes(path, clazz):
    """
    Dynamically load classes for use within CORE.

    :param path: path to load classes from
    :param clazz: class type expected to be inherited from for loading
    :return: list of classes loaded
    """
    # validate path exists
    logging.debug("attempting to load modules from path: %s", path)
    if not os.path.isdir(path):
        logging.warning("invalid custom module directory specified" ": %s" % path)
    # check if path is in sys.path
    parent_path = os.path.dirname(path)
    if parent_path not in sys.path:
        logging.debug("adding parent path to allow imports: %s", parent_path)
        sys.path.append(parent_path)

    # retrieve potential service modules, and filter out invalid modules
    base_module = os.path.basename(path)
    module_names = os.listdir(path)
    module_names = filter(lambda x: _valid_module(path, x), module_names)
    module_names = map(lambda x: x[:-3], module_names)

    # import and add all service modules in the path
    classes = []
    for module_name in module_names:
        import_statement = "%s.%s" % (base_module, module_name)
        logging.debug("importing custom module: %s", import_statement)
        try:
            module = importlib.import_module(import_statement)
            members = inspect.getmembers(module, lambda x: _is_class(module, x, clazz))
            for member in members:
                valid_class = member[1]
                classes.append(valid_class)
        except:
            logging.exception("unexpected error during import, skipping: %s", import_statement)

    return classes
