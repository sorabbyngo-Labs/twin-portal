"""
portal/app.py -- Twin Portal Flask app (with auth)
"""
from __future__ import annotations
import logging
from functools import wraps
from flask import Flask, request, jsonify, render_template, redirect

from bridge.auth import authenticate, verify_token
from bridge.twin_api import (
    list_schemas, register_schema,
    create_twin, get_twin, list_twins, delete_twin,
    add_memory, get_memory, forget_node,
    add_member, get_members,
    link_twins, get_relationships,
    push_interaction, aggregate,
)
from bridge.byngox import route_query, notify_twin_updated
from bridge.chameha import ask_personal

log = logging.getLogger("portal")
app = Flask(__name__, template_folder="templates", static_folder="static")


# -- Auth ---------------------------------------------------------------------

def _token_from_request() -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.cookies.get("portal_token", "")


def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = _token_from_request()
        payload = verify_token(token)
        if not payload:
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect("/login")
        request.owner_id = payload["owner_id"]
        request.username = payload["sub"]
        return f(*args, **kwargs)
    return decorated


# -- Auth routes --------------------------------------------------------------

@app.get("/login")
def login_page():
    return render_template("login.html")


@app.post("/api/auth/login")
def api_login():
    b = request.json or {}
    token = authenticate(b.get("username", ""), b.get("password", ""))
    if not token:
        return jsonify({"error": "invalid credentials"}), 401
    resp = jsonify({"ok": True, "token": token})
    resp.set_cookie("portal_token", token, httponly=True,
                    max_age=8*3600, samesite="Lax")
    return resp


@app.post("/api/auth/logout")
def api_logout():
    resp = jsonify({"ok": True})
    resp.delete_cookie("portal_token")
    return resp


@app.get("/api/auth/me")
@require_auth
def api_me():
    return jsonify({"username": request.username, "owner_id": request.owner_id})


# -- UI -----------------------------------------------------------------------

@app.get("/")
@require_auth
def index():
    return render_template("index.html",
                           owner_id=request.owner_id,
                           username=request.username)


@app.get("/twin/<twin_id>")
@require_auth
def twin_detail(twin_id):
    return render_template("twin.html", twin_id=twin_id,
                           owner_id=request.owner_id)


# -- Schemas ------------------------------------------------------------------

@app.get("/api/schemas")
@require_auth
def api_schemas():
    return jsonify(list_schemas())


@app.post("/api/schemas")
@require_auth
def api_create_schema():
    b = request.json or {}
    result = register_schema(
        type_name=b.get("type_name", ""),
        display_name=b.get("display_name", ""),
        description=b.get("description", ""),
        safety_domains=b.get("safety_domains", []),
        attributes=b.get("attributes", {}),
    )
    return jsonify(result or {"error": "failed"}), 201 if result else 500


# -- Twins --------------------------------------------------------------------

@app.get("/api/twins")
@require_auth
def api_list_twins():
    return jsonify(list_twins(
        owner_id=request.owner_id,
        type_name=request.args.get("type"),
    ))


@app.post("/api/twins")
@require_auth
def api_create_twin():
    b = request.json or {}
    result = create_twin(
        owner_id=request.owner_id,
        name=b.get("name", ""),
        type_name=b.get("type_name", "person"),
        language=b.get("language", "en"),
        region=b.get("region", "KE"),
        attributes=b.get("attributes", {}),
    )
    if result:
        notify_twin_updated(result["twin_id"], request.owner_id)
    return jsonify(result or {"error": "failed"}), 201 if result else 500


@app.get("/api/twins/<twin_id>")
@require_auth
def api_get_twin(twin_id):
    t = get_twin(twin_id)
    return jsonify(t) if t else (jsonify({"error": "not found"}), 404)


@app.delete("/api/twins/<twin_id>")
@require_auth
def api_delete_twin(twin_id):
    return jsonify({"deleted": delete_twin(twin_id)})


# -- Memory -------------------------------------------------------------------

@app.get("/api/twins/<twin_id>/memory")
@require_auth
def api_get_memory(twin_id):
    return jsonify(get_memory(twin_id, request.args.get("category")))


@app.post("/api/twins/<twin_id>/memory")
@require_auth
def api_add_memory(twin_id):
    b = request.json or {}
    result = add_memory(twin_id, b.get("category", "general"),
                        b.get("summary", ""), float(b.get("confidence", 1.0)),
                        b.get("data", {}))
    if result:
        notify_twin_updated(twin_id, request.owner_id)
    return jsonify(result or {"error": "failed"}), 201 if result else 500


@app.delete("/api/twins/<twin_id>/memory/<node_id>")
@require_auth
def api_forget(twin_id, node_id):
    return jsonify({"deleted": forget_node(twin_id, node_id)})


# -- Members ------------------------------------------------------------------

@app.get("/api/twins/<twin_id>/members")
@require_auth
def api_get_members(twin_id):
    return jsonify(get_members(twin_id))


@app.post("/api/twins/<twin_id>/members")
@require_auth
def api_add_member(twin_id):
    b = request.json or {}
    result = add_member(twin_id, b.get("twin_id", ""),
                        b.get("display_name", ""), b.get("role", "member"),
                        b.get("consent_level", "summary"))
    return jsonify(result or {"error": "failed"}), 201 if result else 500


# -- Relationships ------------------------------------------------------------

@app.get("/api/twins/<twin_id>/relationships")
@require_auth
def api_get_relationships(twin_id):
    return jsonify(get_relationships(twin_id))


@app.post("/api/twins/<twin_id>/relationships")
@require_auth
def api_link(twin_id):
    b = request.json or {}
    result = link_twins(twin_id, b.get("target_twin_id", ""),
                        b.get("relation", "linked_to"),
                        b.get("consent_level", "summary"))
    return jsonify(result or {"error": "failed"}), 201 if result else 500


# -- Byngox query routing -----------------------------------------------------

@app.post("/api/query")
@require_auth
def api_query():
    b = request.json or {}
    plan = route_query(query=b.get("query", ""),
                       twin_id=b.get("twin_id", ""),
                       domain=b.get("domain", "general"))
    return jsonify(plan)


# -- Chameha voice ------------------------------------------------------------

@app.post("/api/voice")
@require_auth
def api_voice():
    b = request.json or {}
    text    = b.get("text", "")
    twin_id = b.get("twin_id", "")
    domain  = b.get("domain", "general")
    if not text:
        return jsonify({"error": "text required"}), 400
    response = ask_personal(text, request.owner_id, twin_id, domain)
    if not response:
        plan = route_query(query=text, twin_id=twin_id, domain=domain)
        return jsonify({"response": f"Routing to {', '.join(plan['agents'])}...",
                        "agents": plan["agents"], "fallback": True})
    return jsonify({"response": response, "fallback": False})


# -- Interactions -------------------------------------------------------------

@app.post("/api/twins/<twin_id>/interactions")
@require_auth
def api_interaction(twin_id):
    b = request.json or {}
    ok = push_interaction(twin_id, b.get("role", "user"),
                          b.get("content", ""), b.get("domain", "general"))
    return jsonify({"ok": ok})


# -- Aggregate ----------------------------------------------------------------

@app.post("/api/twins/<twin_id>/aggregate/<member_id>")
@require_auth
def api_aggregate(twin_id, member_id):
    return jsonify({"ok": aggregate(twin_id, member_id)})
