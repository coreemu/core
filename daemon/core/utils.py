"""
Miscellaneous utility functions, wrappers around some subprocess procedures.
"""

import concurrent.futures
import fcntl
import hashlib
import importlib
import inspect
import json
import logging
import logging.config
import os
import random
import shlex
import shutil
import sys
import threading
from collections import OrderedDict
from collections.abc import Iterable
from pathlib import Path
from queue import Queue
from subprocess import PIPE, STDOUT, Popen
from typing import TYPE_CHECKING, Any, Callable, Generic, Optional, TypeVar, Union

import netaddr

from core.errors import CoreCommandError, CoreError

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from core.emulator.coreemu import CoreEmu
    from core.emulator.session import Session
    from core.nodes.base import CoreNode
T = TypeVar("T")

DEVNULL = open(os.devnull, "wb")
IFACE_CONFIG_FACTOR: int = 1000


def execute_script(coreemu: "CoreEmu", file_path: Path, args: str) -> None:
    """
    Provides utility function to execute a python script in context of the
    provide coreemu instance.

    :param coreemu: coreemu to provide to script
    :param file_path: python script to execute
    :param args: args to provide script
    :return: nothing
    """
    sys.argv = shlex.split(args)
    thread = threading.Thread(
        target=execute_file, args=(file_path, {"coreemu": coreemu}), daemon=True
    )
    thread.start()
    thread.join()


def execute_file(
    path: Path, exec_globals: dict[str, str] = None, exec_locals: dict[str, str] = None
) -> None:
    """
    Provides a way to execute a file.

    :param path: path of file to execute
    :param exec_globals: globals values to pass to execution
    :param exec_locals:  local values to pass to execution
    :return: nothing
    """
    if exec_globals is None:
        exec_globals = {}
    exec_globals.update({"__file__": str(path), "__name__": "__main__"})
    with path.open("rb") as f:
        data = compile(f.read(), path, "exec")
    exec(data, exec_globals, exec_locals)


def hashkey(value: Union[str, int]) -> int:
    """
    Provide a consistent hash that can be used in place
    of the builtin hash, that no longer behaves consistently
    in python3.

    :param value: value to hash
    :return: hash value
    """
    if isinstance(value, int):
        value = str(value)
    value = value.encode()
    return int(hashlib.sha256(value).hexdigest(), 16)


def _detach_init() -> None:
    """
    Fork a child process and exit.

    :return: nothing
    """
    if os.fork():
        # parent exits
        os._exit(0)
    os.setsid()


def _valid_module(path: Path) -> bool:
    """
    Check if file is a valid python module.

    :param path: path to file
    :return: True if a valid python module file, False otherwise
    """
    if not path.is_file():
        return False
    if path.name.startswith("_"):
        return False
    if not path.suffix == ".py":
        return False
    return True


def _is_class(module: Any, member: type, clazz: type) -> bool:
    """
    Validates if a module member is a class and an instance of a CoreService.

    :param module: module to validate for service
    :param member: member to validate for service
    :param clazz: clazz type to check for validation
    :return: True if a valid service, False otherwise
    """
    if not inspect.isclass(member):
        return False
    if not issubclass(member, clazz):
        return False
    if member.__module__ != module.__name__:
        return False
    return True


def close_onexec(fd: int) -> None:
    """
    Close on execution of a shell process.

    :param fd: file descriptor to close
    :return: nothing
    """
    fdflags = fcntl.fcntl(fd, fcntl.F_GETFD)
    fcntl.fcntl(fd, fcntl.F_SETFD, fdflags | fcntl.FD_CLOEXEC)


def which(command: str, required: bool) -> str:
    """
    Find location of desired executable within current PATH.

    :param command: command to find location for
    :param required: command is required to be found, false otherwise
    :return: command location or None
    :raises ValueError: when not found and required
    """
    found_path = shutil.which(command)
    if found_path is None and required:
        raise CoreError(f"failed to find required executable({command}) in path")
    return found_path


def make_tuple_fromstr(s: str, value_type: Callable[[str], T]) -> tuple[T]:
    """
    Create a tuple from a string.

    :param s: string to convert to a tuple
    :param value_type: type of values to be contained within tuple
    :return: tuple from string
    """
    # remove tuple braces and strip commands and space from all values in the tuple
    # string
    values = []
    for x in s.strip("(), ").split(","):
        x = x.strip("' ")
        if x:
            values.append(x)
    return tuple(value_type(i) for i in values)


def mute_detach(args: str, **kwargs: dict[str, Any]) -> int:
    """
    Run a muted detached process by forking it.

    :param args: arguments for the command
    :param kwargs: keyword arguments for the command
    :return: process id of the command
    """
    args = shlex.split(args)
    kwargs["preexec_fn"] = _detach_init
    kwargs["stdout"] = DEVNULL
    kwargs["stderr"] = STDOUT
    return Popen(args, **kwargs).pid


def cmd(
    args: str,
    env: dict[str, str] = None,
    cwd: Path = None,
    wait: bool = True,
    shell: bool = False,
) -> str:
    """
    Execute a command on the host and returns the combined stderr stdout output.

    :param args: command arguments
    :param env: environment to run command with
    :param cwd: directory to run command in
    :param wait: True to wait for status, False otherwise
    :param shell: True to use shell, False otherwise
    :return: combined stdout and stderr
    :raises CoreCommandError: when there is a non-zero exit status or the file to
        execute is not found
    """
    logger.debug("command cwd(%s) wait(%s): %s", cwd, wait, args)
    input_args = args
    if shell is False:
        args = shlex.split(args)
    try:
        output = PIPE if wait else DEVNULL
        p = Popen(args, stdout=output, stderr=output, env=env, cwd=cwd, shell=shell)
        if wait:
            stdout, stderr = p.communicate()
            stdout = stdout.decode().strip()
            stderr = stderr.decode().strip()
            status = p.returncode
            if status != 0:
                raise CoreCommandError(status, input_args, stdout, stderr)
            return stdout
        else:
            return ""
    except OSError as e:
        logger.error("cmd error: %s", e.strerror)
        raise CoreCommandError(1, input_args, "", e.strerror)


def run_cmds(args: list[str], wait: bool = True, shell: bool = False) -> list[str]:
    """
    Execute a series of commands on the host and returns a list of the combined stderr
    stdout output.

    :param args: command arguments
    :param wait: True to wait for status, False otherwise
    :param shell: True to use shell, False otherwise
    :return: combined stdout and stderr
    :raises CoreCommandError: when there is a non-zero exit status or the file to
        execute is not found
    """
    outputs = []
    for arg in args:
        output = cmd(arg, wait=wait, shell=shell)
        outputs.append(output)
    return outputs


def file_munge(pathname: str, header: str, text: str) -> None:
    """
    Insert text at the end of a file, surrounded by header comments.

    :param pathname: file path to add text to
    :param header: header text comments
    :param text: text to append to file
    :return: nothing
    """
    # prevent duplicates
    file_demunge(pathname, header)

    with open(pathname, "a") as append_file:
        append_file.write(f"# BEGIN {header}\n")
        append_file.write(text)
        append_file.write(f"# END {header}\n")


def file_demunge(pathname: str, header: str) -> None:
    """
    Remove text that was inserted in a file surrounded by header comments.

    :param pathname: file path to open for removing a header
    :param header: header text to target for removal
    :return: nothing
    """
    with open(pathname) as read_file:
        lines = read_file.readlines()

    start = None
    end = None

    for i, line in enumerate(lines):
        if line == f"# BEGIN {header}\n":
            start = i
        elif line == f"# END {header}\n":
            end = i + 1

    if start is None or end is None:
        return

    with open(pathname, "w") as write_file:
        lines = lines[:start] + lines[end:]
        write_file.write("".join(lines))


def expand_corepath(
    pathname: str, session: "Session" = None, node: "CoreNode" = None
) -> Path:
    """
    Expand a file path given session information.

    :param pathname: file path to expand
    :param session: core session object to expand path
    :param node: node to expand path with
    :return: expanded path
    """
    if session is not None:
        pathname = pathname.replace("~", f"/home/{session.user}")
        pathname = pathname.replace("%SESSION%", str(session.id))
        pathname = pathname.replace("%SESSION_DIR%", str(session.directory))
        pathname = pathname.replace("%SESSION_USER%", session.user)
    if node is not None:
        pathname = pathname.replace("%NODE%", str(node.id))
        pathname = pathname.replace("%NODENAME%", node.name)
    return Path(pathname)


def sysctl_devname(devname: str) -> Optional[str]:
    """
    Translate a device name to the name used with sysctl.

    :param devname: device name to translate
    :return: translated device name
    """
    if devname is None:
        return None
    return devname.replace(".", "/")


def load_config(file_path: Path, d: dict[str, str]) -> None:
    """
    Read key=value pairs from a file, into a dict. Skip comments; strip newline
    characters and spacing.

    :param file_path: file path to read data from
    :param d: dictionary to config into
    :return: nothing
    """
    with file_path.open("r") as f:
        lines = f.readlines()
    for line in lines:
        if line[:1] == "#":
            continue
        try:
            key, value = line.split("=", 1)
            d[key] = value.strip()
        except ValueError:
            logger.exception("error reading file to dict: %s", file_path)


def load_module(import_statement: str, clazz: Generic[T]) -> list[T]:
    classes = []
    try:
        module = importlib.import_module(import_statement)
        members = inspect.getmembers(module, lambda x: _is_class(module, x, clazz))
        for member in members:
            valid_class = member[1]
            classes.append(valid_class)
    except Exception:
        logger.exception(
            "unexpected error during import, skipping: %s", import_statement
        )
    return classes


def load_classes(path: Path, clazz: Generic[T]) -> list[T]:
    """
    Dynamically load classes for use within CORE.

    :param path: path to load classes from
    :param clazz: class type expected to be inherited from for loading
    :return: list of classes loaded
    """
    # validate path exists
    logger.debug("attempting to load modules from path: %s", path)
    if not path.is_dir():
        logger.warning("invalid custom module directory specified" ": %s", path)
    # check if path is in sys.path
    parent = str(path.parent)
    if parent not in sys.path:
        logger.debug("adding parent path to allow imports: %s", parent)
        sys.path.append(parent)
    # import and add all service modules in the path
    classes = []
    for p in path.iterdir():
        if not _valid_module(p):
            continue
        import_statement = f"{path.name}.{p.stem}"
        logger.debug("importing custom module: %s", import_statement)
        loaded = load_module(import_statement, clazz)
        classes.extend(loaded)
    return classes


def load_logging_config(config_path: Path) -> None:
    """
    Load CORE logging configuration file.

    :param config_path: path to logging config file
    :return: nothing
    """
    with config_path.open("r") as f:
        log_config = json.load(f)
    logging.config.dictConfig(log_config)


def run_cmds_threaded(
    node_cmds: list[tuple["CoreNode", list[str]]],
    wait: bool = True,
    shell: bool = False,
    workers: int = None,
) -> tuple[dict[int, list[str]], list[Exception]]:
    """
    Run the set of commands for the node provided. Each node will
    run the commands within the context of a threadpool.

    :param node_cmds: list of tuples of nodes and commands to run within them
    :param wait: True to wait for status, False otherwise
    :param shell: True to run shell like, False otherwise
    :param workers: number of workers for threadpool, uses library default otherwise
    :return: tuple including dict of node id to list of command output and a list of
        exceptions if any
    """

    def _node_cmds(
        _target: "CoreNode", _cmds: list[str], _wait: bool, _shell: bool
    ) -> list[str]:
        cmd_outputs = []
        for _cmd in _cmds:
            output = _target.cmd(_cmd, wait=_wait, shell=_shell)
            cmd_outputs.append(output)
        return cmd_outputs

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = []
        node_mappings = {}
        for node, cmds in node_cmds:
            future = executor.submit(_node_cmds, node, cmds, wait, shell)
            node_mappings[future] = node
            futures.append(future)
        outputs = {}
        exceptions = []
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                node = node_mappings[future]
                outputs[node.id] = result
            except Exception as e:
                logger.exception("thread pool exception")
                exceptions.append(e)
    return outputs, exceptions


def run_cmds_mp(
    node_cmds: list[tuple["CoreNode", list[str]]],
    wait: bool = True,
    shell: bool = False,
    workers: int = None,
) -> tuple[dict[int, list[str]], list[Exception]]:
    """
    Run the set of commands for the node provided. Each node will
    run the commands within the context of a process pool. This will not work
    for distributed nodes and throws an exception when encountered.

    :param node_cmds: list of tuples of nodes and commands to run within them
    :param wait: True to wait for status, False otherwise
    :param shell: True to run shell like, False otherwise
    :param workers: number of workers for threadpool, uses library default otherwise
    :return: tuple including dict of node id to list of command output and a list of
        exceptions if any
    :raises CoreError: when a distributed node is provided as input
    """
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as executor:
        futures = []
        node_mapping = {}
        for node, cmds in node_cmds:
            node_cmds = [node.create_cmd(x) for x in cmds]
            if node.server:
                raise CoreError(
                    f"{node.name} uses a distributed server and not supported"
                )
            future = executor.submit(run_cmds, node_cmds, wait=wait, shell=shell)
            node_mapping[future] = node
            futures.append(future)
        exceptions = []
        outputs = {}
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                node = node_mapping[future]
                outputs[node.id] = result
            except Exception as e:
                logger.exception("thread pool exception")
                exceptions.append(e)
    return outputs, exceptions


def threadpool(
    funcs: list[tuple[Callable, Iterable[Any], dict[Any, Any]]], workers: int = 10
) -> tuple[list[Any], list[Exception]]:
    """
    Run provided functions, arguments, and keywords within a threadpool
    collecting results and exceptions.

    :param funcs: iterable that provides a func, args, kwargs
    :param workers: number of workers for the threadpool
    :return: results and exceptions from running functions with args and kwargs
    """
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = []
        for func, args, kwargs in funcs:
            future = executor.submit(func, *args, **kwargs)
            futures.append(future)
        results = []
        exceptions = []
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                logger.exception("thread pool exception")
                exceptions.append(e)
    return results, exceptions


def random_mac() -> str:
    """
    Create a random mac address using Xen OID 00:16:3E.

    :return: random mac address
    """
    value = random.randint(0, 0xFFFFFF)
    value |= 0x00163E << 24
    mac = netaddr.EUI(value, dialect=netaddr.mac_unix_expanded)
    return str(mac)


def iface_config_id(node_id: int, iface_id: int = None) -> int:
    """
    Common utility to generate a configuration id, in case an interface is being
    targeted.

    :param node_id: node for config id
    :param iface_id: interface for config id
    :return: generated config id when interface is present, node id otherwise
    """
    if iface_id is not None and iface_id >= 0:
        return node_id * IFACE_CONFIG_FACTOR + iface_id
    else:
        return node_id


def parse_iface_config_id(config_id: int) -> tuple[int, Optional[int]]:
    """
    Parses configuration id, that may be potentially derived from an interface for a
    node.

    :param config_id: configuration id to parse
    :return:
    """
    iface_id = None
    node_id = config_id
    if config_id >= IFACE_CONFIG_FACTOR:
        iface_id = config_id % IFACE_CONFIG_FACTOR
        node_id = config_id // IFACE_CONFIG_FACTOR
    return node_id, iface_id


class SetQueue(Queue):
    """
    Set backed queue to avoid duplicate submissions.
    """

    def _init(self, maxsize):
        self.queue: OrderedDict = OrderedDict()

    def _put(self, item):
        self.queue[item] = None

    def _get(self):
        key, _ = self.queue.popitem(last=False)
        return key
