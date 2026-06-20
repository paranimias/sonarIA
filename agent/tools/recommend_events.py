import os

from boto3.dynamodb.conditions import Key
from data.table import get_table

# Synonyms: any of these terms means the user is asking for music events
_MUSIC_TERMS = {"música", "musica", "musical", "musicales", "concierto", "conciertos", "show"}


def handle(tool_input: dict, *, ctx: dict) -> dict:
    genre = (tool_input.get("genre") or "").strip().lower()
    artist = (tool_input.get("artist") or "").strip().lower()

    table = get_table(os.environ.get("SONARIA_TABLE_NAME", "sonaria"))
    resp = table.query(
        KeyConditionExpression=Key("PK").eq("EVENTS") & Key("SK").begins_with("EVENT#"),
        Limit=100,
    )
    _INTERNAL = {"PK", "SK", "ttl"}
    events: list[dict] = [
        {k: v for k, v in item.items() if k not in _INTERNAL}
        for item in resp.get("Items", [])
    ]

    if artist:
        events = [e for e in events if artist in e.get("title", "").lower()]

    if genre:
        if genre in _MUSIC_TERMS:
            # General music query → prefer events tagged as música but include all
            music_events = [e for e in events if e.get("genre", "").lower() == "música"]
            events = music_events if music_events else events
        else:
            # Specific genre (jazz, rock, salsa…) → match title or genre field
            events = [
                e
                for e in events
                if genre in (e.get("title", "") + " " + e.get("genre", "")).lower()
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
