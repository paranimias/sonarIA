import pytest
from aws_lambda_powertools import Logger


_CONTEXT_KEYS = ("phone_number", "user_id", "agent_id", "wamid")


@pytest.fixture(autouse=True)
def reset_logger_context():
    """aws_lambda_powertools Logger is a singleton — remove context keys between tests."""
    logger = Logger(service="test")
    logger.remove_keys([*_CONTEXT_KEYS])
    yield
    logger.remove_keys([*_CONTEXT_KEYS])
