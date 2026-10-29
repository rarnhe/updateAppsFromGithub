import importlib.util
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def updater():
    script = Path(__file__).resolve().parents[1] / "updateAppsFromGithub.py"
    spec = importlib.util.spec_from_file_location("updateAppsFromGithub", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
