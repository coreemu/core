/*
 * CORE
 * Copyright (c)2010-2012 the Boeing Company.
 * See the LICENSE file included in this distribution.
 *
 * author: Tom Goff <thomas.goff@boeing.com>
 *
 * vnode_client.c
 *
 *
 *
 */

#include <stdio.h>
#include <limits.h>
#include <fcntl.h>
#include <errno.h>
#include <assert.h>

#include "vnode_chnl.h"
#include "vnode_client.h"
#include "vnode_tlv.h"
#include "vnode_io.h"


extern int verbose;

typedef struct {
  vnode_client_cmddonecb_t cmddonecb;
  void *data;
} vnode_clientcmd_t;

vnode_client_cmdio_t *vnode_open_clientcmdio(vnode_client_cmdiotype_t iotype)
{
  int err;
  vnode_client_cmdio_t *clientcmdio;

  clientcmdio = malloc(sizeof(*clientcmdio));
  if (!clientcmdio)
  {
    WARN("malloc() failed");
    return NULL;
  }

  clientcmdio->iotype = iotype;

  switch (clientcmdio->iotype)
  {
  case VCMD_IO_NONE:
  case VCMD_IO_FD:
    err = 0;
    break;

  case VCMD_IO_PIPE:
    err = open_stdio_pipe(&clientcmdio->stdiopipe);
    break;

  case VCMD_IO_PTY:
    err = open_stdio_pty(&clientcmdio->stdiopty);
    break;

  default:
    WARNX("unknown i/o type: %u", clientcmdio->iotype);
    err = -1;
    break;
  }

  if (err)
  {
    free(clientcmdio);
    clientcmdio = NULL;
  }

  return clientcmdio;
}

void vnode_close_clientcmdio(vnode_client_cmdio_t *clientcmdio)
{
  switch (clientcmdio->iotype)
  {
  case VCMD_IO_NONE:
  case VCMD_IO_FD:
    break;

  case VCMD_IO_PIPE:
    close_stdio_pipe(&clientcmdio->stdiopipe);
    break;

  case VCMD_IO_PTY:
    close_stdio_pty(&clientcmdio->stdiopty);
    break;

  default:
    WARNX("unknown i/o type: %u", clientcmdio->iotype);
    break;
  }

  memset(clientcmdio, 0, sizeof(*clientcmdio));
  free(clientcmdio);

  return;
}

static void vnode_client_cmddone(vnode_cmdentry_t *cmd)
{
  vnode_clientcmd_t *clientcmd = cmd->data;;

  if (clientcmd->cmddonecb)
    clientcmd->cmddonecb(cmd->cmdid, cmd->pid, cmd->status, clientcmd->data);

  memset(clientcmd, 0, sizeof(*clientcmd));
  free(clientcmd);

  memset(cmd, 0, sizeof(*cmd));
  free(cmd);

  return;
}

static int tlv_cmdreqack_cmdid(vnode_tlv_t *tlv, void *data)
{
  vnode_cmdreqack_t *cmdreqack = data;
  int tmp;

  assert(tlv->type == VNODE_TLV_CMDID);

  tmp = tlv_int32(&cmdreqack->cmdid, tlv);

  if (tmp == 0 && verbose)
    INFO("VNODE_TLV_CMDID: %d", cmdreqack->cmdid);

  return tmp;
}

static int tlv_cmdreqack_cmdpid(vnode_tlv_t *tlv, void *data)
{
  vnode_cmdreqack_t *cmdreqack = data;
  int tmp;

  assert(tlv->type == VNODE_TLV_CMDPID);

  tmp = tlv_int32(&cmdreqack->pid, tlv);

  if (tmp == 0 && verbose)
    INFO("VNODE_TLV_CMDPID: %d", cmdreqack->pid);

  return tmp;
}

static void vnode_clientrecv_cmdreqack(vnode_msgio_t *msgio)
{
  vnode_cmdentry_t *cmd;
  vnode_client_t *client = msgio->data;
  vnode_cmdreqack_t cmdreqack = CMDREQACK_INIT;
  static const vnode_tlvhandler_t tlvhandler[VNODE_TLV_MAX] = {
    [VNODE_TLV_CMDID] = tlv_cmdreqack_cmdid,
    [VNODE_TLV_CMDPID] = tlv_cmdreqack_cmdpid,
  };

#ifdef DEBUG
  WARNX("command request ack");
#endif

  assert(msgio->msgbuf.msg->hdr.type == VNODE_MSG_CMDREQACK);

  if (vnode_parsemsg(msgio->msgbuf.msg, &cmdreqack, tlvhandler))
    return;

  TAILQ_FOREACH(cmd, &client->cmdlisthead, entries)
    if (cmd->cmdid == cmdreqack.cmdid)
      break;

  if (cmd == NULL)
  {
    WARNX("cmdid %d not found in command list", cmdreqack.cmdid);
    return;
  }

#ifdef DEBUG
  WARNX("cmdid %d found in cmd list", cmdreqack.cmdid);
#endif

  cmd->pid = cmdreqack.pid;

  if (cmdreqack.pid == -1)
  {
#ifdef DEBUG
    WARNX("XXX pid == -1 removing cmd from list");
#endif
    TAILQ_REMOVE(&client->cmdlisthead, cmd, entries);

    cmd->status = -1;
    vnode_client_cmddone(cmd);

    return;
  }

  return;
}

static int tlv_cmdstatus_cmdid(vnode_tlv_t *tlv, void *data)
{
  vnode_cmdstatus_t *cmdstatus = data;
  int tmp;

  assert(tlv->type == VNODE_TLV_CMDID);

  tmp = tlv_int32(&cmdstatus->cmdid, tlv);

  if (tmp == 0 && verbose)
    INFO("VNODE_TLV_CMDID: %d", cmdstatus->cmdid);

  return tmp;
}

static int tlv_cmdstatus_status(vnode_tlv_t *tlv, void *data)
{
  vnode_cmdstatus_t *cmdstatus = data;
  int tmp;

  assert(tlv->type == VNODE_TLV_CMDSTATUS);

  tmp = tlv_int32(&cmdstatus->status, tlv);

  if (tmp == 0 && verbose)
    INFO("VNODE_TLV_CMDSTATUS: %d", cmdstatus->status);

  return tmp;
}

static void vnode_clientrecv_cmdstatus(vnode_msgio_t *msgio)
{
  vnode_cmdentry_t *cmd;
  vnode_client_t *client = msgio->data;
  vnode_cmdstatus_t cmdstatus = CMDSTATUS_INIT;
  static const vnode_tlvhandler_t tlvhandler[VNODE_TLV_MAX] = {
    [VNODE_TLV_CMDID] = tlv_cmdstatus_cmdid,
    [VNODE_TLV_CMDSTATUS] = tlv_cmdstatus_status,
  };

#ifdef DEBUG
  WARNX("command status");
#endif

  assert(msgio->msgbuf.msg->hdr.type == VNODE_MSG_CMDSTATUS);

  if (vnode_parsemsg(msgio->msgbuf.msg, &cmdstatus, tlvhandler))
    return;

  TAILQ_FOREACH(cmd, &client->cmdlisthead, entries)
    if (cmd->cmdid == cmdstatus.cmdid)
      break;

  if (cmd == NULL)
  {
    WARNX("cmdid %d not found in command list", cmdstatus.cmdid);
    return;
  }

#ifdef DEBUG
  WARNX("cmdid %d found in cmd list; removing", cmdstatus.cmdid);
#endif
  TAILQ_REMOVE(&client->cmdlisthead, cmd, entries);

  cmd->status = cmdstatus.status;
  vnode_client_cmddone(cmd);

  return;
}

static void server_ioerror(vnode_msgio_t *msgio)
{
  vnode_client_t *client = msgio->data;

#ifdef DEBUG
  WARNX("i/o error on fd %d; client: %p", msgio->fd, client);
#endif

  if (client)
  {
    assert(msgio == &client->msgio);
    if (client->ioerrorcb)
      client->ioerrorcb(client);
  }

  return;
}

vnode_client_t *vnode_client(struct ev_loop *loop, const char *ctrlchnlname,
			     vnode_clientcb_t ioerrorcb, void *data)
{
  int fd = -1;
  vnode_client_t *client;
  static const vnode_msghandler_t msghandler[VNODE_MSG_MAX] = {
    [VNODE_MSG_CMDREQACK] = vnode_clientrecv_cmdreqack,
    [VNODE_MSG_CMDSTATUS] = vnode_clientrecv_cmdstatus,
  };

  if (!ioerrorcb)
  {
    WARNX("no i/o error callback given");
    return NULL;
  }

  fd = vnode_connect(ctrlchnlname);
  if (fd < 0)
  {
    WARN("vnode_connect() failed for '%s'", ctrlchnlname);
    return NULL;
  }

  if ((client = calloc(1, sizeof(*client))) == NULL)
  {
    WARN("calloc() failed");
    close(fd);
    return NULL;
  }

  TAILQ_INIT(&client->cmdlisthead);
  client->loop = loop;
  client->serverfd = fd;
  client->ioerrorcb = ioerrorcb;
  client->data = data;

  if (vnode_msgiostart(&client->msgio,  client->loop,
		       client->serverfd, client, server_ioerror, msghandler))
  {
    WARNX("vnode_msgiostart() failed");
    close(fd);
    return NULL;
  }

#ifdef DEBUG
  WARNX("new client connected to %s: %p", ctrlchnlname, client);
#endif

  return client;
}

void vnode_delclient(vnode_client_t *client)
{
#ifdef DEBUG
  WARNX("deleting client: %p", client);
#endif

  vnode_msgiostop(&client->msgio);
  if (client->serverfd >= 0)
  {
    close(client->serverfd);
    client->serverfd = -1;
  }

  while (!TAILQ_EMPTY(&client->cmdlisthead))
  {
    vnode_cmdentry_t *cmd;

    cmd = TAILQ_FIRST(&client->cmdlisthead);
    TAILQ_REMOVE(&client->cmdlisthead, cmd, entries);

    cmd->status = -1;
    vnode_client_cmddone(cmd);
  }

  /* XXX more stuff ?? */

  memset(client, 0, sizeof(*client));
  free(client);

  return;
}

static int vnode_setcmdio(int *cmdin, int *cmdout, int *cmderr,
			  vnode_client_cmdio_t *clientcmdio)
{
  switch (clientcmdio->iotype)
  {
  case VCMD_IO_NONE:
    *cmdin = -1;
    *cmdout = -1;
    *cmderr = -1;
    break;

  case VCMD_IO_FD:
    *cmdin = clientcmdio->stdiofd.infd;
    *cmdout = clientcmdio->stdiofd.outfd;
    *cmderr = clientcmdio->stdiofd.errfd;
    break;

  case VCMD_IO_PIPE:
    *cmdin = clientcmdio->stdiopipe.infd[0];
    *cmdout = clientcmdio->stdiopipe.outfd[1];
    *cmderr = clientcmdio->stdiopipe.errfd[1];
    break;

  case VCMD_IO_PTY:
    *cmdin = clientcmdio->stdiopty.slavefd;
    *cmdout = clientcmdio->stdiopty.slavefd;
    *cmderr = clientcmdio->stdiopty.slavefd;
    break;

  default:
    WARNX("unknown i/o type: %u", clientcmdio->iotype);
    return -1;
  }

  return 0;
}

static void vnode_cleanupcmdio(vnode_client_cmdio_t *clientcmdio)
{
#define CLOSE(var)				\
  do {						\
    if (var >= 0)				\
      close(var);				\
    var = -1;					\
  } while (0)

  switch (clientcmdio->iotype)
  {
  case VCMD_IO_NONE:
  case VCMD_IO_FD:
    break;

  case VCMD_IO_PIPE:
    CLOSE(clientcmdio->stdiopipe.infd[0]);
    CLOSE(clientcmdio->stdiopipe.outfd[1]);
    CLOSE(clientcmdio->stdiopipe.errfd[1]);
    break;

  case VCMD_IO_PTY:
    CLOSE(clientcmdio->stdiopty.slavefd);
    break;

  default:
    WARNX("unknown i/o type: %u", clientcmdio->iotype);
    break;
  }

#undef CLOSE

  return;
}

int vnode_client_cmdreq(vnode_client_t *client,
			vnode_client_cmdio_t *clientcmdio,
			vnode_client_cmddonecb_t cmddonecb, void *data,
			int argc, char *argv[])
{
  int cmdin, cmdout, cmderr;
  vnode_clientcmd_t *clientcmd;
  vnode_cmdentry_t *cmd;

  if (argc >= VNODE_ARGMAX)
  {
    WARNX("too many command arguments");
    return -1;
  }

  if (argv[argc] != NULL)
  {
    WARNX("command arguments not null-terminated");
    return -1;
  }

  if (vnode_setcmdio(&cmdin, &cmdout, &cmderr, clientcmdio))
  {
    WARNX("vnode_setcmdio() failed");
    return -1;
  }

  if ((clientcmd = malloc(sizeof(*clientcmd))) == NULL)
  {
    WARN("malloc() failed");
    return -1;
  }

  clientcmd->cmddonecb = cmddonecb;
  clientcmd->data = data;

  if ((cmd = malloc(sizeof(*cmd))) == NULL)
  {
    WARN("malloc() failed");
    free(clientcmd);
    return -1;
  }

  if (client->cmdid < 0)
    client->cmdid = 0;
  cmd->cmdid = client->cmdid++;
  cmd->pid = -1;
  cmd->status = -1;
  cmd->data = clientcmd;

  TAILQ_INSERT_TAIL(&client->cmdlisthead, cmd, entries);

  if (vnode_send_cmdreq(client->serverfd, cmd->cmdid,
			argv, cmdin, cmdout, cmderr))
  {
    WARN("vnode_send_cmdreq() failed");
    TAILQ_REMOVE(&client->cmdlisthead, cmd, entries);
    free(clientcmd);
    free(cmd);
    return -1;
  }

  vnode_cleanupcmdio(clientcmdio);

  return cmd->cmdid;
}
