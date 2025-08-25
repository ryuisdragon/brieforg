import os
import pytest
import re

pytestmark = pytest.mark.network


def _payload():
    return {
        "session_id": "sess-e2e-001",
        "intent": "six_chapter_report",
        "params": {
            "category": "熱水器",
            "brand_focus": "喜特麗",
            "window": "last_12m",
            "locale": "zh-TW",
        },
        "attachments": [],
    }


def test_chat_turn_six_chapter_httpx(httpx_client):
    resp = httpx_client.post("/chat/turn", json=_payload())
    assert resp.status_code == 200
    data = resp.json()
    sections = data["report"]["sections"]
    ids = [s["id"] for s in sections]
    assert ids == ["macro", "buzz", "competitors", "brand", "audience", "insight"]
    citation = re.compile(r"〔.+｜\d{4}-(\d{2})(-\d{2})?〕")
    for s in sections:
        assert citation.search(s["body"])


def test_chat_turn_six_chapter_fastapi(client):
    resp = client.post("/chat/turn", json=_payload())
    assert resp.status_code == 200
