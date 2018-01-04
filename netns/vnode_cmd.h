/*
 * CORE
 * Copyright (c)2010-2012 the Boeing Company.
 * See the LICENSE file included in this distribution.
 *
 * author: Tom Goff <thomas.goff@boeing.com>
 *
 * vnode_cmd.h
 *
 */

#ifndef _VNODE_CMD_H_
#define _VNODE_CMD_H_

#include <sys/types.h>
#include <sys/queue.h>

#include "vnode_msg.h"

typedef struct {
  int infd;
  int outfd;
  int errfd;
} vnode_cmdio_t;

typedef struct {
  int32_t cmdid;
  vnode_cmdio_t cmdio;
  char *cmdarg[VNODE_ARGMAX];
} vnode_cmdreq_t;

#define CMDREQ_INIT {}

typedef struct {
  int32_t cmdid;
  int32_t pid;
} vnode_cmdreqack_t;

#define CMDREQACK_INIT {.cmdid = 0, .pid = -1}

typedef struct {
  int32_t cmdid;
  int32_t status;
} vnode_cmdstatus_t;

#define CMDSTATUS_INIT {.cmdid = 0, .status = -1}

typedef struct {
  int32_t cmdid;
  int32_t signum;
} vnode_cmdsignal_t;

#define CMDSIGNAL_INIT {.cmdid = 0, .signum = 0}

typedef struct cmdentry {
  TAILQ_ENTRY(cmdentry) entries;

  int32_t cmdid;
  pid_t pid;
  int status;
  void *data;
} vnode_cmdentry_t;

void vnode_recv_cmdreq(vnode_msgio_t *msgio);
int vnode_send_cmdreq(int fd, int32_t cmdid, char *argv[],
		      int infd, int outfd, int errfd);
int vnode_send_cmdstatus(int fd, int32_t cmdid, int32_t status);
int vnode_send_cmdsignal(int fd, int32_t cmdid, int32_t signum);
void vnode_recv_cmdsignal(vnode_msgio_t *msgio);

#endif /* _VNODE_CMD_H_ */
