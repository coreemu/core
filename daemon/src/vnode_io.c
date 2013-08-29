/*
 * CORE
 * Copyright (c)2010-2012 the Boeing Company.
 * See the LICENSE file included in this distribution.
 *
 * author: Tom Goff <thomas.goff@boeing.com>
 *
 * vnode_io.c
 *
 */

#include <unistd.h>
#include <stdint.h>
#include <errno.h>
/* #define _XOPEN_SOURCE */
#ifndef __USE_XOPEN
#define __USE_XOPEN
#endif
#include <stdlib.h>
#include <fcntl.h>
#include <termios.h>

#include <sys/ioctl.h>

#include "myerr.h"
#include "vnode_chnl.h"
#include "vnode_io.h"


int set_nonblock(int fd)
{
  int fl, r = 0;

  if ((fl = fcntl(fd, F_GETFL)) == -1)
  {
    fl = 0;
    r = -1;
  }
  if (fcntl(fd, F_SETFL, fl | O_NONBLOCK))
    r = -1;

  return r;
}

int clear_nonblock(int fd)
{
  int fl, r = 0;

  if ((fl = fcntl(fd, F_GETFL)) == -1)
  {
    fl = 0;
    r = -1;
  }
  if (fcntl(fd, F_SETFL, fl & ~O_NONBLOCK))
    r = -1;

  return r;
}

int open_stdio_pty(stdio_pty_t *stdiopty)
{
  int masterfd, slavefd;

  INIT_STDIO_PTY(stdiopty);

  if ((masterfd = posix_openpt(O_RDWR | O_NOCTTY)) < 0)
  {
    WARN("posix_openpt() failed");
    return -1;
  }

  if (grantpt(masterfd))
  {
    WARN("grantpt() failed");
    close(masterfd);
    return -1;
  }

  if (unlockpt(masterfd))
  {
    WARN("unlockpt() failed");
    close(masterfd);
    return -1;
  }

  if ((slavefd = open(ptsname(masterfd), O_RDWR | O_NOCTTY)) < 0)
  {
    WARN("open() failed");
    close(masterfd);
    return -1;
  }

  stdiopty->masterfd = masterfd;
  stdiopty->slavefd = slavefd;

  return 0;
}

void close_stdio_pty(stdio_pty_t *stdiopty)
{
  if (stdiopty->masterfd >= 0)
    close(stdiopty->masterfd);
  if (stdiopty->slavefd >= 0)
    close(stdiopty->slavefd);

  INIT_STDIO_PTY(stdiopty);

  return;
}

int open_stdio_pipe(stdio_pipe_t *stdiopipe)
{
  int infd[2], outfd[2], errfd[2];

  INIT_STDIO_PIPE(stdiopipe);

  if (pipe(infd) < 0)
  {
    WARN("pipe() failed");
    return -1;
  }

  if (pipe(outfd) < 0)
  {
    WARN("pipe() failed");
    close(infd[0]);
    close(infd[1]);
    return -1;
  }

  if (pipe(errfd) < 0)
  {
    WARN("pipe() failed");
    close(infd[0]);
    close(infd[1]);
    close(outfd[0]);
    close(outfd[1]);
    return -1;
  }

  stdiopipe->infd[0] = infd[0];
  stdiopipe->infd[1] = infd[1];

  stdiopipe->outfd[0] = outfd[0];
  stdiopipe->outfd[1] = outfd[1];

  stdiopipe->errfd[0] = errfd[0];
  stdiopipe->errfd[1] = errfd[1];

  return 0;
}

void close_stdio_pipe(stdio_pipe_t *stdiopipe)
{
  if (stdiopipe->infd[0] >= 0)
    close(stdiopipe->infd[0]);
  if (stdiopipe->infd[1] >= 0)
    close(stdiopipe->infd[1]);

  if (stdiopipe->outfd[0] >= 0)
    close(stdiopipe->outfd[0]);
  if (stdiopipe->outfd[1] >= 0)
    close(stdiopipe->outfd[1]);

  if (stdiopipe->errfd[0] >= 0)
    close(stdiopipe->errfd[0]);
  if (stdiopipe->errfd[1] >= 0)
    close(stdiopipe->errfd[1]);

  INIT_STDIO_PIPE(stdiopipe);

  return;
}
