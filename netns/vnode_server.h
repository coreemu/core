/*
 * CORE
 * Copyright (c)2010-2012 the Boeing Company.
 * See the LICENSE file included in this distribution.
 *
 * author: Tom Goff <thomas.goff@boeing.com>
 *
 * vnode_server.h
 *
 */

#ifndef _VNODE_SERVER_H_
#define _VNODE_SERVER_H_

#include <limits.h>
#include <ev.h>

#include <sys/queue.h>

#include "vnode_msg.h"

typedef struct {
  TAILQ_HEAD(clientlist, cliententry) clientlisthead;
  TAILQ_HEAD(cmdlist, cmdentry) cmdlisthead;
  struct ev_loop *loop;
  char ctrlchnlname[PATH_MAX];
  char pidfilename[PATH_MAX];
  int serverfd;
  ev_io fdwatcher;
  ev_child childwatcher;
} vnode_server_t;

typedef struct cliententry {
  TAILQ_ENTRY(cliententry) entries;

  vnode_server_t *server;
  int clientfd;
  vnode_msgio_t msgio;
} vnode_cliententry_t;

vnode_server_t *vnoded(int newnetns, const char *ctrlchnlname,
		       const char *logfilename, const char *pidfilename,
		       const char *chdirname);
void vnode_delserver(vnode_server_t *server);
#endif	/* _VNODE_SERVER_H_ */
