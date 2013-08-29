/*
 * CORE
 * Copyright (c)2010-2012 the Boeing Company.
 * See the LICENSE file included in this distribution.
 *
 * author: Tom Goff <thomas.goff@boeing.com>
 *
 * vcmdmodule.c
 *
 * C bindings for the vcmd Python module that allows a Python script to
 * execute a program within a running namespace given by the specified channel.
 *
 */

#include <Python.h>
#include <structmember.h>
#include <pthread.h>
#include <fcntl.h>
#undef NDEBUG		      /* XXX force enabling asserts for now */
#include <assert.h>

#include "vnode_client.h"

/* #define DEBUG */

int verbose;

/* ev_default_loop(0) is not used because it interferes with SIGCHLD */
static struct ev_loop *loop;
static pthread_t evloopthread;

static TAILQ_HEAD(asyncreqhead, asyncreq) asyncreqlisthead;
static pthread_mutex_t asyncreqlist_mutex = PTHREAD_MUTEX_INITIALIZER;

static int asyncpipe[2];
static pthread_mutex_t asyncpipe_writemutex = PTHREAD_MUTEX_INITIALIZER;
static ev_io asyncwatcher;

typedef void (*asyncfunc_t)(struct ev_loop *loop, void *data);

typedef struct asyncreq {
  TAILQ_ENTRY(asyncreq) entries;

  pthread_mutex_t mutex;
  pthread_cond_t cv;
  int done;

  asyncfunc_t asyncfunc;
  void *data;
} vcmd_asyncreq_t;

static void vcmd_asyncreq_cb(struct ev_loop *loop, ev_io *w, int revents)
{
  vcmd_asyncreq_t *asyncreq;

  /* drain the event pipe */
  for (;;)
  {
    ssize_t len;
    char buf[BUFSIZ];

    len = read(asyncpipe[0], buf, sizeof(buf));
    if (len <= 0)
    {
      if (len == 0)
	ERR(1, "asynchronous event pipe closed");
      break;
    }
  }

  for (;;)
  {
    pthread_mutex_lock(&asyncreqlist_mutex);
    asyncreq = TAILQ_FIRST(&asyncreqlisthead);
    if (asyncreq)
      TAILQ_REMOVE(&asyncreqlisthead, asyncreq, entries);
    pthread_mutex_unlock(&asyncreqlist_mutex);

    if (!asyncreq)
      break;

    assert(asyncreq->asyncfunc);
    asyncreq->asyncfunc(loop, asyncreq->data);

    pthread_mutex_lock(&asyncreq->mutex);
    asyncreq->done = 1;
    pthread_cond_broadcast(&asyncreq->cv);
    pthread_mutex_unlock(&asyncreq->mutex);
  }

  return;
}

static void call_asyncfunc(asyncfunc_t asyncfunc, void *data)
{
  vcmd_asyncreq_t asyncreq = {
    .asyncfunc = asyncfunc,
    .data = data,
  };
  char zero = 0;
  ssize_t len;

  pthread_mutex_init(&asyncreq.mutex, NULL);
  pthread_cond_init(&asyncreq.cv, NULL);

  pthread_mutex_lock(&asyncreqlist_mutex);
  TAILQ_INSERT_TAIL(&asyncreqlisthead, &asyncreq, entries);
  pthread_mutex_unlock(&asyncreqlist_mutex);

  pthread_mutex_lock(&asyncpipe_writemutex);
  len = write(asyncpipe[1], &zero, sizeof(zero));
  pthread_mutex_unlock(&asyncpipe_writemutex);
  if (len == -1)
    ERR(1, "write() failed");
  if (len != sizeof(zero))
    WARN("incomplete write: %d of %d", len, sizeof(zero));

  pthread_mutex_lock(&asyncreq.mutex);
Py_BEGIN_ALLOW_THREADS
  while (!asyncreq.done)
    pthread_cond_wait(&asyncreq.cv, &asyncreq.mutex);
Py_END_ALLOW_THREADS
  pthread_mutex_unlock(&asyncreq.mutex);

  pthread_mutex_destroy(&asyncreq.mutex);
  pthread_cond_destroy(&asyncreq.cv);

  return;
}

static void *start_evloop(void *data)
{
  struct ev_loop *loop = data;

#ifdef DEBUG
  WARNX("starting event loop: %p", loop);
#endif

  ev_loop(loop, 0);

#ifdef DEBUG
  WARNX("event loop done: %p", loop);
#endif

  return NULL;
}

static int init_evloop(void)
{
  int err;

  loop = ev_loop_new(0);
  if (!loop)
  {
    WARN("ev_loop_new() failed");
    return -1;
  }

  TAILQ_INIT(&asyncreqlisthead);

  err = pipe(asyncpipe);
  if (err)
  {
    WARN("pipe() failed");
    return -1;
  }
  set_nonblock(asyncpipe[0]);
  ev_io_init(&asyncwatcher, vcmd_asyncreq_cb, asyncpipe[0], EV_READ);
  ev_io_start(loop, &asyncwatcher);

  err = pthread_create(&evloopthread, NULL, start_evloop, loop);
  if (err)
  {
    errno = err;
    WARN("pthread_create() failed");
    return -1;
  }

  return 0;
}

typedef struct {
  PyObject_HEAD

  int32_t _cmdid;
  int _complete;
  int _status;
  pthread_mutex_t _mutex;
  pthread_cond_t _cv;
} VCmdWait;

static PyObject *VCmdWait_new(PyTypeObject *type,
			      PyObject *args, PyObject *kwds)
{
  VCmdWait *self;

#ifdef DEBUG
  WARNX("enter");
#endif

  self = (VCmdWait *)type->tp_alloc(type, 0);
  if (!self)
    return NULL;

  self->_cmdid = -1;
  self->_complete = 0;
  self->_status = -1;
  pthread_mutex_init(&self->_mutex, NULL);
  pthread_cond_init(&self->_cv, NULL);

#ifdef DEBUG
  WARNX("%p: exit", self);
#endif

  return (PyObject *)self;
}

static void VCmdWait_dealloc(VCmdWait *self)
{
#ifdef DEBUG
  WARNX("%p: enter", self);
#endif

  pthread_mutex_destroy(&self->_mutex);
  pthread_cond_destroy(&self->_cv);

  self->ob_type->tp_free((PyObject *)self);

  return;
}

static PyObject *VCmdWait_wait(VCmdWait *self)
{
  int status;

  pthread_mutex_lock(&self->_mutex);

#ifdef DEBUG
  WARNX("%p: waiting for cmd %d: complete: %d; status: %d",
	self, self->_cmdid, self->_complete, self->_status);
#endif

Py_BEGIN_ALLOW_THREADS
  while (!self->_complete)
    pthread_cond_wait(&self->_cv, &self->_mutex);
Py_END_ALLOW_THREADS

  status = self->_status;

  pthread_mutex_unlock(&self->_mutex);

#ifdef DEBUG
  WARNX("%p: done waiting for cmd %d: status: %d",
	self, self->_cmdid, self->_status);
#endif

  return Py_BuildValue("i", status);
}

static PyObject *VCmdWait_complete(VCmdWait *self,
				   PyObject *args, PyObject *kwds)
{
  if (self->_complete)
    Py_RETURN_TRUE;
  else
    Py_RETURN_FALSE;
}

static PyObject *VCmdWait_status(VCmdWait *self,
				 PyObject *args, PyObject *kwds)
{
  if (self->_complete)
    return Py_BuildValue("i", self->_status);
  else
    Py_RETURN_NONE;
}

static PyMemberDef VCmdWait_members[] = {
  {NULL, 0, 0, 0, NULL},
};

static PyMethodDef VCmdWait_methods[] = {
  {"wait", (PyCFunction)VCmdWait_wait, METH_NOARGS,
   "wait() -> int\n\n"
   "Wait for command to complete and return exit status"},

  {"complete", (PyCFunction)VCmdWait_complete, METH_NOARGS,
   "complete() -> boolean\n\n"
   "Return True if command has completed; return False otherwise."},

  {"status", (PyCFunction)VCmdWait_status, METH_NOARGS,
   "status() -> int\n\n"
   "Return exit status if command has completed; return None otherwise."},

  {NULL, NULL, 0, NULL},
};

static PyTypeObject vcmd_VCmdWaitType = {
  PyObject_HEAD_INIT(NULL)
  .tp_name = "vcmd.VCmdWait",
  .tp_basicsize = sizeof(VCmdWait),
  .tp_dealloc = (destructor)VCmdWait_dealloc,
  .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
  .tp_doc = "VCmdWait objects",
  .tp_methods = VCmdWait_methods,
  .tp_members = VCmdWait_members,
  .tp_new = VCmdWait_new,
};


typedef struct vcmdentry {
  PyObject_HEAD

  vnode_client_t *_client;
  int _client_connected;
} VCmd;

static PyObject *VCmd_new(PyTypeObject *type, PyObject *args, PyObject *kwds)
{
  VCmd *self;

  self = (VCmd *)type->tp_alloc(type, 0);
  if (!self)
    return NULL;

  self->_client = NULL;
  self->_client_connected = 0;

  return (PyObject *)self;
}

static void vcmd_ioerrorcb(vnode_client_t *client)
{
  VCmd *self;
  PyGILState_STATE gstate = 0;
  int pythreads;

  pythreads = PyEval_ThreadsInitialized();
  if (pythreads)
    gstate = PyGILState_Ensure();

  if (verbose)
    WARNX("i/o error for client %p", client);

  self = client->data;

  assert(self);
  assert(self->_client == client);

  self->_client_connected = 0;

  if (pythreads)
    PyGILState_Release(gstate);

  return;
}

typedef struct {
  vnode_client_t *client;
  const char *ctrlchnlname;
  void *data;
} vcmd_newclientreq_t;

static void async_newclientreq(struct ev_loop *loop, void *data)
{
  vcmd_newclientreq_t *newclreq = data;

  newclreq->client = vnode_client(loop, newclreq->ctrlchnlname,
				  vcmd_ioerrorcb, newclreq->data);

  return;
}

typedef struct {
  vnode_client_t *client;
} vcmd_delclientreq_t;

static void async_delclientreq(struct ev_loop *loop, void *data)
{
  vcmd_delclientreq_t *delclreq = data;

  vnode_delclient(delclreq->client);

  return;
}

static int VCmd_init(VCmd *self, PyObject *args, PyObject *kwds)
{
  vcmd_newclientreq_t newclreq = {.data = self};

#ifdef DEBUG
  WARNX("%p: enter", self);
#endif

  if (!loop)
    if (init_evloop())
      return -1;

  if (!PyArg_ParseTuple(args, "s", &newclreq.ctrlchnlname))
    return -1;

  call_asyncfunc(async_newclientreq, &newclreq);
  self->_client = newclreq.client;
  if (!self->_client)
  {
    WARN("vnode_client() failed");
    PyErr_SetFromErrno(PyExc_OSError);
    return -1;
  }

 self->_client_connected = 1;

  return 0;
}

static void VCmd_dealloc(VCmd *self)
{
#ifdef DEBUG
  WARNX("%p: enter", self);
#endif

  self->_client_connected = 0;
  if (self->_client)
  {
    vcmd_delclientreq_t delclreq = {.client = self->_client};

    call_asyncfunc(async_delclientreq, &delclreq);
    self->_client = NULL;
  }

  self->ob_type->tp_free((PyObject *)self);

  return;
}

static PyObject *VCmd_connected(VCmd *self, PyObject *args, PyObject *kwds)
{
  if (self->_client_connected)
    Py_RETURN_TRUE;
  else
    Py_RETURN_FALSE;
}

static void vcmd_cmddonecb(int32_t cmdid, pid_t pid, int status, void *data)
{
  VCmdWait *cmdwait = data;
  PyGILState_STATE gstate = 0;
  int pythreads;

#ifdef DEBUG
  WARNX("cmdid %d; pid %d; status: 0x%x", cmdid, pid, status);

  if (WIFEXITED(status))
    WARNX("command %d terminated normally with status: %d",
	  cmdid, WEXITSTATUS(status));
  else if (WIFSIGNALED(status))
    WARNX("command %d terminated by signal: %d", cmdid, WTERMSIG(status));
  else
    WARNX("unexpected termination status for command %d: 0x%x", cmdid, status);
#endif

#ifdef DEBUG
  WARNX("%p: waiting for lock", cmdwait);
#endif

  pthread_mutex_lock(&cmdwait->_mutex);

  cmdwait->_status = status;
  cmdwait->_complete = 1;

#ifdef DEBUG
  WARNX("%p: command callback done", cmdwait);
#endif

  pthread_cond_broadcast(&cmdwait->_cv);
  pthread_mutex_unlock(&cmdwait->_mutex);

  pythreads = PyEval_ThreadsInitialized();
  if (pythreads)
    gstate = PyGILState_Ensure();

  Py_DECREF(cmdwait);

  if (pythreads)
    PyGILState_Release(gstate);

  return;
}

typedef struct {
  int cmdid;
  vnode_client_t *client;
  vnode_client_cmdio_t *clientcmdio;
  void *data;
  int argc;
  char **argv;
} vcmd_cmdreq_t;

static void async_cmdreq(struct ev_loop *loop, void *data)
{
  vcmd_cmdreq_t *cmdreq = data;

  cmdreq->cmdid = vnode_client_cmdreq(cmdreq->client, cmdreq->clientcmdio,
				      vcmd_cmddonecb, cmdreq->data,
				      cmdreq->argc, cmdreq->argv);

  return;
}

static void free_string_array(char **array, Py_ssize_t count)
{
  Py_ssize_t i;

  for (i = 0; i < count; i++)
    PyMem_Free(array[i]);

  PyMem_Del(array);
}

static PyObject *_VCmd_cmd(VCmd *self, PyObject *args, PyObject *kwds,
			   vnode_client_cmdiotype_t iotype)
{
  int status, infd, outfd, errfd;
  PyObject *cmdargs;
  char **argv = NULL;
  Py_ssize_t i, argc;
  PyObject *(*getitem)(PyObject *, Py_ssize_t);
  VCmdWait *cmdwait;
  vnode_client_cmdio_t *cmdio;
  PyObject *pyinfile = NULL, *pyoutfile = NULL, *pyerrfile = NULL;
  PyObject *pyptyfile = NULL;
  PyObject *ret;

  if (!self->_client_connected)
  {
    PyErr_SetString(PyExc_ValueError, "not connected");
    return NULL;
  }

  if (iotype == VCMD_IO_FD)
  {
    char *kwlist[] = {"infd", "outfd", "errfd", "args", NULL};

    status = PyArg_ParseTupleAndKeywords(args, kwds, "iiiO", kwlist,
					 &infd, &outfd, &errfd, &cmdargs);
  }
  else
  {
    char *kwlist[] = {"args", NULL};

    status = PyArg_ParseTupleAndKeywords(args, kwds, "O", kwlist, &cmdargs);
  }

  if (!status)
    return NULL;

  /* cmdargs must be a list or tuple of strings */
  if (PyList_Check(cmdargs))
  {
    argc = PyList_Size(cmdargs);
    getitem = PyList_GetItem;
  }
  else if (PyTuple_Check(cmdargs))
  {
    argc = PyTuple_Size(cmdargs);
    getitem = PyTuple_GetItem;
  }
  else
  {
    argc = -1;
  }

  if (argc <= 0)
  {
    PyErr_SetString(PyExc_TypeError,
                    "cmd arg must be a nonempty tuple or list");
    return NULL;
  }

  argv = PyMem_New(char *, argc + 1);
  if (argv == NULL)
    return PyErr_NoMemory();

  for (i = 0; i < argc; i++)
  {
    if (!PyArg_Parse((*getitem)(cmdargs, i), "et",
		     Py_FileSystemDefaultEncoding, &argv[i]))
    {
      free_string_array(argv, i);
      PyErr_SetString(PyExc_TypeError, "cmd arg must contain only strings");
      return NULL;
    }
  }
  argv[argc] = NULL;

  cmdwait = (VCmdWait *)VCmdWait_new(&vcmd_VCmdWaitType, NULL, NULL);
  if (cmdwait == NULL)
  {
    free_string_array(argv, i);
    return PyErr_NoMemory();
  }

  pthread_mutex_lock(&cmdwait->_mutex);
  cmdwait->_cmdid = -1;

  cmdio = vnode_open_clientcmdio(iotype);
  if (cmdio)
  {
    int err = 0;
    vcmd_cmdreq_t cmdreq = {
      .client = self->_client,
      .clientcmdio = cmdio,
      .data = cmdwait,
      .argc = argc,
      .argv = argv,
    };

#define PYFILE(obj, fd, name, mode)			\
    do {						\
      FILE *tmp;					\
      obj = NULL;					\
      tmp = fdopen(fd, mode);				\
      if (!tmp)						\
      {							\
	WARN("fdopen() failed for fd %d", fd);		\
	break;						\
      }							\
      obj = PyFile_FromFile(tmp, name, mode, fclose);	\
      if (!obj)						\
	fclose(tmp);					\
    } while(0)

    switch (iotype)
    {
    case VCMD_IO_NONE:
      break;

    case VCMD_IO_FD:
      SET_STDIOFD(cmdio, infd, outfd, errfd);
      break;

    case VCMD_IO_PIPE:
      PYFILE(pyinfile, cmdio->stdiopipe.infd[1], "<pipe>", "wb");
      if (!pyinfile)
      {
	err = 1;
	break;
      }
      PYFILE(pyoutfile, cmdio->stdiopipe.outfd[0], "<pipe>", "rb");
      if (!pyoutfile)
      {
	PyObject_Del(pyinfile);
	err = 1;
	break;
      }
      PYFILE(pyerrfile, cmdio->stdiopipe.errfd[0], "<pipe>", "rb");
      if (!pyerrfile)
      {
	PyObject_Del(pyoutfile);
	PyObject_Del(pyinfile);
	err = 1;
	break;
      }
      break;

    case VCMD_IO_PTY:
      PYFILE(pyptyfile, cmdio->stdiopty.masterfd, "/dev/ptmx", "r+b");
      if (!pyptyfile)
	err = 1;
      break;

    default:
      if (verbose)
	WARNX("invalid iotype: 0x%x", iotype);
      errno = EINVAL;
      err = 1;
      break;
    }

#undef PYFILE

    if (!err)
    {
      call_asyncfunc(async_cmdreq, &cmdreq);
      cmdwait->_cmdid = cmdreq.cmdid;
    }
  }

  free_string_array(argv, argc);
  free(cmdio);

  if (cmdwait->_cmdid < 0)
  {
    if (pyinfile)
      PyObject_Del(pyinfile);
    if (pyoutfile)
      PyObject_Del(pyoutfile);
    if (pyerrfile)
      PyObject_Del(pyerrfile);
    if (pyptyfile)
      PyObject_Del(pyptyfile);

    PyErr_SetFromErrno(PyExc_OSError);
    pthread_mutex_unlock(&cmdwait->_mutex);
    Py_DECREF(cmdwait);
    return NULL;
  }

  /* don't do Py_DECREF(cmdwait) or VCmdWait_dealloc(cmdwait) if
   * there's an error below since cmddonecb should still get called
   */

  switch (iotype)
  {
  case VCMD_IO_NONE:
  case VCMD_IO_FD:
    ret = Py_BuildValue("O", (PyObject *)cmdwait);
    break;

  case VCMD_IO_PIPE:
    ret = Py_BuildValue("(OOOO)", (PyObject *)cmdwait,
			pyinfile, pyoutfile, pyerrfile);
    break;

  case VCMD_IO_PTY:
    ret = Py_BuildValue("(OO)", (PyObject *)cmdwait, pyptyfile);
    break;

  default:
    ret = NULL;
    break;
  }

  pthread_mutex_unlock(&cmdwait->_mutex);

  return ret;
}

static PyObject *VCmd_qcmd(VCmd *self, PyObject *args, PyObject *kwds)
{
  return _VCmd_cmd(self, args, kwds, VCMD_IO_NONE);
}

static PyObject *VCmd_redircmd(VCmd *self, PyObject *args, PyObject *kwds)
{
  return _VCmd_cmd(self, args, kwds, VCMD_IO_FD);
}

static PyObject *VCmd_popen(VCmd *self, PyObject *args, PyObject *kwds)
{
  return _VCmd_cmd(self, args, kwds, VCMD_IO_PIPE);
}

static PyObject *VCmd_ptyopen(VCmd *self, PyObject *args, PyObject *kwds)
{
  return _VCmd_cmd(self, args, kwds, VCMD_IO_PTY);
}

static PyObject *VCmd_kill(VCmd *self, PyObject *args, PyObject *kwds)
{
  VCmdWait *cmdwait;
  int sig;

  if (!PyArg_ParseTuple(args, "O!i", &vcmd_VCmdWaitType, &cmdwait, &sig))
    return NULL;

  if (cmdwait->_complete)
  {
    PyErr_SetString(PyExc_ValueError, "command already complete");
    return NULL;
  }

  if (vnode_send_cmdsignal(self->_client->serverfd, cmdwait->_cmdid, sig))
  {
    PyErr_SetFromErrno(PyExc_OSError);
    return NULL;
  }

  Py_RETURN_NONE;
}

static PyMemberDef VCmd_members[] = {
  {NULL, 0, 0, 0, NULL},
};

static PyMethodDef VCmd_methods[] = {
  {"connected", (PyCFunction)VCmd_connected, METH_NOARGS,
   "connected() -> boolean\n\n"
   "returns True if connected; False otherwise"},

  {"popen", (PyCFunction)VCmd_popen, METH_VARARGS | METH_KEYWORDS,
   "popen(args...) -> (VCmdWait, cmdin, cmdout, cmderr)\n\n"
   "Send command request and use pipe I/O.\n\n"
   "args: executable file name followed by command arguments"},

  {"ptyopen", (PyCFunction)VCmd_ptyopen, METH_VARARGS| METH_KEYWORDS,
   "ptyopen(args...) -> (VCmdWait, cmdpty)\n\n"
   "Send command request and use pty I/O.\n\n"
   "args: executable file name followed by command arguments"},

  {"qcmd", (PyCFunction)VCmd_qcmd, METH_VARARGS | METH_KEYWORDS,
   "qcmd(args...) -> VCmdWait\n\n"
   "Send command request without I/O.\n\n"
   "args: executable file name followed by command arguments"},

  {"redircmd", (PyCFunction)VCmd_redircmd, METH_VARARGS | METH_KEYWORDS,
   "redircmd(infd, outfd, errfd, args...) -> VCmdWait\n\n"
   "Send command request with I/O redirected from/to the given fds.\n\n"
   "infd:  file descriptor for command standard input\n"
   "outfd: file descriptor for command standard output\n"
   "errfd: file descriptor for command standard error\n"
   "args:  executable file name followed by command arguments"},

  {"kill", (PyCFunction)VCmd_kill, METH_VARARGS,
   "kill(cmdwait, signum) -> None\n\n"
   "Send signal to a command.\n\n"
   "cmdwait: the VCmdWait object from an earlier command request\n"
   "signum: the signal to send"},

  {NULL, NULL, 0, NULL},
};

static PyTypeObject vcmd_VCmdType = {
  PyObject_HEAD_INIT(NULL)
  .tp_name = "vcmd.VCmd",
  .tp_basicsize = sizeof(VCmd),
  .tp_dealloc = (destructor)VCmd_dealloc,
  .tp_flags = Py_TPFLAGS_DEFAULT | Py_TPFLAGS_BASETYPE,
  .tp_doc = "VCmd objects",
  .tp_methods = VCmd_methods,
  .tp_members = VCmd_members,
  .tp_init = (initproc)VCmd_init,
  .tp_new = VCmd_new,
};

static PyObject *vcmd_verbose(PyObject *self, PyObject *args)
{
  int oldval = verbose;

  if (!PyArg_ParseTuple(args, "|i", &verbose))
    return NULL;

  return Py_BuildValue("i", oldval);
}

static PyMethodDef vcmd_methods[] = {
  {"verbose", (PyCFunction)vcmd_verbose, METH_VARARGS,
   "verbose([newval]) -> int\n\n"
   "Get the current verbose level and optionally set it to newval."},

  {NULL, NULL, 0, NULL},
};

PyMODINIT_FUNC initvcmd(void)
{
  PyObject *m;

  if (PyType_Ready(&vcmd_VCmdType) < 0)
    return;

  if (PyType_Ready(&vcmd_VCmdWaitType) < 0)
    return;

  m = Py_InitModule3("vcmd", vcmd_methods, "vcmd module that does stuff...");
  if (!m)
    return;

  Py_INCREF(&vcmd_VCmdType);
  PyModule_AddObject(m, "VCmd", (PyObject *)&vcmd_VCmdType);

  Py_INCREF(&vcmd_VCmdWaitType);
  PyModule_AddObject(m, "VCmdWait", (PyObject *)&vcmd_VCmdWaitType);

  return;
}
