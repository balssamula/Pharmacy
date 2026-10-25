"""Server-side Supabase token storage. Do not expose the service key in browser/UI.

Requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in Streamlit Secrets.
No automatic OAuth refresh happens in Streamlit. The Edge Function is the sole refresher.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
import streamlit as st

LOGGER = logging.getLogger(__name__)
TABLE = "salla_oauth_tokens"


def _secret(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        try:
            value = str(st.secrets.get(name, ""))
        except (FileNotFoundError, AttributeError, KeyError):
            pass
    return str(value).strip()


def is_configured() -> bool:
    return bool(_secret("SUPABASE_URL") and _secret("SUPABASE_SERVICE_ROLE_KEY"))


def _request(method: str, *, params=None, payload=None, prefer: str = "return=representation") -> Any:
    url = _secret("SUPABASE_URL").rstrip("/")
    key = _secret("SUPABASE_SERVICE_ROLE_KEY")
    if not url.startswith("https://") or not key:
        raise RuntimeError("Supabase لم يُضبط بعد في Secrets")
    if "/rest/v1" in url or "/functions/v1" in url:
        raise RuntimeError("SUPABASE_URL يجب أن يكون رابط المشروع الأساسي دون /rest/v1 أو /functions/v1")
    if key.startswith("sb_publishable_"):
        raise RuntimeError("استخدم مفتاح sb_secret_ الخاص بالخادم، وليس sb_publishable_")
    headers = {"apikey": key, "Accept": "application/json",
               "Content-Type": "application/json", "Prefer": prefer}
    # Supabase's modern sb_secret_ is NOT a JWT. Send it as apikey only.
    # JWT-based legacy service_role keys also work during migration.
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {key}"
    try:
        response = requests.request(
            method, f"{url}/rest/v1/{TABLE}", params=params, json=payload,
            headers=headers,
            timeout=(6, 15),
        )
        response.raise_for_status()
        return response.json() if response.content else []
    except requests.RequestException as exc:
        LOGGER.error("Supabase token repository HTTP failure: %s", type(exc).__name__)
        raise RuntimeError("تعذر الاتصال بمخزن الرموز في Supabase، راجع إعدادات الاتصال والجدول") from None


def list_stores() -> list[dict]:
    data = _request("GET", params={"select": "merchant_id,store_name,access_token,expires_at,token_updated_at,connection_status,last_error,last_refresh_attempt_at,last_successful_refresh_at,installed_at", "order": "store_name.asc"})
    return data if isinstance(data, list) else []


def get_store(merchant_id: str) -> dict | None:
    mid = str(merchant_id or "").strip()
    if not mid:
        return None
    rows = _request("GET", params={"merchant_id": f"eq.{mid}", "select": "merchant_id,store_name,access_token,expires_at,token_updated_at,connection_status,last_error,last_refresh_attempt_at,last_successful_refresh_at", "limit": "1"})
    return rows[0] if rows else None


def save_credentials(merchant_id: str, store_name: str, access_token: str, refresh_token: str,
                     days_left: float = 14.0, replace: bool = False,
                     initial_status: str = "connected") -> bool:
    if initial_status not in ("connected", "review_required"):
        raise ValueError("حالة استيراد غير مسموح بها")
    mid = str(merchant_id or "").strip()
    if not mid or not str(access_token).strip() or not str(refresh_token).strip():
        raise ValueError("يلزم معرف المتجر والرمزان معًا")
    existing = get_store(mid)
    if existing and not replace:
        return False
    if existing and existing.get("connection_status") == "refreshing":
        raise RuntimeError("تجديد الرموز جارٍ لهذا المتجر؛ لا يمكن تعديلها الآن")
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(days=min(14, max(.01, float(days_left))))
    row = {"merchant_id": mid, "store_name": str(store_name or mid),
           "access_token": str(access_token).strip(),
           "refresh_token": str(refresh_token).strip(),
           "expires_at": expiry.isoformat(), "token_updated_at": now.isoformat(),
           "connection_status": initial_status,
           "last_error": ("Imported from stores.json: verify token validity before enabling renewal"
                          if initial_status == "review_required" else None),
           "last_refresh_attempt_at": None, "lock_nonce": None, "lock_acquired_at": None}
    if existing:
        _request("PATCH", params={"merchant_id": f"eq.{mid}"}, payload=row)
    else:
        _request("POST", payload=row)
    return True


def store_health(store: dict) -> tuple[str, str, float | None]:
    status = str(store.get("connection_status") or "unconfigured")
    expiry = store.get("expires_at")
    days_left = None
    if expiry:
        try:
            days_left = (datetime.fromisoformat(str(expiry).replace("Z", "+00:00")) - datetime.now(timezone.utc)).total_seconds() / 86400
        except ValueError:
            pass
    labels = {"connected": "🟢 متصل", "refreshing": "🔄 تجديد جارٍ",
              "review_required": "🟠 يحتاج مراجعة", "reconnect_required": "🔴 إعادة تفويض مطلوبة"}
    if status == "connected" and days_left is not None and days_left <= 0:
        return "🟠 انتهت صلاحية الوصول", status, days_left
    if status == "connected" and days_left is not None and days_left <= 3:
        return "🟡 التجديد قريب", status, days_left
    return labels.get(status, "⚪ غير معروف"), status, days_left
