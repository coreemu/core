"""
Provides CORE specific errors.
"""
import subprocess


class CoreCommandError(subprocess.CalledProcessError):
    """
    Used when encountering internal CORE command errors.
    """

    def __str__(self):
        return "Command(%s), Status(%s):\nstdout: %s\nstderr: %s" % (
            self.cmd,
            self.returncode,
            self.output,
            self.stderr,
        )


class CoreError(Exception):
    """
    Used for errors when dealing with CoreEmu and Sessions.
    """

    pass
