from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from os import environ
from subprocess import run

class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        """Run zensical build in an OS independent way."""

        run(['uv', 'tool', 'run', 'zensical', 'build'], 
            shell=True,
            env=environ | {'OFFLINE_PLUGIN_ENABLED': 'true'})
