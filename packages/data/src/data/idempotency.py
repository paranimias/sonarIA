import time

from boto3.dynamodb.conditions import Attr
from botocore.exceptions import ClientError


def check_and_set(table, *, wamid: str, ttl_seconds: int = 300) -> bool:
    """Attempt to mark wamid as processed.

    Returns True if this is the first time we see this wamid (safe to process).
    Returns False if it was already processed (duplicate — discard).
    """
    ttl = int(time.time()) + ttl_seconds
    try:
        table.put_item(
            Item={
                "PK": f"IDEMPOTENCY#{wamid}",
                "SK": "IDEMPOTENCY",
                "wamid": wamid,
                "ttl": ttl,
            },
            ConditionExpression=Attr("PK").not_exists(),
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            return False
        raise
