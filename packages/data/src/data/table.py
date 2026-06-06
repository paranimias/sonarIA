import boto3

TABLE_NAME_ENV = "SONARIA_TABLE_NAME"
_DEFAULT_TABLE = "sonaria-local"


def get_table(table_name: str | None = None, *, endpoint_url: str | None = None):
    """Return a boto3 DynamoDB Table resource."""
    kwargs = {}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    dynamodb = boto3.resource("dynamodb", **kwargs)
    return dynamodb.Table(table_name or _DEFAULT_TABLE)


def create_table(table_name: str, *, endpoint_url: str | None = None):
    """Create the single-table with its key schema and GSI. Used in tests and local dev."""
    kwargs = {}
    if endpoint_url:
        kwargs["endpoint_url"] = endpoint_url
    dynamodb = boto3.resource("dynamodb", **kwargs)
    return dynamodb.create_table(
        TableName=table_name,
        BillingMode="PAY_PER_REQUEST",
        KeySchema=[
            {"AttributeName": "PK", "KeyType": "HASH"},
            {"AttributeName": "SK", "KeyType": "RANGE"},
        ],
        AttributeDefinitions=[
            {"AttributeName": "PK", "AttributeType": "S"},
            {"AttributeName": "SK", "AttributeType": "S"},
            {"AttributeName": "GSI1PK", "AttributeType": "S"},
            {"AttributeName": "GSI1SK", "AttributeType": "S"},
        ],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "GSI1",
                "KeySchema": [
                    {"AttributeName": "GSI1PK", "KeyType": "HASH"},
                    {"AttributeName": "GSI1SK", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )
