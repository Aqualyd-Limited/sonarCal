import platform
from os import environ
from subprocess import run

from hatchling.builders.hooks.plugin.interface import BuildHookInterface


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        """Run zensical build in an OS independent way."""

        shell = platform.system() == "Windows"

        run(['uv', 'tool', 'run', 'zensical', 'build'],
            check=False,
            shell=shell,
            env=environ | {'OFFLINE_PLUGIN_ENABLED': 'true'})
