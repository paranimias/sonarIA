from boto3.dynamodb.conditions import Key


def put_user(table, *, user_id: str, wa_id: str, full_name: str, email: str = "", role_name: str = "user") -> None:
    table.put_item(Item={
        "PK": f"USER#{user_id}",
        "SK": "PROFILE",
        "GSI1PK": f"PHONE#{wa_id}",
        "GSI1SK": f"USER#{user_id}",
        "user_id": user_id,
        "wa_id": wa_id,
        "full_name": full_name,
        "email": email,
        "role_name": role_name,
    })


def resolve_by_phone(table, *, wa_id: str) -> list[dict]:
    """Return all user profiles matching a wa_id via GSI1."""
    response = table.query(
        IndexName="GSI1",
        KeyConditionExpression=Key("GSI1PK").eq(f"PHONE#{wa_id}"),
    )
    return response.get("Items", [])


def get_by_id(table, *, user_id: str) -> dict | None:
    response = table.get_item(Key={"PK": f"USER#{user_id}", "SK": "PROFILE"})
    return response.get("Item")
