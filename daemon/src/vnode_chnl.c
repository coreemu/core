/*
 * CORE
 * Copyright (c)2010-2012 the Boeing Company.
 * See the LICENSE file included in this distribution.
 *
 * author: Tom Goff <thomas.goff@boeing.com>
 *
 * vnode_chnl.c
 *
 * Functions for setting up a local UNIX socket to use as a control channel
 * for interacting with a network namespace.
 *
 */

#include <fcntl.h>
#include <string.h>
#include <errno.h>
#include <assert.h>

#include <sys/socket.h>
#include <sys/un.h>

#include "vnode_msg.h"
#include "vnode_tlv.h"
#include "vnode_chnl.h"
#include "vnode_io.h"

extern int verbose;


int vnode_connect(const char *name)
{
  int fd;
  struct sockaddr_un addr;

#ifdef DEBUG
  WARNX("opening '%s'", name);
#endif

  if (strlen(name) > sizeof(addr.sun_path) - 1)
  {
    WARNX("name too long: '%s'", name);
    return -1;
  }

  if ((fd = socket(AF_UNIX, SOCK_SEQPACKET, 0)) < 0)
  {
    WARN("socket() failed");
    return -1;
  }

  addr.sun_family = AF_UNIX;
  strcpy(addr.sun_path, name);
  if (connect(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0)
  {
    WARN("connect() failed for '%s'", name);
    close(fd);
    return -1;
  }

  if (set_nonblock(fd))
    WARN("set_nonblock() failed for fd %d", fd);

  return fd;
}

int vnode_listen(const char *name)
{
  int fd;
  struct sockaddr_un addr;

#ifdef DEBUG
  WARNX("opening '%s'", name);
#endif

  if (strlen(name) > sizeof(addr.sun_path) - 1)
  {
    WARNX("name too long: '%s'", name);
    return -1;
  }

  if ((fd = socket(AF_UNIX, SOCK_SEQPACKET, 0)) < 0)
  {
    WARN("socket() failed");
    return -1;
  }

  unlink(name);
  addr.sun_family = AF_UNIX;
  strcpy(addr.sun_path, name);

  if (bind(fd, (struct sockaddr *)&addr, sizeof(addr)) < 0)
  {
    WARN("bind() failed for '%s'", name);
    close(fd);
    return -1;
  }

  /* to override umask */
  if (chmod(name, S_IRUSR | S_IWUSR | S_IRGRP | S_IWGRP | S_IROTH | S_IWOTH))
    WARN("fchmod() failed for '%s'", name);

  if (listen(fd, 5) < 0)
  {
    WARN("listen() failed");
    close(fd);
    return -1;
  }

  if (set_nonblock(fd))
    WARN("set_nonblock() failed for fd %d", fd);

  return fd;
}
