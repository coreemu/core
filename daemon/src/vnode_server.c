/*
 * CORE
 * Copyright (c)2010-2012 the Boeing Company.
 * See the LICENSE file included in this distribution.
 *
 * author: Tom Goff <thomas.goff@boeing.com>
 *
 * vnode_server.c
 *
 */

#include <stdlib.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <string.h>
#include <limits.h>
#include <assert.h>

#include <arpa/inet.h>
#include <sys/wait.h>

#include "netns.h"
#include "myerr.h"
#include "vnode_msg.h"
#include "vnode_chnl.h"
#include "vnode_cmd.h"

#include "vnode_server.h"

extern int verbose;

static vnode_cliententry_t *vnode_server_newclient(vnode_server_t *server,
						   int fd);
static void vnode_server_delclient(vnode_cliententry_t *client);

static int cloexec(int fd)
{
  int fdflags;

  if ((fdflags = fcntl(fd, F_GETFD)) == -1)
    fdflags = 0;
  if (fcntl(fd, F_SETFD, fdflags | FD_CLOEXEC) == -1)
    return -1;

  return 0;
}

static void client_ioerror(vnode_msgio_t *msgio)
{
  vnode_cliententry_t *client = msgio->data;

  if (verbose)
    INFO("i/o error for client fd %d; deleting client", client->msgio.fd);

  vnode_server_delclient(client);

  return;
}

static vnode_cliententry_t *vnode_server_newclient(vnode_server_t *server,
						   int fd)
{
  vnode_cliententry_t *client;
  vnode_msghandler_t msghandler[VNODE_MSG_MAX] = {
    [VNODE_MSG_CMDREQ] = vnode_recv_cmdreq,
    [VNODE_MSG_CMDSIGNAL] = vnode_recv_cmdsignal,
  };

#ifdef DEBUG
  WARNX("new client on fd %d", fd);
#endif

  cloexec(fd);

  if ((client = malloc(sizeof(*client))) == NULL)
  {
    WARN("malloc() failed");
    return NULL;
  }

  client->server = server;
  client->clientfd = fd;

  TAILQ_INSERT_TAIL(&server->clientlisthead, client, entries);

  if (vnode_msgiostart(&client->msgio, server->loop,
		       client->clientfd, client, client_ioerror, msghandler))
  {
    WARNX("vnode_msgiostart() failed");
    free(client);
    return NULL;
  }

  return client;
}

static void vnode_server_delclient(vnode_cliententry_t *client)
{
#ifdef DEBUG
  WARNX("deleting client for fds %d %d", client->clientfd, client->msgio.fd);
#endif

  TAILQ_REMOVE(&client->server->clientlisthead, client, entries);
  vnode_msgiostop(&client->msgio);
  close(client->clientfd);
  memset(client, 0, sizeof(*client));
  free(client);

  return;
}

/* XXX put this in vnode_cmd.c ?? */
static void vnode_child_cb(struct ev_loop *loop, ev_child *w, int revents)
{
  vnode_server_t *server = w->data;
  vnode_cmdentry_t *cmd;
  char *how;
  int status;

#ifdef DEBUG
  WARNX("child process %d exited with status 0x%x", w->rpid, w->rstatus);
  if (WIFEXITED(w->rstatus))
    WARNX("normal terminataion status: %d", WEXITSTATUS(w->rstatus));
  else if (WIFSIGNALED(w->rstatus))
    WARNX("terminated by signal: %d", WTERMSIG(w->rstatus));
  else
    WARNX("unexpected status: %d", w->rstatus);
#endif

  if (WIFEXITED(w->rstatus))
  {
    how = "normally";
    status = WEXITSTATUS(w->rstatus);
  }
  else if (WIFSIGNALED(w->rstatus))
  {
    how = "due to signal";
    status = WTERMSIG(w->rstatus);
  }
  else
  {
    how = "for unknown reason";
    status = w->rstatus;
  }

  TAILQ_FOREACH(cmd, &server->cmdlisthead, entries)
  {
    if (cmd->pid == w->rpid)
    {
      vnode_cliententry_t *client = cmd->data;

#ifdef DEBUG
      WARNX("pid %d found in cmd list; removing", w->rpid);
#endif

      TAILQ_REMOVE(&server->cmdlisthead, cmd, entries);

      if (verbose)
	INFO("cmd completed %s: pid: %d; cmdid: %d; status %d",
	     how, w->rpid, cmd->cmdid, status);

      if (vnode_send_cmdstatus(client->clientfd, cmd->cmdid, w->rstatus))
	WARNX("vnode_send_cmdstatus() failed");

      free(cmd);

      return;
    }
  }

  WARNX("pid %d not found in client command list: "
	"completed %s with status %d", w->rpid, how, status);

  return;
}

static void vnode_server_cb(struct ev_loop *loop, ev_io *w, int revents)
{
  vnode_server_t *server = w->data;
  int fd;

  for (;;)
  {
    fd = accept(server->serverfd, NULL, NULL);
    if (fd < 0)
    {
      if (errno != EAGAIN)
	WARN("accept() failed");
      break;
    }

    if (vnode_server_newclient(server, fd) == NULL)
    {
      WARN("vnode_server_newclient() failed");
      close(fd);
    }
  }

  return;
}

static vnode_server_t *vnode_newserver(struct ev_loop *loop,
				       int ctrlfd, const char *ctrlchnlname)
{
  vnode_server_t *server;

  if ((server = malloc(sizeof(*server))) == NULL)
  {
    WARN("malloc() failed");
    return NULL;
  }

  TAILQ_INIT(&server->clientlisthead);
  TAILQ_INIT(&server->cmdlisthead);
  server->loop = loop;

  strncpy(server->ctrlchnlname, ctrlchnlname, sizeof(server->ctrlchnlname));
  server->ctrlchnlname[sizeof(server->ctrlchnlname) -1] = '\0';
  memset(server->pidfilename, 0, sizeof(server->pidfilename));
  server->serverfd = ctrlfd;

#ifdef DEBUG
  WARNX("adding vnode_child_cb for pid 0");
#endif

  server->childwatcher.data = server;
  ev_child_init(&server->childwatcher, vnode_child_cb, 0, 0);
  ev_child_start(server->loop, &server->childwatcher);

#ifdef DEBUG
  WARNX("adding vnode_server_cb for fd %d", server->serverfd);
#endif

  server->fdwatcher.data = server;
  ev_io_init(&server->fdwatcher, vnode_server_cb, server->serverfd, EV_READ);
  ev_io_start(server->loop, &server->fdwatcher);

  return server;
}

void vnode_delserver(vnode_server_t *server)
{
  unlink(server->ctrlchnlname);
  if (server->pidfilename[0] != '\0')
  {
    unlink(server->pidfilename);
  }
  ev_io_stop(server->loop, &server->fdwatcher);
  close(server->serverfd);

  ev_child_stop(server->loop, &server->childwatcher);

  while (!TAILQ_EMPTY(&server->clientlisthead))
  {
    vnode_cliententry_t *client;

    client = TAILQ_FIRST(&server->clientlisthead);
    TAILQ_REMOVE(&server->clientlisthead, client, entries);
    vnode_server_delclient(client);
  }

  while (!TAILQ_EMPTY(&server->cmdlisthead))
  {
    vnode_cmdentry_t *cmd;

    cmd = TAILQ_FIRST(&server->cmdlisthead);
    TAILQ_REMOVE(&server->cmdlisthead, cmd, entries);
    free(cmd);
  }

  memset(server, 0, sizeof(*server));
  free(server);

  return;
}

vnode_server_t *vnoded(int newnetns, const char *ctrlchnlname,
		       const char *logfilename, const char *pidfilename,
		       const char *chdirname)
{
  int ctrlfd;
  unsigned int i;
  long openmax;
  vnode_server_t *server;
  pid_t pid;

  setsid();

  if ((ctrlfd = vnode_listen(ctrlchnlname)) < 0)
  {
    WARNX("vnode_listen() failed for '%s'", ctrlchnlname);
    return NULL;
  }
  cloexec(ctrlfd);

  if (newnetns)
  {
    pid = nsfork(0);
    if (pid == -1)
    {
      WARN("nsfork() failed");
      close(ctrlfd);
      unlink(ctrlchnlname);
      return NULL;
    }
  }
  else
  {
    pid = getpid();
  }

  if (pid)
  {
    printf("%u\n", pid);
    fflush(stdout);

    if (pidfilename)
    {
      FILE *pidfile;

      pidfile = fopen(pidfilename, "w");
      if (pidfile != NULL)
      {
	fprintf(pidfile, "%u\n", pid);
	fclose(pidfile);
      }
      else
      {
	WARN("fopen() failed for '%s'", pidfilename);
      }
    }

    if (newnetns)
      _exit(0);		       /* nothing else for the parent to do */
  }

  /* try to close any open files */
  if ((openmax = sysconf(_SC_OPEN_MAX)) < 0)
    openmax = 1024;
  assert(openmax >= _POSIX_OPEN_MAX);
  for (i = 3; i < openmax; i++)
    if (i != ctrlfd)
      close(i);

  if (!logfilename)
    logfilename = "/dev/null";

#define DUPFILE(filename, mode, fileno)			\
  do {							\
    int fd;						\
    if ((fd = open(filename, mode, 0644)) == -1)	\
      WARN("open() failed for '%s'", filename);		\
    else						\
    {							\
      if (dup2(fd, fileno) == -1)			\
	WARN("dup2() failed for " #fileno);		\
      close(fd);					\
    }							\
  } while (0);

  DUPFILE("/dev/null", O_RDONLY, STDIN_FILENO);
  DUPFILE(logfilename,
	  O_WRONLY | O_CREAT | O_TRUNC | O_APPEND, STDOUT_FILENO);
  DUPFILE(logfilename,
	  O_WRONLY | O_CREAT | O_TRUNC | O_APPEND, STDERR_FILENO);

#undef DUPFILE

  setvbuf(stdout, NULL, _IOLBF, 0);
  setvbuf(stderr, NULL, _IOLBF, 0);

  if (chdirname && chdir(chdirname))
    WARN("chdir() failed");

  server = vnode_newserver(ev_default_loop(0), ctrlfd, ctrlchnlname);
  if (!server)
  {
    close(ctrlfd);
    unlink(ctrlchnlname);
  }
  if (pidfilename)
  {
    strncpy(server->pidfilename, pidfilename, sizeof(server->pidfilename));
    server->pidfilename[sizeof(server->pidfilename) -1] = '\0';
  }

  return server;
}
