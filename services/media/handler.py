import json
import os
from datetime import datetime, timezone

import boto3
import httpx
from common.logging import get_logger

logger = get_logger()

_GRAPH_API_BASE = "https://graph.facebook.com/v19.0"

_MEDIA_EXTENSIONS = {
    "audio": "ogg",
    "image": "jpg",
    "video": "mp4",
    "document": "bin",
    "sticker": "webp",
}


def _cfg(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


_s3 = boto3.client("s3")
_sqs = boto3.client("sqs")


def handler(event: dict, context) -> dict:
    records = event.get("Records", [])
    for record in records:
        try:
            _process_record(record)
        except Exception as exc:  # noqa: BLE001
            logger.error("media_error", error=str(exc), record=record.get("messageId"))
    return {"statusCode": 200}


def _process_record(record: dict) -> None:
    msg = json.loads(record["body"])
    media_id: str = msg["media_id"]
    media_type: str = msg["message_type"]
    wa_id: str = msg["wa_id"]
    wamid: str = msg["wamid"]
    phone_number_id: str = msg["phone_number_id"]

    access_token = _cfg("META_ACCESS_TOKEN")

    # 1. Get media URL from Meta Graph API
    media_url = _get_media_url(media_id, access_token)

    # 2. Download media bytes
    media_bytes = _download_media(media_url, access_token)

    # 3. Save to S3
    s3_key = _build_s3_key(wa_id, media_type)
    _s3.put_object(
        Bucket=_cfg("MEDIA_BUCKET"),
        Key=s3_key,
        Body=media_bytes,
    )
    logger.info("media_saved", s3_key=s3_key, media_type=media_type, wamid=wamid)

    # 4. Transcribe / extract text
    text = _extract_text(media_bytes, media_type)

    # 5. Re-enqueue as text message for the agent
    _enqueue_text(
        wa_id=wa_id,
        wamid=wamid,
        phone_number_id=phone_number_id,
        text=text,
        s3_key=s3_key,
    )


def _get_media_url(media_id: str, access_token: str) -> str:
    resp = httpx.get(
        f"{_GRAPH_API_BASE}/{media_id}",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10.0,
    )
    resp.raise_for_status()
    return resp.json()["url"]


def _download_media(url: str, access_token: str) -> bytes:
    resp = httpx.get(
        url,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.content


def _build_s3_key(wa_id: str, media_type: str) -> str:
    now = datetime.now(tz=timezone.utc)
    ext = _MEDIA_EXTENSIONS.get(media_type, "bin")
    ts = int(now.timestamp() * 1000)
    return f"{wa_id}/{now.year}/{now.month:02d}/{now.day:02d}/{media_type}/{ts}.{ext}"


def _extract_text(media_bytes: bytes, media_type: str) -> str:
    if media_type == "audio":
        return _transcribe_audio(media_bytes)
    # For images: return a placeholder — vision processing is handled by the agent ctx
    return f"[{media_type} recibido]"


def _transcribe_audio(audio_bytes: bytes) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=_cfg("OPENAI_API_KEY"))
    # OpenAI Whisper expects a file-like object with a name
    import io

    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = "audio.ogg"
    transcript = client.audio.transcriptions.create(model="whisper-1", file=audio_file)
    return transcript.text


def _enqueue_text(*, wa_id: str, wamid: str, phone_number_id: str, text: str, s3_key: str) -> None:
    body = json.dumps(
        {
            "wa_id": wa_id,
            "wamid": wamid,
            "phone_number_id": phone_number_id,
            "message_type": "text",
            "text": text,
            "media_id": None,
            "s3_key": s3_key,
        }
    )
    _sqs.send_message(
        QueueUrl=_cfg("SQS_QUEUE_URL"),
        MessageBody=body,
        MessageGroupId=wa_id,
        MessageDeduplicationId=f"{wamid}-transcribed",
    )
