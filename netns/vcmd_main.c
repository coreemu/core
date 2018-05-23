/*
 * CORE
 * Copyright (c)2010-2012 the Boeing Company.
 * See the LICENSE file included in this distribution.
 *
 * author: Tom Goff <thomas.goff@boeing.com>
 *
 * vcmd_main.c
 *
 * vcmd utility program for executing programs in an existing namespace
 * specified by the given channel.
 *
 */

#include <stdarg.h>
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include <fcntl.h>
#include <termios.h>
#include <getopt.h>

#include <sys/stat.h>
#include <sys/wait.h>
#include <sys/ioctl.h>

#include "version.h"
#include "vnode_chnl.h"
#include "vnode_cmd.h"
#include "vnode_client.h"

#include "myerr.h"

#define FORWARD_SIGNALS
#define VCMD_DEFAULT_CMD "/bin/bash"

int verbose;

typedef struct {
  vnode_client_t *client;
  vnode_client_cmdio_t *cmdio;
  int argc;
  char **argv;
  int cmdid;
  int cmdstatus;
  ev_io stdin_watcher;
  int stdin_fwdfd;
  ev_io ptymaster_watcher;
  int ptymaster_fwdfd;
} vcmd_t;

static vcmd_t vcmd;

static struct termios saveattr;
static int saveattr_set;

struct option longopts[] =
{ 
    {"version", no_argument, NULL, 'V'},
    {"help", no_argument, NULL, 'h'},
    { 0 }
};

void usage(int status, char *fmt, ...)
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
	  "Usage: %s [-h|-V] [-v] [-q|-i|-I] -c <channel name> -- command args"
	  "...\n\n"
	  "Run the specified command in the Linux namespace container "
	  "specified by the \ncontrol <channel name>, with the specified "
	  "arguments.\n\nOptions:\n"
	  "  -h, --help  show this help message and exit\n"
	  "  -V, --version  show version number and exit\n"
	  "  -v  enable verbose logging\n"
	  "  -q  run the command quietly, without local input or output\n"
	  "  -i  run the command interactively (use PTY)\n"
	  "  -I  run the command non-interactively (without PTY)\n"
	  "  -c  control channel name (e.g. '/tmp/pycore.45647/n3')\n",
	  __progname);

  va_end(ap);

  exit(status);
}

static void vcmd_rwcb(struct ev_loop *loop, ev_io *w, int revents)
{
  int outfd = *(int *)w->data;
  char buf[BUFSIZ];
  ssize_t rcount, wcount;

  rcount = read(w->fd, buf, sizeof(buf));
  if (rcount <= 0)
  {
    ev_io_stop(loop, w);
  }
  else
  {
    wcount = write(outfd, buf, rcount);
    if (wcount != rcount)
      WARN("write() error: wrote %d of %d bytes", wcount, rcount);
  }

  return;
}

static void vcmd_cmddonecb(int32_t cmdid, pid_t pid, int status, void *data)
{
  vcmd_t *vcmd = data;

  if (vcmd->cmdio->iotype == VCMD_IO_PTY)
  {
    ev_io_stop(vcmd->client->loop, &vcmd->stdin_watcher);
    ev_io_stop(vcmd->client->loop, &vcmd->ptymaster_watcher);

    /* drain command output */
    for (;;)
    {
      char buf[BUFSIZ];
      ssize_t rcount, wcount;

      rcount = read(vcmd->ptymaster_watcher.fd, buf, sizeof(buf));
      if (rcount <= 0)
	break;

      wcount = write(STDOUT_FILENO, buf, rcount);
      if (wcount != rcount)
	WARN("write() error: %d of %d bytes", wcount, rcount);
    }
  }

  vnode_close_clientcmdio(vcmd->cmdio);

#ifdef DEBUG
  WARNX("cmdid %u; pid %d; status: 0x%x", cmdid, pid, status);
#endif

  if (WIFEXITED(status))
    /* normal terminataion */
    vcmd->cmdstatus = WEXITSTATUS(status);
  else if (WIFSIGNALED(status))
  {
    if (verbose)
      INFO("command %u terminated by signal: %d", cmdid, WTERMSIG(status));
    vcmd->cmdstatus = 255;
  }
  else
  {
    INFO("unexpected termination status for command %u: 0x%x", cmdid, status);
    vcmd->cmdstatus = 255;
  }

  vcmd->cmdid = -1;

  ev_unloop(vcmd->client->loop, EVUNLOOP_ALL);

  return;
}

static void vcmd_cmdreqcb(struct ev_loop *loop, ev_timer *w, int revents)
{
  vcmd_t *vcmd = w->data;

#ifdef DEBUG
  WARNX("sending command request: serverfd %d; vcmd %p",
	vcmd->client->serverfd, vcmd);
#endif

  if (vcmd->cmdio->iotype == VCMD_IO_PTY)
  {
    /* setup forwarding i/o */

    vcmd->stdin_fwdfd = vcmd->cmdio->stdiopty.masterfd;
    vcmd->stdin_watcher.data = &vcmd->stdin_fwdfd;
    ev_io_init(&vcmd->stdin_watcher, vcmd_rwcb, STDIN_FILENO, EV_READ);
    ev_io_start(loop, &vcmd->stdin_watcher);

    vcmd->ptymaster_fwdfd = STDOUT_FILENO;
    vcmd->ptymaster_watcher.data = &vcmd->ptymaster_fwdfd;
    ev_io_init(&vcmd->ptymaster_watcher, vcmd_rwcb,
	       vcmd->cmdio->stdiopty.masterfd, EV_READ);
    ev_io_start(loop, &vcmd->ptymaster_watcher);
  }

  vcmd->cmdid = vnode_client_cmdreq(vcmd->client, vcmd->cmdio,
				    vcmd_cmddonecb, vcmd,
				    vcmd->argc, vcmd->argv);
  if (vcmd->cmdid < 0)
  {
    WARNX("vnode_client_cmdreq() failed");
    vnode_delclient(vcmd->client);
    vcmd->client = NULL;
    exit(255);
  }

  return;
}

static void vcmd_ioerrorcb(vnode_client_t *client)
{
  vcmd_t *vcmd = client->data;

  WARNX("i/o error");

  vnode_delclient(client);
  vcmd->client = NULL;

  exit(1);

  return;
}

#ifdef FORWARD_SIGNALS
static void sighandler(int signum)
{
  if (!vcmd.client || vcmd.cmdid < 0)
    return;

#ifdef DEBUG
  WARNX("sending command signal: serverfd %d; cmdid %u; signum: %d",
	vcmd.client->serverfd, vcmd.cmdid, signum);
#endif

  if (vnode_send_cmdsignal(vcmd.client->serverfd, vcmd.cmdid, signum))
    WARN("vnode_send_cmdsignal() failed");

  return;
}
#endif	/* FORWARD_SIGNALS */

static void sigwinch_handler(int signum)
{
  struct winsize wsiz;

  if (signum != SIGWINCH)
  {
    WARNX("unexpected signal number: %d", signum);
    return;
  }

  if (!vcmd.cmdio || vcmd.cmdio->iotype != VCMD_IO_PTY)
    return;

  if (ioctl(STDOUT_FILENO, TIOCGWINSZ, &wsiz))
  {
    WARN("ioctl() failed");
    return;
  }

  if (ioctl(vcmd.cmdio->stdiopty.masterfd, TIOCSWINSZ, &wsiz))
    WARN("ioctl() failed");

  return;
}

static int termioraw(int fd, struct termios *saveattr)
{
  int err;
  struct termios raw = {};

  err = tcgetattr(fd, saveattr);
  if (err)
  {
    WARN("tcgetattr() failed");
    return err;
  }

  cfmakeraw(&raw);
  err = tcsetattr(fd, TCSADRAIN, &raw);
  if (err)
  {
    WARN("tcsetattr() failed");
    return err;
  }

  return 0;
}

static void cleanup(void)
{
  if (saveattr_set)
    if (tcsetattr(STDOUT_FILENO, TCSADRAIN, &saveattr))
      WARN("tcsetattr() failed");

  return;
}

int main(int argc, char *argv[])
{
  char *ctrlchnlname = NULL;
  vnode_client_cmdiotype_t iotype = VCMD_IO_FD;
  ev_timer cmdreq;
  extern const char *__progname;
#ifdef FORWARD_SIGNALS
  int i;
  struct sigaction sig_action = {
    .sa_handler = sighandler,
  };
#endif	/* FORWARD_SIGNALS */
  char *def_argv[2] = { VCMD_DEFAULT_CMD, 0 };

  if (isatty(STDIN_FILENO) && isatty(STDOUT_FILENO) &&
      isatty(STDERR_FILENO) && getpgrp() == tcgetpgrp(STDOUT_FILENO))
    iotype = VCMD_IO_PTY;

  /* Parse command line argument list */
  for (;;)
  {
    int opt;

    if ((opt = getopt_long(argc, argv, "c:hiIqvV", longopts, NULL)) == -1)
      break;

    switch (opt)
    {
    case 'c':
      ctrlchnlname = optarg;
      break;

    case 'i':
      iotype = VCMD_IO_PTY;
      break;

    case 'I':
      iotype = VCMD_IO_FD;
      break;

    case 'q':
      iotype = VCMD_IO_NONE;
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
    usage(1, "no control channel name given");

  if (!argc)
  {
    argc = 1;
    argv = def_argv;
  }

  if (argc >= VNODE_ARGMAX)
    usage(1, "too many command arguments");

  if (atexit(cleanup))
    ERR(1, "atexit() failed");

#ifdef FORWARD_SIGNALS
  for (i = 1; i < _NSIG; i++)
  if (sigaction(i, &sig_action, NULL))
    if (verbose && i != SIGKILL && i != SIGSTOP)
      WARN("sigaction() failed for %d", i);
#endif	/* FORWARD_SIGNALS */

  vcmd.cmdio = vnode_open_clientcmdio(iotype);
  if (!vcmd.cmdio)
    ERR(1, "vnode_open_clientcmdio() failed");

  vcmd.argc = argc;
  vcmd.argv = argv;
  vcmd.cmdstatus = 255;

  switch (vcmd.cmdio->iotype)
  {
  case VCMD_IO_NONE:
    break;

  case VCMD_IO_FD:
    SET_STDIOFD(vcmd.cmdio, STDIN_FILENO, STDOUT_FILENO, STDERR_FILENO);
    break;

  case VCMD_IO_PTY:
    {
      struct sigaction sigwinch_action = {
	.sa_handler = sigwinch_handler,
      };

      if (sigaction(SIGWINCH, &sigwinch_action, NULL))
	WARN("sigaction() failed for SIGWINCH");

      sigwinch_handler(SIGWINCH);

      if (termioraw(STDOUT_FILENO, &saveattr))
	WARNX("termioraw() failed");
      else
	saveattr_set = 1;
    }
    break;

  default:
    ERR(1, "unsupported i/o type: %u", vcmd.cmdio->iotype);
    break;
  }

  vcmd.client = vnode_client(ev_default_loop(0), ctrlchnlname,
			     vcmd_ioerrorcb, &vcmd);
  if (!vcmd.client)
    ERR(1, "vnode_client() failed");

  cmdreq.data = &vcmd;
  ev_timer_init(&cmdreq, vcmd_cmdreqcb, 0, 0);
  ev_timer_start(vcmd.client->loop, &cmdreq);

  ev_loop(vcmd.client->loop, 0);

  vnode_delclient(vcmd.client);

  exit(vcmd.cmdstatus);
}
