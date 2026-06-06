import json

import boto3
import pytest
from data.table import create_table
from moto import mock_aws

TABLE_NAME = "sonaria-test"
QUEUE_NAME = "sonaria-agent.fifo"
USER_ID = "cognito-sub-abc123"


@pytest.fixture(autouse=True)
def env_vars(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("SONARIA_TABLE_NAME", TABLE_NAME)


@pytest.fixture
def aws_resources(monkeypatch):
    with mock_aws():
        tbl = create_table(TABLE_NAME)
        tbl.wait_until_exists()

        sqs = boto3.client("sqs", region_name="us-east-1")
        resp = sqs.create_queue(
            QueueName=QUEUE_NAME,
            Attributes={"FifoQueue": "true", "ContentBasedDeduplication": "false"},
        )
        queue_url = resp["QueueUrl"]
        monkeypatch.setenv("SQS_QUEUE_URL", queue_url)

        import services.api.handler as api

        api._sqs = sqs

        yield {
            "sqs": sqs,
            "queue_url": queue_url,
            "table": boto3.resource("dynamodb", region_name="us-east-1").Table(TABLE_NAME),
        }


def apigw_event(
    method: str,
    path: str,
    body: dict | None = None,
    user_id: str = USER_ID,
    params: dict | None = None,
) -> dict:
    """Build a minimal API Gateway HTTP API event with JWT claims."""
    return {
        "requestContext": {
            "http": {"method": method},
            "authorizer": {"jwt": {"claims": {"sub": user_id, "email": "test@test.com"}}},
        },
        "rawPath": path,
        "queryStringParameters": params,
        "body": json.dumps(body) if body else None,
    }


def apigw_event_no_auth(method: str, path: str, body: dict | None = None) -> dict:
    """Event without JWT authorizer context."""
    return {
        "requestContext": {"http": {"method": method}},
        "rawPath": path,
        "body": json.dumps(body) if body else None,
    }
