import pytest

pytest.main([
    "-v",
    "--cov-report",
    "xml",
    "--cov=.",
    "tests"
])
