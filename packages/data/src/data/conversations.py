from boto3.dynamodb.conditions import Key


def append_turn(
    table, *, wa_id: str, index: int, role: str, content: str, meta: dict | None = None
) -> None:
    table.put_item(
        Item={
            "PK": f"CONV#{wa_id}",
            "SK": f"TURN#{index:012d}",
            "role": role,
            "content": content,
            "meta": meta or {},
        }
    )


def get_turns(table, *, wa_id: str, n: int) -> list[dict]:
    """Return the last n turns for wa_id, ordered oldest-first."""
    response = table.query(
        KeyConditionExpression=Key("PK").eq(f"CONV#{wa_id}") & Key("SK").begins_with("TURN#"),
        ScanIndexForward=False,
        Limit=n,
    )
    return list(reversed(response.get("Items", [])))
