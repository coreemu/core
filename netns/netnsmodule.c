/*
 * CORE
 * Copyright (c)2010-2012 the Boeing Company.
 * See the LICENSE file included in this distribution.
 *
 * author: Tom Goff <thomas.goff@boeing.com>
 *
 * netnsmodule.c
 *
 * Python module C bindings providing nsfork and nsexecvp methods for
 * forking a child process into a new namespace, with nsexecvp executing a
 * new program using the default search path.
 *
 */

#include <Python.h>

#include <err.h>
#include <signal.h>

#include "netns.h"

/* parts taken from python/trunk/Modules/posixmodule.c */

static void free_string_array(char **array, Py_ssize_t count)
{
  Py_ssize_t i;

  for (i = 0; i < count; i++)
    PyMem_Free(array[i]);

  PyMem_DEL(array);
}

static PyObject *netns_nsexecvp(PyObject *self, PyObject *args)
{
  pid_t pid;
  char **argv;
  Py_ssize_t i, argc;
  PyObject *(*getitem)(PyObject *, Py_ssize_t);

  /* args should be a list or tuple of strings */

  if (PyList_Check(args))
  {
    argc = PyList_Size(args);
    getitem = PyList_GetItem;
  }
  else if (PyTuple_Check(args))
  {
    argc = PyTuple_Size(args);
    getitem = PyTuple_GetItem;
  }
  else
  {
    PyErr_SetString(PyExc_TypeError,
		    "netns_nsexecvp() args must be a tuple or list");
    return NULL;
  }

  argv = PyMem_NEW(char *, argc + 1);
  if (argv == NULL)
    return PyErr_NoMemory();

  for (i = 0; i < argc; i++)
  {
    if (!PyArg_Parse((*getitem)(args, i), "et",
		     Py_FileSystemDefaultEncoding, &argv[i]))
    {
      free_string_array(argv, i);
      PyErr_SetString(PyExc_TypeError,
		      "netns_nsexecvp() args must contain only strings");
      return NULL;
    }
  }
  argv[argc] = NULL;

  pid = nsexecvp(argv);

  free_string_array(argv, argc);

  if (pid < 0)
    return PyErr_SetFromErrno(PyExc_OSError);
  else
    return PyInt_FromLong(pid);
}

static PyObject *netns_nsfork(PyObject *self, PyObject *args)
{
  int flags;
  pid_t pid;

  if (!PyArg_ParseTuple(args, "i", &flags))
    return NULL;

  pid = nsfork(flags);
  if (pid < 0)
    return PyErr_SetFromErrno(PyExc_OSError);

  if (pid == 0)			/* child */
    PyOS_AfterFork();

  return PyInt_FromLong(pid);
}

static PyMethodDef netns_methods[] = {
  {"nsfork", netns_nsfork, METH_VARARGS,
   "nsfork(cloneflags) -> int\n\n"
   "Fork a child process into a new namespace using the Linux clone()\n"
   "system call.\n\n"
   "cloneflags: additional flags passed to clone()"},

  {"nsexecvp", netns_nsexecvp, METH_VARARGS,
   "nsexecvp(args...) -> int\n\n"
   "Fork a child process into a new namespace using the Linux clone()\n"
   "system call and have the child execute a new program using the\n"
   "default search path.\n\n"
   "args: the executable file name followed by command arguments"},

  {NULL, NULL, 0, NULL},
};

PyMODINIT_FUNC initnetns(void)
{
  PyObject *m;

  m = Py_InitModule("netns", netns_methods);
  if (m == NULL)
    return;

#define MODADDINT(x)				\
  do {						\
    PyObject *tmp = Py_BuildValue("i", x);	\
    if (tmp)					\
    {						\
      Py_INCREF(tmp);				\
      PyModule_AddObject(m, #x, tmp);		\
    }						\
  } while (0)

  MODADDINT(CLONE_VFORK);

#undef MODADDINT

  return;
}
