/*
 * CORE
 * Copyright (c)2010-2012 the Boeing Company.
 * See the LICENSE file included in this distribution.
 *
 * author: Tom Goff <thomas.goff@boeing.com>
 *
 * vnoded_main.c
 *
 * vnoded daemon runs as PID 1 in the Linux namespace container and receives
 * and executes commands via a control channel.
 *
 */

#include <stdio.h>
#include <stdarg.h>
#include <unistd.h>
#include <stdlib.h>
#include <getopt.h>

#include <sys/wait.h>

#include "version.h"
#include "vnode_server.h"
#include "myerr.h"

int verbose;

static vnode_server_t *vnodeserver;

struct option longopts[] =
{ 
    {"version", no_argument, NULL, 'V'},
    {"help", no_argument, NULL, 'h'},
    { 0 }
};

static void usage(int status, char *fmt, ...)
{
  extern const char *__progname;
  va_list ap;
  FILE *output;

  va_start(ap, fmt);

  output = status ? stderr : stdout;
  fprintf(output, "\n");
  if (fmt != NULL)
  {
    vfprintf(output, fmt, ap);
    fprintf(output, "\n\n");
  }
  fprintf(output,
	  "Usage: %s [-h|-V] [-v] [-n] [-C <chdir>] [-l <logfile>] "
	  "[-p <pidfile>] -c <control channel>\n\n"
	  "Linux namespace container server daemon runs as PID 1 in the "
	  "container. \nNormally this process is launched automatically by the "
	  "CORE daemon.\n\nOptions:\n"
	  "  -h, --help  show this help message and exit\n"
	  "  -V, --version  show version number and exit\n"
	  "  -v  enable verbose logging\n"
	  "  -n  do not create and run daemon within a new network namespace "
	  "(for debug)\n"
	  "  -C  change to the specified <chdir> directory\n"
	  "  -l  log output to the specified <logfile> file\n"
	  "  -p  write process id to the specified <pidfile> file\n"
	  "  -c  establish the specified <control channel> for receiving "
	  "control commands\n",
	  __progname);

  va_end(ap);

  exit(0);
}

static void sigexit(int signum)
{
  WARNX("exiting due to signal: %d", signum);
  exit(0);
  return;
}

static void cleanup_sigchld(int signum)
{
  /* nothing */
}

static void cleanup()
{
  static int incleanup = 0;

  if (incleanup)
    return;
  incleanup = 1;

  if (vnodeserver)
  {
    struct ev_loop *loop = vnodeserver->loop;
    vnode_delserver(vnodeserver);
    if (loop)
      ev_unloop(loop, EVUNLOOP_ALL);
  }

  /* don't use SIG_IGN here because receiving SIGCHLD is needed to
   * interrupt the sleep below in order to avoid long delays
   */
  if (signal(SIGCHLD, cleanup_sigchld) == SIG_ERR)
    WARN("signal() failed");

  if (getpid() == 1)
  {
    struct timespec delay = {
      .tv_sec = 2,
      .tv_nsec = 0,
    };

    /* try to gracefully terminate all processes in this namespace
     * first
     */
    kill(-1, SIGTERM);
    /* wait for child processes to terminate */
    for (;;)
    {
      pid_t pid;
      int err;
      struct timespec rem;

      pid = waitpid(-1, NULL, WNOHANG);
      if (pid == -1)
	break;			/* an error occurred */
      if (pid != 0)
	continue;		/* a child was reaped */

      err = nanosleep(&delay, &rem);
      if (err == -1 && errno == EINTR)
      {
	delay = rem;
	continue;
      }

      /* force termination after delay */
      kill(-1, SIGKILL);
      break;
    }
  }

  return;
}

int main(int argc, char *argv[])
{
  int newnetns = 1;
  char *ctrlchnlname = NULL, *logfilename = NULL, *chdirname = NULL;
  char *pidfilename = NULL;
  extern const char *__progname;

  for (;;)
  {
    int opt;

    if ((opt = getopt_long(argc, argv, "c:C:l:nvVhp:", longopts, NULL)) == -1)
      break;

    switch (opt)
    {
    case 'c':
      ctrlchnlname = optarg;
      break;

    case 'C':
      chdirname = optarg;
      break;

    case 'l':
      logfilename = optarg;
      break;

    case 'n':
      newnetns = 0;
      break;

    case 'p':
      pidfilename = optarg;
      break;

    case 'v':
      verbose++;
      break;

    case 'V':
      printf("%s version %s\n", __progname, CORE_VERSION);
      exit(0);

    case 'h':
      /* pass through */
    default:
      usage(0, NULL);
    }
  }

  argc -= optind;
  argv += optind;

  if (ctrlchnlname == NULL)
    usage(1, "no control channel given");

  for (; argc; argc--, argv++)
    WARNX("ignoring command line argument: '%s'", *argv);

  if (atexit(cleanup))
    ERR(1, "atexit() failed");

  if (signal(SIGTERM, sigexit) == SIG_ERR)
    ERR(1, "signal() failed");
  if (signal(SIGINT, sigexit) == SIG_ERR)
    ERR(1, "signal() failed");
  /* XXX others? */

  vnodeserver = vnoded(newnetns, ctrlchnlname, logfilename, pidfilename,
		       chdirname);
  if (vnodeserver == NULL)
    ERRX(1, "vnoded() failed");

  ev_loop(vnodeserver->loop, 0);

  exit(0);
}
