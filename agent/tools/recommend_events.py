import os

from boto3.dynamodb.conditions import Key
from data.table import get_table

# Synonyms: any of these terms means the user is asking for music events
_MUSIC_TERMS = {"música", "musica", "musical", "musicales", "concierto", "conciertos", "show"}


_PAGE_SIZE = 15


def handle(tool_input: dict, *, ctx: dict) -> dict:
    genre = (tool_input.get("genre") or "").strip().lower()
    artist = (tool_input.get("artist") or "").strip().lower()
    offset = max(0, int(tool_input.get("offset") or 0))

    table = get_table(os.environ.get("SONARIA_TABLE_NAME", "sonaria"))
    resp = table.query(
        KeyConditionExpression=Key("PK").eq("EVENTS") & Key("SK").begins_with("EVENT#"),
        Limit=200,
    )
    _INTERNAL = {"PK", "SK", "ttl"}
    events: list[dict] = [
        {k: v for k, v in item.items() if k not in _INTERNAL} for item in resp.get("Items", [])
    ]

    if artist:
        events = [e for e in events if artist in e.get("title", "").lower()]

    if genre:
        if genre in _MUSIC_TERMS:
            music_events = [e for e in events if e.get("genre", "").lower() == "música"]
            events = music_events if music_events else events
        else:
            events = [
                e
                for e in events
                if genre in (e.get("title", "") + " " + e.get("genre", "")).lower()
            ]

    total = len(events)
    page = events[offset : offset + _PAGE_SIZE]

    return {
        "ok": True,
        "events": page,
        "total_found": total,
        "has_more": (offset + len(page)) < total,
        "note": (
            None
            if page
            else "Sin eventos musicales en base de datos. El scraper corre a medianoche Colombia."
        ),
    }
