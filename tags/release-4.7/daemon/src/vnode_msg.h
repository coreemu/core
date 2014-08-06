/*
 * CORE
 * Copyright (c)2010-2012 the Boeing Company.
 * See the LICENSE file included in this distribution.
 *
 * author: Tom Goff <thomas.goff@boeing.com>
 *
 * vnode_msg.h
 *
 */

#ifndef _VNODE_MSG_H_
#define _VNODE_MSG_H_

#include <stdlib.h>
#include <unistd.h>
#include <stdint.h>
#include <ev.h>

#include "myerr.h"

typedef struct __attribute__ ((__packed__)) {
  uint32_t type;
  uint32_t vallen;
  uint8_t  val[];
} vnode_tlv_t;

typedef struct __attribute__ ((__packed__)) {
  uint32_t type;
  uint32_t datalen;
} vnode_msghdr_t;

typedef struct __attribute__ ((__packed__)) {
  vnode_msghdr_t hdr;
  uint8_t  data[];
} vnode_msg_t;

typedef enum {
  VNODE_MSG_NONE = 0,
  VNODE_MSG_CMDREQ,
  VNODE_MSG_CMDREQACK,
  VNODE_MSG_CMDSTATUS,
  VNODE_MSG_CMDSIGNAL,
  VNODE_MSG_MAX,
} vnode_msgtype_t;

typedef enum {
  VNODE_TLV_NONE = 0,
  VNODE_TLV_CMDID,
  VNODE_TLV_STDIN,
  VNODE_TLV_STDOUT,
  VNODE_TLV_STDERR,
  VNODE_TLV_CMDARG,
  VNODE_TLV_CMDPID,
  VNODE_TLV_CMDSTATUS,
  VNODE_TLV_SIGNUM,
  VNODE_TLV_MAX,
} vnode_tlvtype_t;

enum {
  VNODE_ARGMAX = 1024,
  VNODE_MSGSIZMAX = 65535,
};

typedef struct {
  vnode_msg_t *msg;
  size_t msgbufsize;
  int infd;
  int outfd;
  int errfd;
} vnode_msgbuf_t;

#define INIT_MSGBUF(msgbuf)			\
  do {						\
    (msgbuf)->msg = NULL;			\
    (msgbuf)->msgbufsize = 0;			\
    (msgbuf)->infd = -1;			\
    (msgbuf)->outfd = -1;			\
    (msgbuf)->errfd = -1;			\
  } while (0)

#define FREE_MSGBUF(msgbuf)			\
  do {						\
    if ((msgbuf)->msg)				\
      free((msgbuf)->msg);			\
    INIT_MSGBUF(msgbuf);			\
  } while (0)

struct vnode_msgio;
typedef void (*vnode_msghandler_t)(struct vnode_msgio *msgio);

typedef struct vnode_msgio {
  struct ev_loop *loop;
  int fd;
  ev_io fdwatcher;
  vnode_msgbuf_t msgbuf;
  void *data;
  vnode_msghandler_t ioerror;
  vnode_msghandler_t msghandler[VNODE_MSG_MAX];
} vnode_msgio_t;

typedef int (*vnode_tlvhandler_t)(vnode_tlv_t *tlv, void *data);


static inline void vnode_msgiohandler(vnode_msgio_t *msgio,
				      vnode_msgtype_t msgtype,
				      vnode_msghandler_t msghandlefn)
{
  msgio->msghandler[msgtype] = msghandlefn;
  return;
}

static inline int vnode_resizemsgbuf(vnode_msgbuf_t *msgbuf, size_t size)
{
  void *newbuf;
  if ((newbuf = realloc(msgbuf->msg, size)) == NULL)
  {
    WARN("realloc() failed for size %u", size);
    return -1;
  }
  msgbuf->msg = newbuf;
  msgbuf->msgbufsize = size;
  return 0;
}

static inline int vnode_initmsgbuf(vnode_msgbuf_t *msgbuf)
{
  INIT_MSGBUF(msgbuf);
  return vnode_resizemsgbuf(msgbuf, VNODE_MSGSIZMAX);
}

#define vnode_msglen(msgbuf)				\
  (sizeof(*(msgbuf)->msg) + (msgbuf)->msg->hdr.datalen)

ssize_t vnode_sendmsg(int fd, vnode_msgbuf_t *msgbuf);
ssize_t vnode_recvmsg(vnode_msgio_t *msgio);

int vnode_msgiostart(vnode_msgio_t *msgio, struct ev_loop *loop,
		     int fd, void *data, vnode_msghandler_t ioerror,
		     const vnode_msghandler_t msghandler[VNODE_MSG_MAX]);
void vnode_msgiostop(vnode_msgio_t *msgio);

int vnode_parsemsg(vnode_msg_t *msg, void *data,
		   const vnode_tlvhandler_t tlvhandler[VNODE_TLV_MAX]);
ssize_t vnode_addtlv(vnode_msgbuf_t *msgbuf, size_t offset,
		     uint32_t type, uint32_t vallen, const void *valp);

#endif	/* _VNODE_MSG_H_ */
