"""
smia_client.py — the one place that knows how to talk to smia. Every
enrichment proxy route in routes/enrich.py goes through this, so smia's base
URL and bearer token are never duplicated per route (design.md D2).

A network failure (smia unreachable) raises SmiaUnavailableError; smia's own
response — success or failure — is returned as a plain (status, body) pair
so the caller can pass it straight through unchanged (D3: no retry, no
reinterpretation of what smia itself reported).
"""

from __future__ import annotations

import os

import requests

SMIA_BASE_URL_ENV = "SMIA_BASE_URL"
SMIA_AUTH_TOKEN_ENV = "SMIA_AUTH_TOKEN"


class SmiaUnavailableError(Exception):
    """smia could not be reached at all — distinct from smia responding with
    its own error body, which travels back as a normal (status, body) pair."""


def _base_url() -> str:
    base = os.environ.get(SMIA_BASE_URL_ENV)
    if not base:
        raise SmiaUnavailableError(f"{SMIA_BASE_URL_ENV} is not configured")
    return base.rstrip("/")


def _headers() -> dict:
    return {"Authorization": f"Bearer {os.environ.get(SMIA_AUTH_TOKEN_ENV, '')}"}


def _json_or_text(resp: requests.Response):
    try:
        return resp.json()
    except ValueError:
        return {"error": resp.text}


def post(path: str, json: dict, timeout: float = 20.0) -> tuple[int, dict]:
    try:
        resp = requests.post(f"{_base_url()}{path}", json=json, headers=_headers(), timeout=timeout)
    except requests.RequestException as exc:
        raise SmiaUnavailableError(str(exc)) from exc
    return resp.status_code, _json_or_text(resp)


def get(path: str, timeout: float = 20.0) -> tuple[int, dict]:
    try:
        resp = requests.get(f"{_base_url()}{path}", headers=_headers(), timeout=timeout)
    except requests.RequestException as exc:
        raise SmiaUnavailableError(str(exc)) from exc
    return resp.status_code, _json_or_text(resp)


def get_bytes(path: str, timeout: float = 30.0) -> tuple[int, bytes, str]:
    """For fetching raw audio bytes off a /tts candidate's sha256 (smia's
    GET /tts/{key} serves raw bytes when `key` is an audio hash rather than
    a lookup resource id — confirmed against a live smia response)."""
    try:
        resp = requests.get(f"{_base_url()}{path}", headers=_headers(), timeout=timeout)
    except requests.RequestException as exc:
        raise SmiaUnavailableError(str(exc)) from exc
    return resp.status_code, resp.content, resp.headers.get("Content-Type", "audio/mpeg")
