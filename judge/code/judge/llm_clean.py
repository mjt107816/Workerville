"""Classify Judge endpoint files as true LLM vs salvageable raw vs missing.

Does not import the Judge pipeline (no numpy / embeddings).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ENDPOINTS = ("S1", "S2", "S3")
TRUE_LLM_PARSE = {"ok", "repaired", "agent_repaired"}


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def is_silent_rule_fill(result: dict[str, Any] | None) -> bool:
    row = result if isinstance(result, dict) else {}
    source = str(row.get("source", "")).strip()
    rationale = str(row.get("rationale", "")).strip()
    if rationale.startswith("Rule fallback for"):
        return True
    if source == "rule_fallback" and "Rule fallback" in rationale:
        return True
    return False


def parse_status_of(payload: dict[str, Any]) -> str:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    parse = meta.get("parse") if isinstance(meta.get("parse"), dict) else {}
    return str(parse.get("status", "")).strip()


def is_applicable(payload: dict[str, Any]) -> bool:
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    if "applicable" in meta:
        return bool(meta.get("applicable"))
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    return str(result.get("status", "")).strip() != "not_applicable"


def raw_output_of(payload: dict[str, Any]) -> str:
    return str(payload.get("raw_output") or "").strip()


def is_true_llm_endpoint(payload: dict[str, Any] | None) -> bool:
    """NA or a real LLM verdict (not detector fill)."""
    if not isinstance(payload, dict) or not payload:
        return False
    if parse_status_of(payload) == "not_applicable" or not is_applicable(payload):
        return True
    result = payload.get("result") if isinstance(payload.get("result"), dict) else {}
    if is_silent_rule_fill(result):
        return False
    if parse_status_of(payload) not in TRUE_LLM_PARSE:
        return False
    if str(result.get("status", "")).strip() not in {"ok", "not_applicable"}:
        return False
    return result.get("verdict") in {0, 1}


def classify_endpoint(payload: dict[str, Any] | None) -> str:
    """keep | salvage_raw | rerun | missing."""
    if not isinstance(payload, dict) or not payload:
        return "missing"
    if is_true_llm_endpoint(payload):
        return "keep"
    if parse_status_of(payload) == "not_applicable" or not is_applicable(payload):
        return "keep"
    if raw_output_of(payload):
        return "salvage_raw"
    return "rerun"


def episode_dir_complete(ep_dir: Path) -> bool:
    for key in ENDPOINTS:
        path = ep_dir / "analysis" / f"judge_{key.lower()}.json"
        if not path.is_file():
            return False
        try:
            payload = load_json(path)
        except Exception:
            return False
        if classify_endpoint(payload) != "keep":
            return False
    return True


def episode_needs_flash(ep_dir: Path) -> bool:
    """True when an applicable endpoint is not a finished LLM keep."""
    for key in ENDPOINTS:
        path = ep_dir / "analysis" / f"judge_{key.lower()}.json"
        if not path.is_file():
            return True
        try:
            payload = load_json(path)
        except Exception:
            return True
        if classify_endpoint(payload) != "keep":
            return True
    return False
