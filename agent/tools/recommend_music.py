import os

import httpx

LASTFM_BASE = "https://ws.audioscrobbler.com/2.0/"
_LIMIT = 6


def handle(tool_input: dict, *, ctx: dict) -> dict:
    api_key = os.environ.get("LASTFM_API_KEY", "")
    if not api_key:
        return {"ok": False, "error": "LASTFM_API_KEY not configured"}

    artist = (tool_input.get("artist") or "").strip()
    genre = (tool_input.get("genre") or "").strip()

    if not artist and not genre:
        return {"ok": False, "error": "Provide at least one of: artist, genre"}

    result: dict = {"ok": True}
    with httpx.Client(timeout=10) as client:
        if artist:
            result["similar_artists"] = _similar_artists(client, api_key, artist)
            result["top_tracks"] = _artist_top_tracks(client, api_key, artist)
        if genre:
            result["top_artists"] = _tag_top_artists(client, api_key, genre)
            result["top_tracks_by_genre"] = _tag_top_tracks(client, api_key, genre)

    return result


def _call(client: httpx.Client, api_key: str, method: str, **params) -> dict:
    resp = client.get(
        LASTFM_BASE,
        params={"method": method, "api_key": api_key, "format": "json", "limit": _LIMIT, **params},
    )
    resp.raise_for_status()
    return resp.json()


def _similar_artists(client: httpx.Client, api_key: str, artist: str) -> list[dict]:
    try:
        data = _call(client, api_key, "artist.getSimilar", artist=artist)
        items = data.get("similarartists", {}).get("artist", [])
        return [
            {
                "name": a["name"],
                "match_pct": round(float(a.get("match", 0)) * 100),
                "url": a.get("url", ""),
            }
            for a in items
        ]
    except Exception:
        return []


def _artist_top_tracks(client: httpx.Client, api_key: str, artist: str) -> list[dict]:
    try:
        data = _call(client, api_key, "artist.getTopTracks", artist=artist)
        items = data.get("toptracks", {}).get("track", [])
        return [
            {
                "title": t["name"],
                "artist": t.get("artist", {}).get("name", artist),
                "url": t.get("url", ""),
            }
            for t in items
        ]
    except Exception:
        return []


def _tag_top_artists(client: httpx.Client, api_key: str, tag: str) -> list[dict]:
    try:
        data = _call(client, api_key, "tag.getTopArtists", tag=tag)
        items = data.get("topartists", {}).get("artist", [])
        return [{"name": a["name"], "url": a.get("url", "")} for a in items]
    except Exception:
        return []


def _tag_top_tracks(client: httpx.Client, api_key: str, tag: str) -> list[dict]:
    try:
        data = _call(client, api_key, "tag.getTopTracks", tag=tag)
        items = data.get("tracks", {}).get("track", [])
        return [
            {
                "title": t["name"],
                "artist": t.get("artist", {}).get("name", ""),
                "url": t.get("url", ""),
            }
            for t in items
        ]
    except Exception:
        return []
