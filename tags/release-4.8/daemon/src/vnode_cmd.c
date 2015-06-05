/*
 * CORE
 * Copyright (c)2010-2012 the Boeing Company.
 * See the LICENSE file included in this distribution.
 *
 * author: Tom Goff <thomas.goff@boeing.com>
 *
 * vnode_cmd.c
 *
 */

#include <fcntl.h>
#include <string.h>
#include <assert.h>

#include <arpa/inet.h>
#include <sys/ioctl.h>

#include "myerr.h"
#include "vnode_msg.h"
#include "vnode_server.h"
#include "vnode_tlv.h"
#include "vnode_io.h"

#include "vnode_cmd.h"

extern int verbose;

static void vnode_process_cmdreq(vnode_cliententry_t *client,
				 vnode_cmdreq_t *cmdreq);

static int tlv_cmdreq_cmdid(vnode_tlv_t *tlv, void *data)
{
  vnode_cmdreq_t *cmdreq = data;
  int tmp;

  assert(tlv->type == VNODE_TLV_CMDID);

  tmp = tlv_int32(&cmdreq->cmdid, tlv);

  if (tmp == 0 && verbose)
    INFO("VNODE_TLV_CMDID: %u", cmdreq->cmdid);

  return tmp;
}

static int tlv_cmdreq_cmdarg(vnode_tlv_t *tlv, void *data)
{
  vnode_cmdreq_t *cmdreq = data;
  int i, tmp;

  assert(tlv->type == VNODE_TLV_CMDARG);

#define CMDARGMAX (sizeof(cmdreq->cmdarg) / sizeof(cmdreq->cmdarg[0]))

  for (i = 0; i < CMDARGMAX; i++)
    if (cmdreq->cmdarg[i] == NULL)
      break;

  if (i == CMDARGMAX)
  {
    WARNX("too many command arguments");
    return -1;
  }

#undef CMDARGMAX

  tmp = tlv_string(&cmdreq->cmdarg[i], tlv);

  if (tmp == 0 && verbose)
    INFO("VNODE_TLV_CMDARG: '%s'", cmdreq->cmdarg[i]);

  return tmp;
}

void vnode_recv_cmdreq(vnode_msgio_t *msgio)
{
  vnode_cliententry_t *client = msgio->data;
  vnode_cmdreq_t cmdreq = CMDREQ_INIT;
  static vnode_tlvhandler_t cmdreq_tlvhandler[VNODE_TLV_MAX] = {
    [VNODE_TLV_CMDID] = tlv_cmdreq_cmdid,
    [VNODE_TLV_CMDARG] = tlv_cmdreq_cmdarg,
  };

#ifdef DEBUG
  WARNX("command request");
#endif

  assert(msgio->msgbuf.msg->hdr.type == VNODE_MSG_CMDREQ);

  if (vnode_parsemsg(msgio->msgbuf.msg, &cmdreq, cmdreq_tlvhandler))
    return;

  cmdreq.cmdio.infd = msgio->msgbuf.infd;
  cmdreq.cmdio.outfd = msgio->msgbuf.outfd;
  cmdreq.cmdio.errfd = msgio->msgbuf.errfd;

  vnode_process_cmdreq(client, &cmdreq);

  return;
}

int vnode_send_cmdreq(int fd, int32_t cmdid, char *argv[],
		      int infd, int outfd, int errfd)
{
  size_t offset = 0;
  vnode_msgbuf_t msgbuf;
  char **cmdarg;
  int tmp;

  if (vnode_initmsgbuf(&msgbuf))
    return -1;

#define ADDTLV(t, l, vp)				\
  do {							\
    ssize_t tlvlen;					\
    tlvlen = vnode_addtlv(&msgbuf, offset, t, l, vp);	\
    if (tlvlen < 0)					\
    {							\
      WARNX("vnode_addtlv() failed");			\
      FREE_MSGBUF(&msgbuf);				\
      return -1;					\
    }							\
    offset += tlvlen;					\
  } while (0)

  ADDTLV(VNODE_TLV_CMDID, sizeof(cmdid), &cmdid);

  for (cmdarg = argv; *cmdarg; cmdarg++)
    ADDTLV(VNODE_TLV_CMDARG, strlen(*cmdarg) + 1, *cmdarg);

#undef ADDTLV

  msgbuf.infd = infd;
  msgbuf.outfd = outfd;
  msgbuf.errfd = errfd;

#ifdef DEBUG
  WARNX("sending cmd req on fd %d: cmd '%s'", fd, argv[0]);
#endif

  msgbuf.msg->hdr.type = VNODE_MSG_CMDREQ;
  msgbuf.msg->hdr.datalen = offset;
  if (vnode_sendmsg(fd, &msgbuf) == vnode_msglen(&msgbuf))
    tmp = 0;
  else
    tmp = -1;

  FREE_MSGBUF(&msgbuf);

  return tmp;
}

int vnode_send_cmdreqack(int fd, int32_t cmdid, int32_t pid)
{
  ssize_t tmp = -1;
  size_t offset = 0;
  vnode_msgbuf_t msgbuf;

  if (vnode_initmsgbuf(&msgbuf))
    return -1;

#define ADDTLV(t, l, vp)				\
  do {							\
    ssize_t tlvlen;					\
    tlvlen = vnode_addtlv(&msgbuf, offset, t, l, vp);	\
    if (tlvlen < 0)					\
    {							\
      WARNX("vnode_addtlv() failed");			\
      FREE_MSGBUF(&msgbuf);				\
      return -1;					\
    }							\
    offset += tlvlen;					\
  } while (0)

  ADDTLV(VNODE_TLV_CMDID, sizeof(cmdid), &cmdid);
  ADDTLV(VNODE_TLV_CMDPID, sizeof(pid), &pid);

#undef ADDTLV

#ifdef DEBUG
  WARNX("sending cmd req ack on fd %d: cmdid %d; pid %d", fd, cmdid, pid);
#endif

  msgbuf.msg->hdr.type = VNODE_MSG_CMDREQACK;
  msgbuf.msg->hdr.datalen = offset;
  if (vnode_sendmsg(fd, &msgbuf) == vnode_msglen(&msgbuf))
    tmp = 0;

  FREE_MSGBUF(&msgbuf);

  return tmp;
}

int vnode_send_cmdstatus(int fd, int32_t cmdid, int32_t status)
{
  int tmp;
  size_t offset = 0;
  vnode_msgbuf_t msgbuf;

  if (vnode_initmsgbuf(&msgbuf))
    return -1;

#define ADDTLV(t, l, vp)				\
  do {							\
    ssize_t tlvlen;					\
    tlvlen = vnode_addtlv(&msgbuf, offset, t, l, vp);	\
    if (tlvlen < 0)					\
    {							\
      WARNX("vnode_addtlv() failed");			\
      FREE_MSGBUF(&msgbuf);				\
      return -1;					\
    }							\
    offset += tlvlen;					\
  } while (0)

  ADDTLV(VNODE_TLV_CMDID, sizeof(cmdid), &cmdid);
  ADDTLV(VNODE_TLV_CMDSTATUS, sizeof(status), &status);

#undef ADDTLV

#ifdef DEBUG
  WARNX("sending cmd status on fd %d: cmdid %d; status %d",
	fd, cmdid, status);
#endif

  msgbuf.msg->hdr.type = VNODE_MSG_CMDSTATUS;
  msgbuf.msg->hdr.datalen = offset;
  if (vnode_sendmsg(fd, &msgbuf) == vnode_msglen(&msgbuf))
    tmp = 0;
  else
    tmp = -1;

  FREE_MSGBUF(&msgbuf);

  return tmp;
}

int vnode_send_cmdsignal(int fd, int32_t cmdid, int32_t signum)
{
  ssize_t tmp;
  size_t offset = 0;
  vnode_msgbuf_t msgbuf;

  if (vnode_initmsgbuf(&msgbuf))
    return -1;

#define ADDTLV(t, l, vp)				\
  do {							\
    ssize_t tlvlen;					\
    tlvlen = vnode_addtlv(&msgbuf, offset, t, l, vp);	\
    if (tlvlen < 0)					\
    {							\
      WARNX("vnode_addtlv() failed");			\
      FREE_MSGBUF(&msgbuf);				\
      return -1;					\
    }							\
    offset += tlvlen;					\
  } while (0)

  ADDTLV(VNODE_TLV_CMDID, sizeof(cmdid), &cmdid);
  ADDTLV(VNODE_TLV_SIGNUM, sizeof(signum), &signum);

#undef ADDTLV

#ifdef DEBUG
  WARNX("sending cmd signal on fd %d: cmdid %d; signum %d",
	fd, cmdid, signum);
#endif

  msgbuf.msg->hdr.type = VNODE_MSG_CMDSIGNAL;
  msgbuf.msg->hdr.datalen = offset;
  if (vnode_sendmsg(fd, &msgbuf) == vnode_msglen(&msgbuf))
    tmp = 0;
  else
    tmp = -1;

  FREE_MSGBUF(&msgbuf);

  return tmp;
}

static int tlv_cmdsignal_cmdid(vnode_tlv_t *tlv, void *data)
{
  vnode_cmdsignal_t *cmdsignal = data;
  int tmp;

  assert(tlv->type == VNODE_TLV_CMDID);

  tmp = tlv_int32(&cmdsignal->cmdid, tlv);

  if (tmp == 0 && verbose)
    INFO("VNODE_TLV_CMDID: %d", cmdsignal->cmdid);

  return tmp;
}

static int tlv_cmdsignal_signum(vnode_tlv_t *tlv, void *data)
{
  vnode_cmdsignal_t *cmdsignal = data;
  int tmp;

  assert(tlv->type == VNODE_TLV_SIGNUM);

  tmp = tlv_int32(&cmdsignal->signum, tlv);

  if (tmp == 0 && verbose)
    INFO("VNODE_TLV_SIGNUM: %d", cmdsignal->signum);

  return tmp;
}

void vnode_recv_cmdsignal(vnode_msgio_t *msgio)
{
  vnode_cliententry_t *client = msgio->data;
  vnode_cmdsignal_t cmdsignal = CMDSIGNAL_INIT;
  static vnode_tlvhandler_t cmdsignal_tlvhandler[VNODE_TLV_MAX] = {
    [VNODE_TLV_CMDID] = tlv_cmdsignal_cmdid,
    [VNODE_TLV_SIGNUM] = tlv_cmdsignal_signum,
  };
  vnode_cmdentry_t *cmd;

#ifdef DEBUG
  WARNX("command signal");
#endif

  assert(msgio->msgbuf.msg->hdr.type == VNODE_MSG_CMDSIGNAL);

  if (vnode_parsemsg(msgio->msgbuf.msg, &cmdsignal, cmdsignal_tlvhandler))
    return;


  TAILQ_FOREACH(cmd, &client->server->cmdlisthead, entries)
  {
    if (cmd->cmdid == cmdsignal.cmdid && cmd->data == client)
    {
      if (verbose)
	INFO("sending pid %u signal %u", cmd->pid, cmdsignal.signum);

      if (kill(cmd->pid, cmdsignal.signum))
	WARN("kill() failed");

      break;
    }
  }

  if (cmd == NULL)
    WARNX("cmdid %d not found for client %p", cmdsignal.cmdid, client);

  return;
}

static pid_t forkexec(vnode_cmdreq_t *cmdreq)
{
  pid_t pid;

  if (verbose)
    INFO("spawning '%s'", cmdreq->cmdarg[0]);

  pid = fork();
  switch (pid)
  {
  case -1:
    WARN("fork() failed");
    break;

  case 0:
    /* child */
    if (setsid() == -1)
      WARN("setsid() failed");

#define DUP2(oldfd, newfd)			\
    do {					\
      if (oldfd >= 0)				\
	if (dup2(oldfd, newfd) < 0)		\
	{					\
	  WARN("dup2() failed for " #newfd	\
	       ": oldfd: %d; newfd: %d",	\
	       oldfd, newfd);			\
	  _exit(1);				\
	}					\
    } while (0)

    DUP2(cmdreq->cmdio.infd, STDIN_FILENO);
    DUP2(cmdreq->cmdio.outfd, STDOUT_FILENO);
    DUP2(cmdreq->cmdio.errfd, STDERR_FILENO);

#undef DUP2

#define CLOSE_IF_NOT(fd, notfd)			\
    do {					\
      if (fd >= 0 && fd != notfd)		\
	close(fd);				\
    } while (0)

    CLOSE_IF_NOT(cmdreq->cmdio.infd, STDIN_FILENO);
    CLOSE_IF_NOT(cmdreq->cmdio.outfd, STDOUT_FILENO);
    CLOSE_IF_NOT(cmdreq->cmdio.errfd, STDERR_FILENO);

#undef CLOSE_IF_NOT

    if (clear_nonblock(STDIN_FILENO))
      WARN("clear_nonblock() failed");
    if (clear_nonblock(STDOUT_FILENO))
      WARN("clear_nonblock() failed");
    if (clear_nonblock(STDERR_FILENO))
      WARN("clear_nonblock() failed");

    /* try to get a controlling terminal (don't steal a terminal and
       ignore errors) */
    if (isatty(STDIN_FILENO))
      ioctl(STDIN_FILENO, TIOCSCTTY, 0);
    else if (isatty(STDOUT_FILENO))
      ioctl(STDOUT_FILENO, TIOCSCTTY, 0);

    execvp(cmdreq->cmdarg[0], cmdreq->cmdarg);
    WARN("execvp() failed for '%s'", cmdreq->cmdarg[0]);
    _exit(1);
    break;

  default:
    /* parent */
    break;
  }

#define CLOSE(fd)				\
  do {						\
    if (fd >= 0)				\
      close(fd);				\
  } while (0)

  CLOSE(cmdreq->cmdio.infd);
  CLOSE(cmdreq->cmdio.outfd);
  CLOSE(cmdreq->cmdio.errfd);

#undef CLOSE

  return pid;
}

static void vnode_process_cmdreq(vnode_cliententry_t *client,
				 vnode_cmdreq_t *cmdreq)
{
  vnode_cmdentry_t *cmd = NULL;

  if ((cmd = malloc(sizeof(*cmd))) == NULL)
  {
    WARN("malloc() failed");
    return;
  }

  cmd->cmdid = cmdreq->cmdid;
  cmd->pid = -1;
  cmd->status = -1;
  cmd->data = client;
  cmd->pid = forkexec(cmdreq);

  if (verbose)
    INFO("cmd: '%s'; pid: %d; cmdid: %d; "
	 "infd: %d; outfd: %d; errfd: %d",
	 cmdreq->cmdarg[0], cmd->pid, cmd->cmdid,
	 cmdreq->cmdio.infd, cmdreq->cmdio.outfd, cmdreq->cmdio.errfd);

  if (vnode_send_cmdreqack(client->clientfd, cmd->cmdid, cmd->pid))
  {
    WARNX("vnode_send_cmdreqack() failed");
    // XXX if (cmd->pid != -1) kill(cmd->pid, SIGKILL); ?
    free(cmd);
    return;
  }

  if (cmd->pid == -1)
    free(cmd);
  else
  {
#ifdef DEBUG
    WARNX("adding pid %d to cmd list", cmd->pid);
#endif
    TAILQ_INSERT_TAIL(&client->server->cmdlisthead, cmd, entries);
  }

  return;
}
