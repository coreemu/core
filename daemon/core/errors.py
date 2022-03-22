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
            f"command({self.cmd}), status({self.returncode}):\n"
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


class CoreServiceError(Exception):
    """
    Used when there is an error related to accessing a service.
    """

    pass


class CoreServiceBootError(Exception):
    """
    Used when there is an error booting a service.
    """

    pass


class CoreConfigError(Exception):
    """
    Used when there is an error defining a configurable option.
    """

    pass
