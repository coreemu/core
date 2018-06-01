/*
 * CORE
 * Copyright (c)2010-2012 the Boeing Company.
 * See the LICENSE file included in this distribution.
 *
 * author: Tom Goff <thomas.goff@boeing.com>
 *
 * vnode_client.h
 *
 */

#ifndef _VNODE_CLIENT_H_
#define _VNODE_CLIENT_H_

#include <sys/queue.h>
#include <sys/types.h>

#include "vnode_msg.h"
#include "vnode_cmd.h"
#include "vnode_io.h"

struct vnode_client;
typedef void (*vnode_clientcb_t)(struct vnode_client *client);

typedef struct vnode_client {
  TAILQ_HEAD(cmdlist, cmdentry) cmdlisthead;

  struct ev_loop *loop;
  int serverfd;
  struct vnode_msgio msgio;
  void *data;

  vnode_clientcb_t ioerrorcb;

  int32_t cmdid;
} vnode_client_t;

typedef void (*vnode_client_cmddonecb_t)(int32_t cmdid, pid_t pid,
					 int status, void *data);

typedef enum {
  VCMD_IO_NONE = 0,
  VCMD_IO_FD,
  VCMD_IO_PIPE,
  VCMD_IO_PTY,
} vnode_client_cmdiotype_t;

typedef struct {
  vnode_client_cmdiotype_t iotype;
  union {
    stdio_fd_t stdiofd;
    stdio_pipe_t stdiopipe;
    stdio_pty_t stdiopty;
  };
} vnode_client_cmdio_t;

#define SET_STDIOFD(clcmdio, ifd, ofd, efd)	\
  do {						\
    (clcmdio)->iotype = VCMD_IO_FD;		\
    (clcmdio)->stdiofd.infd = (ifd);		\
    (clcmdio)->stdiofd.outfd = (ofd);		\
    (clcmdio)->stdiofd.errfd = (efd);		\
  } while (0)

vnode_client_t *vnode_client(struct ev_loop *loop, const char *ctrlchnlname,
			     vnode_clientcb_t ioerrorcb, void *data);
void vnode_delclient(vnode_client_t *client);

vnode_client_cmdio_t *vnode_open_clientcmdio(vnode_client_cmdiotype_t iotype);
void vnode_close_clientcmdio(vnode_client_cmdio_t *clientcmdio);

int vnode_client_cmdreq(vnode_client_t *client,
			vnode_client_cmdio_t *clientcmdio,
			vnode_client_cmddonecb_t cmddonecb, void *data,
			int argc, char *argv[]);

#endif	/* _VNODE_CLIENT_H_ */
