import tomllib
from pathlib import Path


def define_env(env):

    @env.macro
    def supported_python_versions() -> str:

        toml_path = Path('pyproject.toml')

        if not toml_path.exists():
            return f"Error: {toml_path} not found"

        with Path.open(toml_path, "rb") as f:
            data = tomllib.load(f)

        if "project" in data and "requires-python" in data["project"]:
            return data["project"]["requires-python"].replace('>=', '≥').replace('<=', '≤')

        return f"Python version not found in {toml_path.name}"

    @env.macro
    def min_python_version() -> str:

        toml_path = Path('pyproject.toml')

        if not toml_path.exists():
            return f"Error: {toml_path} not found"

        with Path.open(toml_path, "rb") as f:
            data = tomllib.load(f)

        if "project" in data and "requires-python" in data["project"]:
            # Simplistic way that will fail if the version identifier is not >=
            return data["project"]["requires-python"].replace('>=', '')[:4]

        return f"Python version not found in {toml_path.name}"
