"""
Provides CORE specific errors.
"""
import subprocess


class CoreCommandError(subprocess.CalledProcessError):
    """
    Used when encountering internal CORE command errors.
    """

    def __str__(self):
        return "Command(%s), Status(%s):\n%s" % (self.cmd, self.returncode, self.output)


class CoreError(Exception):
    """
    Used for errors when dealing with CoreEmu and Sessions.
    """

    pass
