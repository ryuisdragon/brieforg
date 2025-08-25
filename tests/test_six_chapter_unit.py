import os
import re
import sys
import pytest

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from prompts.unified_prompts import build_six_chapter_prompt
from models.unified_models import SixChapterReport, Section
from tools.unified_tools import SixChapterReportTool


class DummyLLM:
    def generate_json(self, prompt, data):
        def body(txt):
            return f"{txt}（建議圖：長條＋折線）〔經濟部｜2025-06〕"

        sections = [
            {"id": "macro", "title": "宏觀市場概況", "body": body("全球與台灣均呈穩定成長")},
            {"id": "buzz", "title": "聲量趨勢分析", "body": body("冬季疊加政策宣導帶來聲量高峰")},
            {"id": "competitors", "title": "競品分析", "body": body("強排型式在高價段領先")},
            {"id": "brand", "title": "品牌分析", "body": body("喜特麗在安裝與延保有資產優勢")},
            {"id": "audience", "title": "受眾分析", "body": body("換機族在寒流前後被安全議題觸發")},
            {"id": "insight", "title": "洞察小結", "body": body("季節×安全×補助形成主決策鍊")},
        ]
        return {"sections": sections}


class DummyEvidence:
    def collect(self, ctx):
        return {"evidence": [{"id": "e1", "source": "moea"}]}


def test_prompt_builder_pack():
    p = build_six_chapter_prompt({"category": "熱水器", "brand_focus": "喜特麗", "window": "last_12m"})
    assert "system" in p and "tool" in p and "user" in p


def test_tool_and_schema_validation(monkeypatch):
    tool = SixChapterReportTool(llm=DummyLLM(), evidence_provider=DummyEvidence())
    ctx = type("Ctx", (), {"params": {"category": "熱水器", "brand_focus": "喜特麗", "window": "last_12m"}})()
    out = tool.execute(ctx)
    data = out["report"]
    report = SixChapterReport.parse_obj(data)
    ids = [s["id"] for s in data["sections"]]
    assert ids == ["macro", "buzz", "competitors", "brand", "audience", "insight"]

    citation = re.compile(r"〔.+｜\d{4}-(\d{2})(-\d{2})?〕")
    for s in data["sections"]:
        assert citation.search(s["body"]), f"missing citation in {s['id']}"
        assert "•" not in s["body"] and "—" not in s["body"]
