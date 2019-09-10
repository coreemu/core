import sys

import pytest

distributed = sys.argv[1]
pytest.main(
    ["-v", "--distributed", distributed, "--cov-report", "xml", "--cov=.", "tests"]
)
