from typing import Protocol

class CMSProvider(Protocol):
    def publish(self, *, slug: str, html_body: str, metadata: dict,
                image_bytes: bytes | None) -> str | None: ...