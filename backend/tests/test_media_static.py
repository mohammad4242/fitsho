from __future__ import annotations

import mimetypes

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_static_media_serves_webp_with_explicit_content_type(
    test_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(mimetypes.types_map, ".webp", raising=False)
    app = create_app(test_settings)
    poster = test_settings.media_root / "exercises" / "preview.poster.webp"
    poster.parent.mkdir(parents=True, exist_ok=True)
    poster.write_bytes(b"RIFF\x00\x00\x00\x00WEBP")

    with TestClient(app) as client:
        response = client.get("/media/exercises/preview.poster.webp")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
