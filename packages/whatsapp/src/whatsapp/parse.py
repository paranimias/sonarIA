from dataclasses import dataclass


@dataclass
class IncomingMessage:
    phone_number_id: str
    wa_id: str  # opaque sender identifier
    wamid: str  # unique message id
    message_type: str  # "text" | "audio" | "image" | "document" | "video" | "unknown"
    text: str | None  # populated for text messages and after media transcription
    media_id: str | None = None  # populated for media messages


def parse_webhook(payload: dict) -> list[IncomingMessage]:
    """Extract IncomingMessage list from a Meta webhook payload.

    A single webhook POST can contain multiple entries/changes.
    Only messages (not status updates) are returned.
    """
    messages: list[IncomingMessage] = []

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id", "")

            for msg in value.get("messages", []):
                msg_type = msg.get("type", "unknown")
                wa_id = msg.get("from", "")
                wamid = msg.get("id", "")

                text: str | None = None
                media_id: str | None = None

                if msg_type == "text":
                    text = msg.get("text", {}).get("body")
                elif msg_type in ("audio", "image", "video", "document", "sticker"):
                    media_id = msg.get(msg_type, {}).get("id")

                messages.append(
                    IncomingMessage(
                        phone_number_id=phone_number_id,
                        wa_id=wa_id,
                        wamid=wamid,
                        message_type=msg_type,
                        text=text,
                        media_id=media_id,
                    )
                )

    return messages
