import os

import pytest
from data.table import create_table
from moto import mock_aws

TABLE_NAME = "sonaria-test"


@pytest.fixture(autouse=True)
def aws_credentials():
    """Moto requires fake credentials to be set."""
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
    os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
    os.environ.setdefault("AWS_SECURITY_TOKEN", "testing")
    os.environ.setdefault("AWS_SESSION_TOKEN", "testing")


@pytest.fixture
def table(aws_credentials):
    with mock_aws():
        tbl = create_table(TABLE_NAME)
        tbl.wait_until_exists()
        import boto3

        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        yield dynamodb.Table(TABLE_NAME)
