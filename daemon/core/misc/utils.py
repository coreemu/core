#
# CORE
# Copyright (c)2010-2012 the Boeing Company.
# See the LICENSE file included in this distribution.
#
# authors: Tom Goff <thomas.goff@boeing.com>
#          Jeff Ahrenholz <jeffrey.m.ahrenholz@boeing.com>
#
'''
utils.py: miscellaneous utility functions, wrappers around some subprocess
procedures.
'''

import subprocess, os, ast
import fcntl

def closeonexec(fd):
    fdflags = fcntl.fcntl(fd, fcntl.F_GETFD)
    fcntl.fcntl(fd, fcntl.F_SETFD, fdflags | fcntl.FD_CLOEXEC)

def checkexec(execlist):
    for bin in execlist:
        if which(bin) is None:
            raise EnvironmentError, "executable not found: %s" % bin

def which(program):
    ''' From: http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python
    '''
    def is_exe(fpath):
        return os.path.isfile(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program
    else:
        for path in os.environ["PATH"].split(os.pathsep):
            path = path.strip('"')
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None

def ensurepath(pathlist):
    searchpath = os.environ["PATH"].split(":")
    for p in set(pathlist):
        if p not in searchpath:
            os.environ["PATH"] += ":" + p

def maketuple(obj):
    if hasattr(obj, "__iter__"):
        return tuple(obj)
    else:
        return (obj,)
        
def maketuplefromstr(s, type):
    s.replace('\\', '\\\\')
    return ast.literal_eval(s)
    #return tuple(type(i) for i in s[1:-1].split(','))
    #r = ()
    #for i in s.strip("()").split(','):
    #    r += (i.strip("' "), )
    # chop empty last element from "('a',)" strings
    #if r[-1] == '':
    #    r = r[:-1]
    #return r

def call(*args, **kwds):
    return subprocess.call(*args, **kwds)

def mutecall(*args, **kwds):
    kwds["stdout"] = open(os.devnull, "w")
    kwds["stderr"] = subprocess.STDOUT
    return call(*args, **kwds)

def check_call(*args, **kwds):
    return subprocess.check_call(*args, **kwds)

def mutecheck_call(*args, **kwds):
    kwds["stdout"] = open(os.devnull, "w")
    kwds["stderr"] = subprocess.STDOUT
    return subprocess.check_call(*args, **kwds)

def spawn(*args, **kwds):
    return subprocess.Popen(*args, **kwds).pid

def mutespawn(*args, **kwds):
    kwds["stdout"] = open(os.devnull, "w")
    kwds["stderr"] = subprocess.STDOUT
    return subprocess.Popen(*args, **kwds).pid

def detachinit():
    if os.fork():
        os._exit(0)                 # parent exits
    os.setsid()

def detach(*args, **kwds):
    kwds["preexec_fn"] = detachinit
    return subprocess.Popen(*args, **kwds).pid

def mutedetach(*args, **kwds):
    kwds["preexec_fn"] = detachinit
    kwds["stdout"] = open(os.devnull, "w")
    kwds["stderr"] = subprocess.STDOUT
    return subprocess.Popen(*args, **kwds).pid

def cmdresult(args):
    ''' Execute a command on the host and return a tuple containing the
        exit status and result string. stderr output
        is folded into the stdout result string.
    '''
    cmdid = subprocess.Popen(args, stdin = open(os.devnull, 'r'),
                             stdout = subprocess.PIPE,
                             stderr = subprocess.STDOUT)
    result, err = cmdid.communicate() # err will always be None
    status = cmdid.wait()
    return (status, result)

def hexdump(s, bytes_per_word = 2, words_per_line = 8):
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
    ''' Insert text at the end of a file, surrounded by header comments.
    '''
    filedemunge(pathname, header) # prevent duplicates
    f = open(pathname, 'a')
    f.write("# BEGIN %s\n" % header)
    f.write(text)
    f.write("# END %s\n" % header)
    f.close()

def filedemunge(pathname, header):
    ''' Remove text that was inserted in a file surrounded by header comments.
    '''
    f = open(pathname, 'r')
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
    f = open(pathname, 'w')
    lines = lines[:start] + lines[end:]
    f.write("".join(lines))
    f.close()
    
def expandcorepath(pathname, session=None, node=None):
    ''' Expand a file path given session information.
    '''
    if session is not None:
        pathname = pathname.replace('~', "/home/%s" % session.user)
        pathname = pathname.replace('%SESSION%', str(session.sessionid))
        pathname = pathname.replace('%SESSION_DIR%', session.sessiondir)
        pathname = pathname.replace('%SESSION_USER%', session.user)
    if node is not None:
        pathname = pathname.replace('%NODE%', str(node.objid))
        pathname = pathname.replace('%NODENAME%', node.name)
    return pathname
  
def sysctldevname(devname):
    ''' Translate a device name to the name used with sysctl.
    '''
    if devname is None:
        return None
    return devname.replace(".", "/")

def daemonize(rootdir = "/", umask = 0, close_fds = False, dontclose = (),
              stdin = os.devnull, stdout = os.devnull, stderr = os.devnull,
              stdoutmode = 0644, stderrmode = 0644, pidfilename = None,
              defaultmaxfd = 1024):
    ''' Run the background process as a daemon.
    '''
    if not hasattr(dontclose, "__contains__"):
        if not isinstance(dontclose, int):
            raise TypeError, "dontclose must be an integer"
        dontclose = (int(dontclose),)
    else:
        for fd in dontclose:
            if not isinstance(fd, int):
                raise TypeError, "dontclose must contain only integers"
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
        if (stdout == stderr):
            os.dup2(1, 2)
        os.close(fd)
    # redirect stderr
    if stderr and (stderr != stdout):
        fd = os.open(stderr, os.O_WRONLY | os.O_CREAT | os.O_APPEND,
                     stderrmode)
        os.dup2(fd, 2)
        os.close(fd)
    if os.fork():
        os._exit(0)                 # parent exits
    os.setsid()
    pid = os.fork()
    if pid:
        if pidfilename:
            try:
                f = open(pidfilename, "w")
                f.write("%s\n" % pid)
                f.close()
            except:
                pass
        os._exit(0)                 # parent exits
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
            except:
                pass

def readfileintodict(filename, d):
    ''' Read key=value pairs from a file, into a dict.
        Skip comments; strip newline characters and spacing.
    '''
    with open(filename, 'r') as f:
        lines = f.readlines()
    for l in lines:
        if l[:1] == '#':
            continue
        try:
            key, value = l.split('=', 1)
            d[key] = value.strip()
        except ValueError:
            pass


def checkforkernelmodule(name):
    ''' Return a string if a Linux kernel module is loaded, None otherwise.
    The string is the line from /proc/modules containing the module name,
    memory size (bytes), number of loaded instances, dependencies, state,
    and kernel memory offset.
    '''
    with open('/proc/modules', 'r') as f:
        for line in f:
            if line.startswith(name + ' '):
                return line.rstrip()
    return None
