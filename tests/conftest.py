from copy import deepcopy
import pytest
import config


@pytest.fixture
def default_config():
    return deepcopy(config.DEFAULTS)
