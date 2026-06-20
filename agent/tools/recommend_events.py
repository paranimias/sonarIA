import os

from boto3.dynamodb.conditions import Key
from data.table import get_table


def handle(tool_input: dict, *, ctx: dict) -> dict:
    genre = (tool_input.get("genre") or "").strip().lower()
    artist = (tool_input.get("artist") or "").strip().lower()

    table = get_table(os.environ.get("SONARIA_TABLE_NAME", "sonaria"))
    resp = table.query(
        KeyConditionExpression=Key("PK").eq("EVENTS") & Key("SK").begins_with("EVENT#"),
        Limit=100,
    )
    events: list[dict] = resp.get("Items", [])

    if artist:
        events = [e for e in events if artist in e.get("title", "").lower()]
    if genre:
        events = [
            e for e in events if genre in (e.get("title", "") + " " + e.get("genre", "")).lower()
        ]

    return {
        "ok": True,
        "events": events[:12],
        "total_found": len(events),
        "note": (
            None
            if events
            else "Sin eventos en base de datos. El scraper corre a medianoche (hora Colombia)."
        ),
    }
