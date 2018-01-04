/*
 * CORE
 * Copyright (c)2010-2012 the Boeing Company.
 * See the LICENSE file included in this distribution.
 *
 * author: Tom Goff <thomas.goff@boeing.com>
 *
 * netns.c
 *
 * Implements nsfork() and nsexecvp() for forking and executing processes
 * within a network namespace.
 *
 */

#include <signal.h>
#include <unistd.h>

#include <sys/syscall.h>
#include <sys/mount.h>
#include <sys/utsname.h>

#include "myerr.h"
#include "netns.h"

#define NSCLONEFLGS				\
  (						\
   SIGCHLD       |				\
   CLONE_NEWNS   |				\
   CLONE_NEWUTS  |				\
   CLONE_NEWIPC  |				\
   CLONE_NEWPID	 |				\
   CLONE_NEWNET					\
  )

#define MOUNT_SYS_MIN_VERSION "2.6.35"

static void nssetup(void)
{
  int r;
  struct utsname uts;

  /* Taken from systemd-nspawn.  Not sure why needed, but without this,
   * the host system goes a bit crazy under systemd. */
  r = mount(NULL, "/", NULL, MS_SLAVE|MS_REC, NULL);
  if (r)
    WARN("mounting / failed");

  /* mount per-namespace /proc */
  r = mount(NULL, "/proc", "proc", 0, NULL);
  if (r)
    WARN("mounting /proc failed");

  r = uname(&uts);
  if (r)
  {
    WARN("uname() failed");
    return;
  }

  r = strncmp(uts.release, MOUNT_SYS_MIN_VERSION,
	      sizeof(MOUNT_SYS_MIN_VERSION) - 1);
  if (r >= 0)
  {
    /* mount per-namespace /sys */
    r = mount(NULL, "/sys", "sysfs", 0, NULL);
    if (r)
      WARN("mounting /sys failed");
  }
}

pid_t nsfork(int flags)
{
  int pid;

  pid = syscall(SYS_clone, flags | NSCLONEFLGS, NULL, NULL, NULL, NULL);
  if (pid == 0)			/* child */
  {
    nssetup();
  }

  return pid;
}

pid_t nsexecvp(char *argv[])
{
  pid_t pid;

  pid = nsfork(CLONE_VFORK);
  switch (pid)
  {
  case -1:
    WARN("nsfork() failed");
    break;

  case 0:
    /* child */
    execvp(argv[0], argv);
    WARN("execvp() failed for '%s'", argv[0]);
    _exit(1);
    break;

  default:
    /* parent */
    if (kill(pid, 0))
      pid = -1;
    break;
  }

  return pid;
}
