/*
 * CORE
 * Copyright (c)2010-2012 the Boeing Company.
 * See the LICENSE file included in this distribution.
 *
 * author: Tom Goff <thomas.goff@boeing.com>
 *
 * vnode_io.h
 *
 */

#ifndef _VNODE_IO_H_
#define _VNODE_IO_H_

typedef struct {
  int infd;
  int outfd;
  int errfd;
} stdio_fd_t;

#define INIT_STDIO_FD(s)			\
  do {						\
    (s)->infd = -1;				\
    (s)->outfd = -1;				\
    (s)->errfd = -1;				\
  } while (0)

typedef struct {
  int masterfd;
  int slavefd;
} stdio_pty_t;

#define INIT_STDIO_PTY(s)			\
  do {						\
    (s)->masterfd = -1;				\
    (s)->slavefd = -1;				\
  } while (0)

typedef struct {
  int infd[2];
  int outfd[2];
  int errfd[2];
} stdio_pipe_t;

#define INIT_STDIO_PIPE(s)			\
  do {						\
    (s)->infd[0] = (s)->infd[1] = -1;		\
    (s)->outfd[0] = (s)->outfd[1] = -1;		\
    (s)->errfd[0] = (s)->errfd[1] = -1;		\
  } while (0)

int set_nonblock(int fd);
int clear_nonblock(int fd);

int open_stdio_pty(stdio_pty_t *stdiopty);
void close_stdio_pty(stdio_pty_t *stdiopty);

int open_stdio_pipe(stdio_pipe_t *stdiopipe);
void close_stdio_pipe(stdio_pipe_t *stdiopipe);

#endif /* _VNODE_IO_H_ */
