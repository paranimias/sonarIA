import httpx

_GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


class WhatsAppClient:
    def __init__(self, access_token: str, phone_number_id: str) -> None:
        self._token = access_token
        self._phone_number_id = phone_number_id
        self._http = httpx.Client(
            base_url=_GRAPH_API_BASE,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10.0,
        )

    def send_text(self, *, to: str, text: str) -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        response = self._http.post(
            f"/{self._phone_number_id}/messages",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def send_media(self, *, to: str, media_type: str, media_id: str, caption: str = "") -> dict:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": media_type,
            media_type: {"id": media_id, "caption": caption},
        }
        response = self._http.post(
            f"/{self._phone_number_id}/messages",
            json=payload,
        )
        response.raise_for_status()
        return response.json()

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()
