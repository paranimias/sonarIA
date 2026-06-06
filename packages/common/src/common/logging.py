from aws_lambda_powertools import Logger

_logger = Logger(service="sonaria")


def get_logger() -> Logger:
    return _logger


def bind_context(
    logger: Logger,
    *,
    phone_number: str | None = None,
    user_id: str | None = None,
    agent_id: str | None = None,
    wamid: str | None = None,
) -> None:
    ctx = {
        k: v
        for k, v in {
            "phone_number": phone_number,
            "user_id": user_id,
            "agent_id": agent_id,
            "wamid": wamid,
        }.items()
        if v is not None
    }
    logger.append_keys(**ctx)


def log_turn_usage(
    logger: Logger,
    *,
    input_tokens: int,
    output_tokens: int,
    iterations: int,
    tools_used: list[str],
    identified: bool,
) -> None:
    logger.info(
        "turn_usage",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        iterations=iterations,
        tools_used=tools_used,
        identified=identified,
    )
