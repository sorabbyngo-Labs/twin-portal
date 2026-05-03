"""
bridge/twin_api.py -- Bridge to digital-twin API (port 8741)
Portal calls these functions instead of hitting the twin API directly.
Handles auth, error recovery, and offline fallback.
"""
from __future__ import annotations
import os, logging, requests
from typing import Optional

log = logging.getLogger("portal.bridge.twin")

TWIN_API = os.getenv("TWIN_API_BASE", "http://localhost:8741")
TIMEOUT  = int(os.getenv("TWIN_TIMEOUT_S", "5"))


def _headers() -> dict:
    key = os.getenv("TWIN_API_KEY", "")
    h = {"Content-Type": "application/json"}
    if key:
        h["Authorization"] = f"Bearer {key}"
    return h


def _get(path: str) -> Optional[dict]:
    try:
        r = requests.get(f"{TWIN_API}{path}", headers=_headers(), timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning("twin API GET %s failed: %s", path, e)
        return None


def _post(path: str, body: dict) -> Optional[dict]:
    try:
        r = requests.post(f"{TWIN_API}{path}", json=body, headers=_headers(), timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log.warning("twin API POST %s failed: %s", path, e)
        return None


def _delete(path: str) -> bool:
    try:
        r = requests.delete(f"{TWIN_API}{path}", headers=_headers(), timeout=TIMEOUT)
        r.raise_for_status()
        return True
    except Exception as e:
        log.warning("twin API DELETE %s failed: %s", path, e)
        return False


# -- Schemas ------------------------------------------------------------------

def list_schemas() -> list:
    return _get("/v1/twins/schemas") or []


def register_schema(type_name: str, display_name: str = "",
                    description: str = "", safety_domains: list = None,
                    attributes: dict = None) -> Optional[dict]:
    return _post("/v1/twins/schemas", {
        "type_name":      type_name,
        "display_name":   display_name,
        "description":    description,
        "safety_domains": safety_domains or [],
        "attributes":     attributes or {},
    })


# -- Twins --------------------------------------------------------------------

def create_twin(owner_id: str, name: str, type_name: str,
                language: str = "en", region: str = "KE",
                attributes: dict = None) -> Optional[dict]:
    return _post("/v1/twins", {
        "owner_id":   owner_id,
        "name":       name,
        "type_name":  type_name,
        "language":   language,
        "region":     region,
        "attributes": attributes or {},
    })


def get_twin(twin_id: str) -> Optional[dict]:
    return _get(f"/v1/twins/{twin_id}")


def list_twins(owner_id: str = None, type_name: str = None) -> list:
    params = []
    if owner_id:  params.append(f"owner={owner_id}")
    if type_name: params.append(f"type={type_name}")
    qs = "?" + "&".join(params) if params else ""
    return _get(f"/v1/twins{qs}") or []


def delete_twin(twin_id: str) -> bool:
    return _delete(f"/v1/twins/{twin_id}")


# -- Memory -------------------------------------------------------------------

def add_memory(twin_id: str, category: str, summary: str,
               confidence: float = 1.0, data: dict = None) -> Optional[dict]:
    return _post(f"/v1/twins/{twin_id}/memory", {
        "category":   category,
        "summary":    summary,
        "confidence": confidence,
        "data":       data or {},
    })


def get_memory(twin_id: str, category: str = None) -> list:
    qs = f"?category={category}" if category else ""
    return _get(f"/v1/twins/{twin_id}/memory{qs}") or []


def forget_node(twin_id: str, node_id: str) -> bool:
    return _delete(f"/v1/twins/{twin_id}/memory/{node_id}")


# -- Members ------------------------------------------------------------------

def add_member(twin_id: str, member_twin_id: str, display_name: str,
               role: str = "member", consent_level: str = "summary") -> Optional[dict]:
    return _post(f"/v1/twins/{twin_id}/members", {
        "twin_id":       member_twin_id,
        "display_name":  display_name,
        "role":          role,
        "consent_level": consent_level,
    })


def get_members(twin_id: str) -> list:
    return _get(f"/v1/twins/{twin_id}/members") or []


# -- Relationships ------------------------------------------------------------

def link_twins(twin_id: str, target_twin_id: str,
               relation: str, consent_level: str = "summary") -> Optional[dict]:
    return _post(f"/v1/twins/{twin_id}/relationships", {
        "target_twin_id": target_twin_id,
        "relation":       relation,
        "consent_level":  consent_level,
    })


def get_relationships(twin_id: str) -> list:
    return _get(f"/v1/twins/{twin_id}/relationships") or []


# -- Interactions (from Chameha) ----------------------------------------------

def push_interaction(twin_id: str, role: str,
                     content: str, domain: str = "general") -> bool:
    result = _post(f"/v1/twins/{twin_id}/interactions", {
        "role":    role,
        "content": content,
        "domain":  domain,
    })
    return result is not None


# -- Aggregation --------------------------------------------------------------

def aggregate(twin_id: str, member_twin_id: str) -> bool:
    result = _post(f"/v1/twins/{twin_id}/aggregate/{member_twin_id}", {})
    return result is not None
