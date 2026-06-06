import hashlib
import hmac
import json

import boto3
import pytest
from data.table import create_table
from moto import mock_aws

TABLE_NAME = "sonaria-test"
QUEUE_NAME = "sonaria-test.fifo"
APP_SECRET = "test_secret"
VERIFY_TOKEN = "test_verify_token"


@pytest.fixture(autouse=True)
def env_vars(monkeypatch):
    monkeypatch.setenv("META_APP_SECRET", APP_SECRET)
    monkeypatch.setenv("META_VERIFY_TOKEN", VERIFY_TOKEN)
    monkeypatch.setenv("SONARIA_TABLE_NAME", TABLE_NAME)


@pytest.fixture
def aws_mock(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-1")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    with mock_aws():
        # DynamoDB table
        table = create_table(TABLE_NAME)
        table.wait_until_exists()

        # SQS FIFO queue
        sqs = boto3.client("sqs", region_name="us-east-1")
        resp = sqs.create_queue(
            QueueName=QUEUE_NAME,
            Attributes={"FifoQueue": "true", "ContentBasedDeduplication": "false"},
        )
        queue_url = resp["QueueUrl"]
        monkeypatch.setenv("SQS_QUEUE_URL", queue_url)

        import services.webhook.handler as wh

        # Point the module-level SQS client at the moto mock
        wh._sqs = boto3.client("sqs", region_name="us-east-1")

        yield {"sqs": sqs, "queue_url": queue_url}


def make_post_event(body_dict: dict, secret: str = APP_SECRET) -> dict:
    body = json.dumps(body_dict)
    sig = "sha256=" + hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return {
        "requestContext": {"http": {"method": "POST"}},
        "headers": {"x-hub-signature-256": sig},
        "isBase64Encoded": False,
        "body": body,
    }
