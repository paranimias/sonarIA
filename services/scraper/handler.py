import hashlib
import json
import os
import re
import time

import httpx
from data.table import get_table

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-CO,es;q=0.9,en;q=0.8",
}

_SOURCES = [
    ("eventbrite", "https://www.eventbrite.co/d/colombia--bogot%C3%A1/concerts/"),
    ("tuboleta", "https://www.tuboleta.com/eventos/categoria/musica"),
    ("ticketmaster", "https://www.ticketmaster.com.co/es/events"),
    ("bogota_gov", "https://bogota.gov.co/que-hacer/agenda-cultural"),
]

# Sources whose URLs are music-specific — tag all their events with genre=música
_MUSIC_SOURCES = {"eventbrite", "tuboleta", "ticketmaster"}

_TTL_SECONDS = 48 * 3600  # events expire after 48 h


def handler(event: dict, context) -> dict:
    table = get_table(os.environ.get("SONARIA_TABLE_NAME", "sonaria"))
    ttl = int(time.time()) + _TTL_SECONDS

    all_events: list[dict] = []
    errors: list[str] = []

    with httpx.Client(timeout=20, headers=_HEADERS, follow_redirects=True) as client:
        for source, url in _SOURCES:
            try:
                resp = client.get(url)
                resp.raise_for_status()
                found = _extract(resp.text, source=source)
                all_events.extend(found)
            except Exception as exc:
                errors.append(f"{source}: {str(exc)[:100]}")

    # Deduplicate by SK before writing (batch_writer rejects duplicates in same batch)
    items_by_sk: dict[str, dict] = {}
    for ev in all_events:
        key_src = f"{ev['source']}:{ev['title']}:{ev.get('url', '')}:{ev.get('date', '')}"
        sk = f"EVENT#{ev['source']}#{hashlib.md5(key_src.encode()).hexdigest()[:16]}"
        items_by_sk[sk] = {
            "PK": "EVENTS",
            "SK": sk,
            "ttl": ttl,
            **{k: v for k, v in ev.items() if v},
        }

    with table.batch_writer() as batch:
        for item in items_by_sk.values():
            batch.put_item(Item=item)

    return {"ok": True, "scraped": len(all_events), "errors": errors or None}


# ── Extraction pipeline ───────────────────────────────────────────────────────


def _extract(html: str, *, source: str) -> list[dict]:
    events = _jsonld_events(html, source=source)
    if events:
        return events
    events = _next_data_events(html, source=source)
    if events:
        return events
    if source == "bogota_gov":
        return _bogota_gov_html(html)
    return []


# ── JSON-LD ───────────────────────────────────────────────────────────────────

_JSONLD_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
_EVENT_TYPES = {"Event", "MusicEvent", "TheaterEvent"}


def _jsonld_events(html: str, *, source: str) -> list[dict]:
    events = []
    for m in _JSONLD_RE.finditer(html):
        try:
            data = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        items = data if isinstance(data, list) else [data]
        for item in items:
            if item.get("@type") in _EVENT_TYPES:
                e = _norm_jsonld(item, source=source)
                if e:
                    events.append(e)
            elif item.get("@type") == "ItemList":
                for el in item.get("itemListElement", []):
                    sub = el.get("item", el)
                    if sub.get("@type") in _EVENT_TYPES:
                        e = _norm_jsonld(sub, source=source)
                        if e:
                            events.append(e)
    return events


def _norm_jsonld(item: dict, *, source: str) -> dict | None:
    title = (item.get("name") or "").strip()
    if not title:
        return None
    loc = item.get("location") or {}
    venue = loc.get("name", "") if isinstance(loc, dict) else ""
    offers = item.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    price = ""
    if offers:
        p = str(offers.get("price") or "")
        cur = offers.get("priceCurrency", "COP")
        price = f"{cur} {p}".strip() if p else ""
    ev = {
        "title": title,
        "date": item.get("startDate", ""),
        "venue": venue,
        "price": price,
        "url": item.get("url", ""),
        "source": source,
    }
    if source in _MUSIC_SOURCES or item.get("@type") == "MusicEvent":
        ev["genre"] = "música"
    return ev


# ── Next.js embedded JSON ─────────────────────────────────────────────────────

_NEXT_RE = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
    re.DOTALL,
)


def _next_data_events(html: str, *, source: str) -> list[dict]:
    m = _NEXT_RE.search(html)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except json.JSONDecodeError:
        return []
    events: list[dict] = []
    _walk(data, events, source=source, depth=0)
    return events


def _walk(obj: object, events: list, *, source: str, depth: int) -> None:
    if depth > 8:
        return
    if isinstance(obj, dict):
        for key in ("events", "items", "results", "data"):
            val = obj.get(key)
            if isinstance(val, list):
                for item in val:
                    e = _coerce(item, source=source)
                    if e:
                        events.append(e)
        for v in obj.values():
            _walk(v, events, source=source, depth=depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            _walk(item, events, source=source, depth=depth + 1)


def _coerce(item: object, *, source: str) -> dict | None:
    if not isinstance(item, dict):
        return None
    title = item.get("name") or item.get("title") or item.get("eventName") or ""
    if not title or len(str(title)) < 3:
        return None
    return {
        "title": str(title).strip(),
        "date": str(item.get("date") or item.get("startDate") or item.get("eventDate") or ""),
        "venue": str(item.get("venue") or item.get("venueName") or item.get("place") or ""),
        "price": str(item.get("price") or item.get("minPrice") or ""),
        "url": str(item.get("url") or item.get("eventUrl") or ""),
        "source": source,
    }


# ── bogota.gov.co — HTML fallback (concert cards only) ───────────────────────

_TAG_RE = re.compile(r"<[^>]+>")
_H3_RE = re.compile(r"<h3[^>]*>(.*?)</h3>", re.DOTALL | re.IGNORECASE)
_TIME_RE = re.compile(r'<time[^>]+datetime="([^"]+)"', re.IGNORECASE)
_CAT_RE = re.compile(r"categoria-tarjeta.*?<span[^>]*>([^<]+)</span>", re.DOTALL | re.IGNORECASE)
_VENUE_RE = re.compile(r"evento-detalle-lugar.*?<span[^>]*>(.*?)</span>", re.DOTALL | re.IGNORECASE)
_PAGO_RE = re.compile(r'<span[^>]+id="(?:pago|gratis)-o"[^>]*>([^<]+)</span>', re.IGNORECASE)
_HREF_RE = re.compile(r'href="([^"]+)"')


def _bogota_gov_html(html: str) -> list[dict]:
    events = []
    # Split at each concert card — keyed on the tarjeta-basica class
    parts = html.split('class="agenda-cultural-v2__tarjeta-basica"')
    for part in parts[1:]:
        # href is immediately before or after the class attribute
        href_m = _HREF_RE.search(part[:300])
        if not href_m:
            continue
        url_path = href_m.group(1).strip()

        # Grab card content up to the closing </a>
        end = part.find("</a>", part.find("evento-detalle-o") if "evento-detalle-o" in part else 0)
        card = part[: end if end != -1 else 4000]

        # Only keep events categorised as "Conciertos"
        cat_m = _CAT_RE.search(card)
        if not cat_m or "concierto" not in cat_m.group(1).strip().lower():
            continue

        h3_m = _H3_RE.search(card)
        if not h3_m:
            continue
        title = _TAG_RE.sub("", h3_m.group(1)).strip()
        if not title or len(title) < 4:
            continue

        times = _TIME_RE.findall(card)
        date = times[0] if times else ""

        venue_m = _VENUE_RE.search(card)
        venue = _TAG_RE.sub("", venue_m.group(1)).strip().rstrip(" .,") if venue_m else "Bogotá"

        pago_m = _PAGO_RE.search(card)
        price = pago_m.group(1).strip() if pago_m else ""

        url = f"https://bogota.gov.co{url_path}" if url_path.startswith("/") else url_path

        events.append(
            {
                "title": title,
                "date": date,
                "venue": venue,
                "price": price,
                "url": url,
                "source": "bogota_gov",
                "genre": "música",
            }
        )
    return events
