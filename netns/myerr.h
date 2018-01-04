/*
 * CORE
 * Copyright (c)2010-2012 the Boeing Company.
 * See the LICENSE file included in this distribution.
 *
 * author: Tom Goff <thomas.goff@boeing.com>
 *
 * myerr.h
 *
 * Custom error printing macros.
 */

#ifndef _MYERR_H_
#define _MYERR_H_

#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <time.h>
#include <unistd.h>

#include <sys/time.h>

static void __myerrprintf(const char *func, const char *file, const int line,
			  FILE *stream, const char *fmt, ...)
{
  extern const char *__progname;
  va_list ap;
  pid_t pid;
  struct timeval tv;

  va_start(ap, fmt);

  pid = getpid();
  if (gettimeofday(&tv, NULL))
  {
    fprintf(stream, "%s[%u]: %s[%s:%d]: ", __progname, pid, func, file, line);
  }
  else
  {
    char timestr[9];
    strftime(timestr, sizeof(timestr), "%H:%M:%S", localtime(&tv.tv_sec));
    fprintf(stream, "%s[%u]: %s.%06ld %s[%s:%d]: ",
	    __progname, pid, timestr, tv.tv_usec, func, file, line);
  }

  vfprintf(stream, fmt, ap);
  fputs("\n", stream);

  va_end(ap);

  return;
}

#define INFO(fmt, args...)			\
  __myerrprintf(__func__, __FILE__, __LINE__,	\
		stdout, fmt, ##args)

#define WARNX(fmt, args...)			\
  __myerrprintf(__func__, __FILE__, __LINE__,	\
		stderr, fmt, ##args)

#define WARN(fmt, args...)					\
  __myerrprintf(__func__, __FILE__, __LINE__,			\
		stderr, fmt ": %s", ##args, strerror(errno))

#define ERRX(eval, fmt, args...)		\
  do {						\
    WARNX(fmt, ##args);				\
    exit(eval);					\
 } while (0)

#define ERR(eval, fmt, args...)			\
  do {						\
    WARN(fmt, ##args);				\
    exit(eval);					\
 } while (0)

#endif	/* _MYERR_H_ */
