import subprocess

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, _version: str, _build_data: dict) -> None:
        subprocess.run(['bun', 'install', '--frozen-lockfile'], check=True)  # noqa: S607
        subprocess.run(['bun', 'run', 'build'], check=True)  # noqa: S607
