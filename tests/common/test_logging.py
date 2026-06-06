from aws_lambda_powertools import Logger
from common.logging import bind_context, log_turn_usage


def _fresh_logger() -> Logger:
    return Logger(service="test", level="DEBUG")


def test_bind_context_all_fields():
    logger = _fresh_logger()
    bind_context(
        logger, phone_number="573001234567", user_id="u1", agent_id="sonaria", wamid="wamid_abc"
    )
    assert logger.get_current_keys().get("phone_number") == "573001234567"
    assert logger.get_current_keys().get("user_id") == "u1"
    assert logger.get_current_keys().get("agent_id") == "sonaria"
    assert logger.get_current_keys().get("wamid") == "wamid_abc"


def test_bind_context_partial_fields():
    logger = _fresh_logger()
    bind_context(logger, agent_id="sonaria")
    keys = logger.get_current_keys()
    assert keys.get("agent_id") == "sonaria"
    assert "phone_number" not in keys
    assert "user_id" not in keys


def test_bind_context_none_values_ignored():
    logger = _fresh_logger()
    bind_context(logger, phone_number=None, user_id=None)
    keys = logger.get_current_keys()
    assert "phone_number" not in keys
    assert "user_id" not in keys


def test_log_turn_usage_emits_record(caplog):
    import logging

    logger = _fresh_logger()
    with caplog.at_level(logging.INFO, logger="test"):
        log_turn_usage(
            logger,
            input_tokens=100,
            output_tokens=50,
            iterations=2,
            tools_used=["recommend_events"],
            identified=True,
        )
    assert any("turn_usage" in r.message for r in caplog.records)
