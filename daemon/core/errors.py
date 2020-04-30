"""
Provides CORE specific errors.
"""
import subprocess


class CoreCommandError(subprocess.CalledProcessError):
    """
    Used when encountering internal CORE command errors.
    """

    def __str__(self) -> str:
        return (
            f"Command({self.cmd}), Status({self.returncode}):\n"
            f"stdout: {self.output}\nstderr: {self.stderr}"
        )


class CoreError(Exception):
    """
    Used for errors when dealing with CoreEmu and Sessions.
    """

    pass


class CoreXmlError(Exception):
    """
    Used when there was an error parsing a CORE xml file.
    """

    pass
