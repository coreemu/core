/*
 * CORE
 * Copyright (c)2010-2012 the Boeing Company.
 * See the LICENSE file included in this distribution.
 *
 * author: Tom Goff <thomas.goff@boeing.com>
 *
 * netns_main.c
 *
 * netns utility program runs the specified program with arguments in a new
 * namespace.
 *
 */

#include <stdarg.h>
#include <stdlib.h>
#include <stdio.h>
#include <unistd.h>
#include <signal.h>
#include <getopt.h>

#include <sys/wait.h>

#include "version.h"
#include "netns.h"
#include "myerr.h"

struct option longopts[] =
{ 
    {"version", no_argument, NULL, 'V'},
    {"help", no_argument, NULL, 'h'},
    { 0 }
};

static void usage(int status, char *fmt, ...)
{
  extern const char *__progname;
  va_list ap;
  FILE *output;

  va_start(ap, fmt);

  output = status ? stderr : stdout;
  fprintf(output, "\n");
  if (fmt != NULL)
  {
    vfprintf(output, fmt, ap);
    fprintf(output, "\n\n");
  }
  fprintf(output,
	  "Usage: %s [-h|-V] [-w] -- command [args...]\n\n"
	  "Run the specified command in a new network namespace.\n\n"
	  "Options:\n"
	  "  -h, --help  show this help message and exit\n"
	  "  -V, --version  show version number and exit\n"
	  "  -w  wait for command to complete "
	  "(useful for interactive commands)\n",
	  __progname);

  va_end(ap);

  exit(status);
}

int main(int argc, char *argv[])
{
  pid_t pid;
  int waitcmd = 0;
  int status = 0;
  extern const char *__progname;

  for (;;)
  {
    int opt;

    if ((opt = getopt_long(argc, argv, "hwV", longopts, NULL)) == -1)
      break;

    switch (opt)
    {
    case 'w':
      waitcmd++;
      break;

    case 'V':
      printf("%s version %s\n", __progname, CORE_VERSION);
      exit(0);

    case 'h':
    default:
      usage(0, NULL);
    }
  }

  argc -= optind;
  argv += optind;

  if (!argc)
    usage(1, "no command given");

  if (geteuid() != 0)
    usage(1, "must be suid or run as root");
  if (setuid(0))
    ERR(1, "setuid() failed");

  pid = nsexecvp(argv);
  if (pid < 0)
    ERR(1, "nsexecvp() failed");

  printf("%d\n", pid);

  if (waitcmd)
  {
    if (waitpid(pid, &status, 0) == -1)
      ERR(1, "waitpid() failed");

    if (WIFEXITED(status))
      status = WEXITSTATUS(status);
    else if (WIFSIGNALED(status))
    {
      fprintf(stderr, "process terminated by signal %d\n", WTERMSIG(status));
      status = -1;
    }
  }

  exit(status);
}
