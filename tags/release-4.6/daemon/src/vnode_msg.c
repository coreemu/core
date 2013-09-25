/*
 * CORE
 * Copyright (c)2010-2012 the Boeing Company.
 * See the LICENSE file included in this distribution.
 *
 * author: Tom Goff <thomas.goff@boeing.com>
 *
 * vnode_msg.c
 *
 */

#include <stdlib.h>
#include <errno.h>
#include <assert.h>
#include <string.h>

#include <arpa/inet.h>

#include "myerr.h"

#include "vnode_msg.h"


static void vnode_msg_cb(struct ev_loop *loop, ev_io *w, int revents)
{
  vnode_msgio_t *msgio = w->data;
  ssize_t tmp;
  vnode_msghandler_t msghandlefn;

#ifdef DEBUG
  WARNX("new message on fd %d", msgio->fd);
#endif

  assert(msgio);

  tmp = vnode_recvmsg(msgio);
  if (tmp == 0)
    return;
  else if (tmp < 0)
  {
    ev_io_stop(loop, w);
    if (msgio->ioerror)
      msgio->ioerror(msgio);
    return;
  }

  msghandlefn = msgio->msghandler[msgio->msgbuf.msg->hdr.type];
  if (!msghandlefn)
  {
    WARNX("no handler found for msg type %u from fd %d",
	  msgio->msgbuf.msg->hdr.type, msgio->fd);
    return;
  }

  msghandlefn(msgio);

  return;
}

ssize_t vnode_sendmsg(int fd, vnode_msgbuf_t *msgbuf)
{
  struct msghdr msg = {};
  struct iovec iov[1];
  char buf[CMSG_SPACE(3 * sizeof(int))];

  iov[0].iov_base = msgbuf->msg;
  iov[0].iov_len = vnode_msglen(msgbuf);
  msg.msg_iov = iov;
  msg.msg_iovlen = 1;

  if (msgbuf->infd >= 0)
  {
    struct cmsghdr *cmsg;
    int *fdptr;

    assert(msgbuf->outfd >= 0);
    assert(msgbuf->errfd >= 0);

    msg.msg_control = buf;
    msg.msg_controllen = sizeof(buf);

    cmsg = CMSG_FIRSTHDR(&msg);
    cmsg->cmsg_level = SOL_SOCKET;
    cmsg->cmsg_type = SCM_RIGHTS;
    cmsg->cmsg_len = CMSG_LEN(3 * sizeof(int));

    fdptr = (int *)CMSG_DATA(cmsg);
    fdptr[0] = msgbuf->infd;
    fdptr[1] = msgbuf->outfd;
    fdptr[2] = msgbuf->errfd;

    msg.msg_controllen = cmsg->cmsg_len;
  }

  return sendmsg(fd, &msg, 0);
}

/*
 * return the number of bytes received
 * return 0 if the message should be ignored
 * return a negative value if i/o should stop
 */
ssize_t vnode_recvmsg(vnode_msgio_t *msgio)
{
  ssize_t recvlen;
  struct msghdr msg = {};
  struct iovec iov[1];
  char buf[CMSG_SPACE(3 * sizeof(int))];
  struct cmsghdr *cmsg;

  if (msgio->msgbuf.msgbufsize < VNODE_MSGSIZMAX)
  {
    if (vnode_resizemsgbuf(&msgio->msgbuf, VNODE_MSGSIZMAX))
      return -1;
  }

  msgio->msgbuf.infd = msgio->msgbuf.outfd = msgio->msgbuf.errfd = -1;

  iov[0].iov_base = msgio->msgbuf.msg;
  iov[0].iov_len = msgio->msgbuf.msgbufsize;
  msg.msg_iov = iov;
  msg.msg_iovlen = 1;
  msg.msg_control = buf;
  msg.msg_controllen = sizeof(buf);

  recvlen = recvmsg(msgio->fd, &msg, 0);
  if (recvlen == 0)
    return -1;
  else if (recvlen < 0)
  {
    if (errno == EAGAIN)
      return 0;
    WARN("recvmsg() failed");
    return -1;
  }

  cmsg = CMSG_FIRSTHDR(&msg);
  if (cmsg != NULL && cmsg->cmsg_type == SCM_RIGHTS)
  {
    int *fdptr;

    fdptr = (int *)CMSG_DATA(cmsg);
    msgio->msgbuf.infd = fdptr[0];
    msgio->msgbuf.outfd = fdptr[1];
    msgio->msgbuf.errfd = fdptr[2];
  }

  if (recvlen < sizeof(msgio->msgbuf.msg->hdr))
  {
    WARNX("message header truncated: received %d of %d bytes",
	  recvlen, sizeof(msgio->msgbuf.msg->hdr));
    return 0;
  }

  if (msgio->msgbuf.msg->hdr.type == VNODE_MSG_NONE ||
      msgio->msgbuf.msg->hdr.type >= VNODE_MSG_MAX)
  {
    WARNX("invalid message type: %u", msgio->msgbuf.msg->hdr.type);
    return 0;
  }

  if (recvlen - sizeof(msgio->msgbuf.msg->hdr) !=
      msgio->msgbuf.msg->hdr.datalen)
  {
    WARNX("message length mismatch: received %d bytes; expected %d bytes",
	  recvlen - sizeof(msgio->msgbuf.msg->hdr),
	  msgio->msgbuf.msg->hdr.datalen);
    return 0;
  }

  return recvlen;
}

int vnode_msgiostart(vnode_msgio_t *msgio, struct ev_loop *loop,
		     int fd, void *data, vnode_msghandler_t ioerror,
		     const vnode_msghandler_t msghandler[VNODE_MSG_MAX])
{
#ifdef DEBUG
  WARNX("starting message i/o for fd %d", fd);
#endif

  if (vnode_initmsgbuf(&msgio->msgbuf))
    return -1;

  msgio->loop = loop;
  msgio->fd = fd;
  msgio->fdwatcher.data = msgio;
  ev_io_init(&msgio->fdwatcher, vnode_msg_cb, fd, EV_READ);
  msgio->data = data;
  msgio->ioerror = ioerror;
  memcpy(msgio->msghandler, msghandler, sizeof(msgio->msghandler));

  ev_io_start(msgio->loop, &msgio->fdwatcher);

  return 0;
}

void vnode_msgiostop(vnode_msgio_t *msgio)
{
  ev_io_stop(msgio->loop, &msgio->fdwatcher);
  FREE_MSGBUF(&msgio->msgbuf);

  return;
}

int vnode_parsemsg(vnode_msg_t *msg, void *data,
		   const vnode_tlvhandler_t tlvhandler[VNODE_TLV_MAX])
{
  size_t offset = 0;
  vnode_tlv_t *tlv;
  vnode_tlvhandler_t tlvhandlefn;
  int tmp = -1;

  while (offset < msg->hdr.datalen)
  {
    tlv = (void *)msg->data + offset;

    offset += sizeof(*tlv) + tlv->vallen;

    if (tlv->vallen == 0 || offset > msg->hdr.datalen)
    {
      WARNX("invalid value length: %u", tlv->vallen);
      continue;
    }

    if ((tlvhandlefn = tlvhandler[tlv->type]) == NULL)
    {
      WARNX("unknown tlv type: %u", tlv->type);
      continue;
    }

    if ((tmp = tlvhandlefn(tlv, data)))
      break;
  }

  return tmp;
}

ssize_t vnode_addtlv(vnode_msgbuf_t *msgbuf, size_t offset,
		     uint32_t type, uint32_t vallen, const void *valp)
{
  vnode_tlv_t *tlv;
  size_t msglen, tlvlen;

  tlv = (void *)msgbuf->msg->data + offset;
  msglen = (void *)tlv - (void *)msgbuf->msg;
  tlvlen = sizeof(*tlv) + vallen;

  if (msglen + tlvlen > msgbuf->msgbufsize)
  {
    if (vnode_resizemsgbuf(msgbuf, msgbuf->msgbufsize + tlvlen))
      return -1;
    else
      tlv = (void *)msgbuf->msg->data + offset;
  }

  tlv->type = type;
  tlv->vallen = vallen;
  memcpy(tlv->val, valp, vallen);

  return tlvlen;
}
