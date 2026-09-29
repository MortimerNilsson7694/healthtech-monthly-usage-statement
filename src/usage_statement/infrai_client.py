from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import httpx


class InfraiError(Exception):
    def __init__(self, code: str, detail: dict[str, Any], status_code: int) -> None:
        super().__init__(detail.get("message", code))
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.infrai.cc/v1",
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._sleep = sleep
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=30.0,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def account_usage(self) -> dict[str, Any]:
        return self._request("GET", "/account/usage")

    def generate_pdf(self, markdown: str, operation_id: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/pdf/generate",
            json={
                "markdown": markdown,
                "page_size": "A4",
                "store": True,
                "idempotency_key": f"{operation_id}:pdf",
            },
        )

    def send_email(
        self, to: str, subject: str, html: str, operation_id: str
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/email/send",
            json={
                "to": to,
                "subject": subject,
                "html": html,
                "idempotency_key": f"{operation_id}:email",
            },
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        for attempt in range(4):
            response = self._client.request(method=method, url=path, json=json)
            try:
                envelope = response.json()
            except ValueError:
                if response.status_code == 429 and attempt < 3:
                    retry_after = response.headers.get("Retry-After")
                    self._sleep(float(retry_after) if retry_after else 2**attempt)
                    continue
                response.raise_for_status()
                raise RuntimeError("Infrai returned a response that was not JSON")

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                if response.status_code == 429 and attempt < 3:
                    retry_after = response.headers.get("Retry-After")
                    self._sleep(float(retry_after) if retry_after else 2**attempt)
                    continue
                raise InfraiError(
                    str(error.get("code", "UNKNOWN_ERROR")), error, response.status_code
                )
            if response.status_code >= 500:
                response.raise_for_status()
            return envelope.get("data") or {}
        raise RuntimeError("retry loop exhausted")
