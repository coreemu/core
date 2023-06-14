import logging
import subprocess
from collections.abc import Callable
from pathlib import Path

from core.emulator.enumerations import EventTypes
from core.errors import CoreError

logger = logging.getLogger(__name__)


class HookManager:
    """
    Provides functionality for managing and running script/callback hooks.
    """

    def __init__(self) -> None:
        """
        Create a HookManager instance.
        """
        self.script_hooks: dict[EventTypes, dict[str, str]] = {}
        self.callback_hooks: dict[EventTypes, list[Callable[[], None]]] = {}

    def reset(self) -> None:
        """
        Clear all current hooks.

        :return: nothing
        """
        self.script_hooks.clear()
        self.callback_hooks.clear()

    def add_script_hook(self, state: EventTypes, file_name: str, data: str) -> None:
        """
        Add a hook script to run for a given state.

        :param state: state to run hook on
        :param file_name: hook file name
        :param data: file data
        :return: nothing
        """
        logger.info("setting state hook: %s - %s", state, file_name)
        state_hooks = self.script_hooks.setdefault(state, {})
        if file_name in state_hooks:
            raise CoreError(
                f"adding duplicate state({state.name}) hook script({file_name})"
            )
        state_hooks[file_name] = data

    def delete_script_hook(self, state: EventTypes, file_name: str) -> None:
        """
        Delete a script hook from a given state.

        :param state: state to delete script hook from
        :param file_name: name of script to delete
        :return: nothing
        """
        state_hooks = self.script_hooks.get(state, {})
        if file_name not in state_hooks:
            raise CoreError(
                f"deleting state({state.name}) hook script({file_name}) "
                "that does not exist"
            )
        del state_hooks[file_name]

    def add_callback_hook(
        self, state: EventTypes, hook: Callable[[EventTypes], None]
    ) -> None:
        """
        Add a hook callback to run for a state.

        :param state: state to add hook for
        :param hook: callback to run
        :return: nothing
        """
        hooks = self.callback_hooks.setdefault(state, [])
        if hook in hooks:
            name = getattr(callable, "__name__", repr(hook))
            raise CoreError(
                f"adding duplicate state({state.name}) hook callback({name})"
            )
        hooks.append(hook)

    def delete_callback_hook(
        self, state: EventTypes, hook: Callable[[EventTypes], None]
    ) -> None:
        """
        Delete a state hook.

        :param state: state to delete hook for
        :param hook: hook to delete
        :return: nothing
        """
        hooks = self.callback_hooks.get(state, [])
        if hook not in hooks:
            name = getattr(callable, "__name__", repr(hook))
            raise CoreError(
                f"deleting state({state.name}) hook callback({name}) "
                "that does not exist"
            )
        hooks.remove(hook)

    def run_hooks(
        self, state: EventTypes, directory: Path, env: dict[str, str]
    ) -> None:
        """
        Run all hooks for the current state.

        :param state: state to run hooks for
        :param directory: directory to run script hooks within
        :param env: environment to run script hooks with
        :return: nothing
        """
        for state_hooks in self.script_hooks.get(state, {}):
            for file_name, data in state_hooks.items():
                logger.info("running hook %s", file_name)
                file_path = directory / file_name
                log_path = directory / f"{file_name}.log"
                try:
                    with file_path.open("w") as f:
                        f.write(data)
                    with log_path.open("w") as f:
                        args = ["/bin/sh", file_name]
                        subprocess.check_call(
                            args,
                            stdout=f,
                            stderr=subprocess.STDOUT,
                            close_fds=True,
                            cwd=directory,
                            env=env,
                        )
                except (OSError, subprocess.CalledProcessError) as e:
                    raise CoreError(
                        f"failure running state({state.name}) "
                        f"hook script({file_name}): {e}"
                    )
        for hook in self.callback_hooks.get(state, []):
            try:
                hook()
            except Exception as e:
                name = getattr(callable, "__name__", repr(hook))
                raise CoreError(
                    f"failure running state({state.name}) "
                    f"hook callback({name}): {e}"
                )
