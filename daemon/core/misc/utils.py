"""
Miscellaneous utility functions, wrappers around some subprocess procedures.
"""

import ast
import os
import subprocess

import fcntl
import resource

from core.misc import log

logger = log.get_logger(__name__)


def closeonexec(fd):
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
        if not is_exe(executable):
            raise EnvironmentError("executable not found: %s" % executable)


def is_exe(file_path):
    """
    Check if a given file path exists and is an executable file.

    :param str file_path: file path to check
    :return: True if the file is considered and executable file, False otherwise
    :rtype: bool
    """
    return os.path.isfile(file_path) and os.access(file_path, os.X_OK)


def which(program):
    """
    From: http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python

    :param str program: program to check for
    :return: path if it exists, none otherwise
    """
    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip("\"")
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None


def ensurepath(pathlist):
    """
    Checks a list of paths are contained within the environment path, if not add it to the path.

    :param list[str] pathlist: list of paths to check
    :return: nothing
    """
    searchpath = os.environ["PATH"].split(":")
    for p in set(pathlist):
        if p not in searchpath:
            os.environ["PATH"] += ":" + p


def maketuple(obj):
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


def maketuplefromstr(s, value_type):
    """
    Create a tuple from a string.

    :param str s: string to convert to a tuple
    :param value_type: type of values to be contained within tuple
    :return: tuple from string
    :rtype: tuple
    """
    return tuple(value_type(i) for i in s.split(","))


def mutecall(*args, **kwargs):
    """
    Run a muted call command.

    :param list args: arguments for the command
    :param dict kwargs: keyword arguments for the command
    :return: command result
    :rtype: int
    """
    kwargs["stdout"] = open(os.devnull, "w")
    kwargs["stderr"] = subprocess.STDOUT
    return subprocess.call(*args, **kwargs)


def mutecheck_call(*args, **kwargs):
    """
    Run a muted check call command.

    :param list args: arguments for the command
    :param dict kwargs: keyword arguments for the command
    :return: command result
    :rtype: int
    """
    kwargs["stdout"] = open(os.devnull, "w")
    kwargs["stderr"] = subprocess.STDOUT
    return subprocess.check_call(*args, **kwargs)


def spawn(*args, **kwargs):
    """
    Wrapper for running a spawn command and returning the process id.

    :param list args: arguments for the command
    :param dict kwargs: keyword arguments for the command
    :return: process id of the command
    :rtype: int
    """
    return subprocess.Popen(*args, **kwargs).pid


def mutespawn(*args, **kwargs):
    """
    Wrapper for running a muted spawned command.

    :param list args: arguments for the command
    :param dict kwargs: keyword arguments for the command
    :return: process id of the command
    :rtype: int
    """
    kwargs["stdout"] = open(os.devnull, "w")
    kwargs["stderr"] = subprocess.STDOUT
    return subprocess.Popen(*args, **kwargs).pid


def detachinit():
    """
    Fork a child process and exit.

    :return: nothing
    """
    if os.fork():
        # parent exits
        os._exit(0)
    os.setsid()


def detach(*args, **kwargs):
    """
    Run a detached process by forking it.

    :param list args: arguments for the command
    :param dict kwargs: keyword arguments for the command
    :return: process id of the command
    :rtype: int
    """
    kwargs["preexec_fn"] = detachinit
    return subprocess.Popen(*args, **kwargs).pid


def mutedetach(*args, **kwargs):
    """
    Run a muted detached process by forking it.

    :param list args: arguments for the command
    :param dict kwargs: keyword arguments for the command
    :return: process id of the command
    :rtype: int
    """
    kwargs["preexec_fn"] = detachinit
    kwargs["stdout"] = open(os.devnull, "w")
    kwargs["stderr"] = subprocess.STDOUT
    return subprocess.Popen(*args, **kwargs).pid


def cmdresult(args):
    """
    Execute a command on the host and return a tuple containing the exit status and result string. stderr output
    is folded into the stdout result string.

    :param list args: command arguments
    :return: command status and stdout
    :rtype: tuple[int, str]
    """
    cmdid = subprocess.Popen(args, stdin=open(os.devnull, "r"), stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    # err will always be None
    result, err = cmdid.communicate()
    status = cmdid.wait()
    return status, result


def hexdump(s, bytes_per_word=2, words_per_line=8):
    """
    Hex dump of a string.

    :param str s: string to hex dump
    :param bytes_per_word: number of bytes per word
    :param words_per_line: number of words per line
    :return: hex dump of string
    """
    dump = ""
    count = 0
    bytes = bytes_per_word * words_per_line
    while s:
        line = s[:bytes]
        s = s[bytes:]
        tmp = map(lambda x: ("%02x" * bytes_per_word) % x,
                  zip(*[iter(map(ord, line))] * bytes_per_word))
        if len(line) % 2:
            tmp.append("%x" % ord(line[-1]))
        dump += "0x%08x: %s\n" % (count, " ".join(tmp))
        count += len(line)
    return dump[:-1]


def filemunge(pathname, header, text):
    """
    Insert text at the end of a file, surrounded by header comments.

    :param str pathname: file path to add text to
    :param str header: header text comments
    :param str text: text to append to file
    :return: nothing
    """
    # prevent duplicates
    filedemunge(pathname, header)
    f = open(pathname, "a")
    f.write("# BEGIN %s\n" % header)
    f.write(text)
    f.write("# END %s\n" % header)
    f.close()


def filedemunge(pathname, header):
    """
    Remove text that was inserted in a file surrounded by header comments.

    :param str pathname: file path to open for removing a header
    :param str header: header text to target for removal
    :return: nothing
    """
    f = open(pathname, "r")
    lines = f.readlines()
    f.close()
    start = None
    end = None
    for i in range(len(lines)):
        if lines[i] == "# BEGIN %s\n" % header:
            start = i
        elif lines[i] == "# END %s\n" % header:
            end = i + 1
    if start is None or end is None:
        return
    f = open(pathname, "w")
    lines = lines[:start] + lines[end:]
    f.write("".join(lines))
    f.close()


def expandcorepath(pathname, session=None, node=None):
    """
    Expand a file path given session information.

    :param str pathname: file path to expand
    :param core.session.Session session: core session object to expand path with
    :param core.netns.LxcNode node: node to expand path with
    :return: expanded path
    :rtype: str
    """
    if session is not None:
        pathname = pathname.replace("~", "/home/%s" % session.user)
        pathname = pathname.replace("%SESSION%", str(session.session_id))
        pathname = pathname.replace("%SESSION_DIR%", session.session_dir)
        pathname = pathname.replace("%SESSION_USER%", session.user)
    if node is not None:
        pathname = pathname.replace("%NODE%", str(node.objid))
        pathname = pathname.replace("%NODENAME%", node.name)
    return pathname


def sysctldevname(devname):
    """
    Translate a device name to the name used with sysctl.

    :param str devname: device name to translate
    :return: translated device name
    :rtype: str
    """
    if devname is None:
        return None
    return devname.replace(".", "/")


def daemonize(rootdir="/", umask=0, close_fds=False, dontclose=(),
              stdin=os.devnull, stdout=os.devnull, stderr=os.devnull,
              stdoutmode=0644, stderrmode=0644, pidfilename=None,
              defaultmaxfd=1024):
    """
    Run the background process as a daemon.

    :param str rootdir: root directory for daemon
    :param int umask: umask for daemon
    :param bool close_fds: flag to close file descriptors
    :param dontclose: dont close options
    :param stdin: stdin for daemon
    :param stdout: stdout for daemon
    :param stderr: stderr for daemon
    :param int stdoutmode: stdout mode
    :param int stderrmode: stderr mode
    :param str pidfilename: pid file name
    :param int defaultmaxfd: default max file descriptors
    :return: nothing
    """
    if not hasattr(dontclose, "__contains__"):
        if not isinstance(dontclose, int):
            raise TypeError("dontclose must be an integer")
        dontclose = (int(dontclose),)
    else:
        for fd in dontclose:
            if not isinstance(fd, int):
                raise TypeError("dontclose must contain only integers")

    # redirect stdin
    if stdin:
        fd = os.open(stdin, os.O_RDONLY)
        os.dup2(fd, 0)
        os.close(fd)

    # redirect stdout
    if stdout:
        fd = os.open(stdout, os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                     stdoutmode)
        os.dup2(fd, 1)
        if stdout == stderr:
            os.dup2(1, 2)
        os.close(fd)

    # redirect stderr
    if stderr and (stderr != stdout):
        fd = os.open(stderr, os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                     stderrmode)
        os.dup2(fd, 2)
        os.close(fd)

    if os.fork():
        # parent exits
        os._exit(0)

    os.setsid()
    pid = os.fork()
    if pid:
        if pidfilename:
            try:
                f = open(pidfilename, "w")
                f.write("%s\n" % pid)
                f.close()
            except IOError:
                logger.exception("error writing to file: %s", pidfilename)
        # parent exits
        os._exit(0)

    if rootdir:
        os.chdir(rootdir)

    os.umask(umask)
    if close_fds:
        try:
            maxfd = resource.getrlimit(resource.RLIMIT_NOFILE)[1]
            if maxfd == resource.RLIM_INFINITY:
                raise ValueError
        except:
            maxfd = defaultmaxfd

        for fd in xrange(3, maxfd):
            if fd in dontclose:
                continue
            try:
                os.close(fd)
            except IOError:
                logger.exception("error closing file descriptor")


def readfileintodict(filename, d):
    """
    Read key=value pairs from a file, into a dict. Skip comments; strip newline characters and spacing.

    :param str filename: file to read into a dictionary
    :param dict d: dictionary to read file into
    :return: nothing
    """
    with open(filename, "r") as f:
        lines = f.readlines()
    for l in lines:
        if l[:1] == "#":
            continue
        try:
            key, value = l.split("=", 1)
            d[key] = value.strip()
        except ValueError:
            logger.exception("error reading file to dict: %s", filename)


def checkforkernelmodule(name):
    """
    Return a string if a Linux kernel module is loaded, None otherwise.
    The string is the line from /proc/modules containing the module name,
    memory size (bytes), number of loaded instances, dependencies, state,
    and kernel memory offset.

    :param str name: name of kernel module to check for
    :return: kernel module line, None otherwise
    :rtype: str
    """
    with open("/proc/modules", "r") as f:
        for line in f:
            if line.startswith(name + " "):
                return line.rstrip()
    return None
