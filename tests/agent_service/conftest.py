from pathlib import Path

import boto3
import pytest
from core.types import Completion
from data.table import create_table
from moto import mock_aws

TABLE_NAME = "sonaria-test"
REPO_ROOT = Path(__file__).parent.parent.parent


class FakeRuntime:
    def __init__(self, responses: list[Completion]):
        self._responses = list(responses)
        self._index = 0

    def complete(self, **kwargs) -> Completion:
        if self._index >= len(self._responses):
            return Completion(text_blocks=["done"], tool_calls=[], stop_reason="end_turn", usage={})
        c = self._responses[self._index]
        self._index += 1
        return c


def end_turn(text: str) -> Completion:
    return Completion(
        text_blocks=[text],
        tool_calls=[],
        stop_reason="end_turn",
        usage={"input_tokens": 10, "output_tokens": 5},
    )


@pytest.fixture(autouse=True)
def env_vars(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("SONARIA_TABLE_NAME", TABLE_NAME)
    monkeypatch.setenv("SHARED_DIR", str(REPO_ROOT / "shared"))
    monkeypatch.setenv("AGENT_DIR", str(REPO_ROOT / "agent"))
    monkeypatch.setenv("META_ACCESS_TOKEN", "fake_token")
    monkeypatch.setenv("OPENAI_API_KEY", "fake_key")


@pytest.fixture
def table():
    with mock_aws():
        tbl = create_table(TABLE_NAME)
        tbl.wait_until_exists()
        yield boto3.resource("dynamodb", region_name="us-east-1").Table(TABLE_NAME)
