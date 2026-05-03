"""
portal/app.py -- Twin Portal Flask app
Serves the web UI and proxies requests to:
  - digital-twin API (port 8741) via bridge/twin_api.py
  - Byngox swarm via bridge/byngox.py
  - Chameha voice via NATS (sorabbyngo.chameha.*)
"""
from __future__ import annotations
import logging, os
from flask import Flask, request, jsonify, render_template, send_from_directory

from bridge.twin_api import (
    list_schemas, register_schema,
    create_twin, get_twin, list_twins, delete_twin,
    add_memory, get_memory, forget_node,
    add_member, get_members,
    link_twins, get_relationships,
    push_interaction, aggregate,
)
from bridge.byngox import route_query, notify_twin_updated, notify_safety_flag

log = logging.getLogger("portal")
app = Flask(__name__, template_folder="templates", static_folder="static")


# -- UI -----------------------------------------------------------------------

@app.get("/")
def index():
    return render_template("index.html")


@app.get("/twin/<twin_id>")
def twin_detail(twin_id):
    return render_template("twin.html", twin_id=twin_id)


# -- Schema API ---------------------------------------------------------------

@app.get("/api/schemas")
def api_schemas():
    return jsonify(list_schemas())


@app.post("/api/schemas")
def api_create_schema():
    b = request.json or {}
    result = register_schema(
        type_name=b.get("type_name",""),
        display_name=b.get("display_name",""),
        description=b.get("description",""),
        safety_domains=b.get("safety_domains",[]),
        attributes=b.get("attributes",{}),
    )
    return jsonify(result or {"error": "failed"}), 201 if result else 500


# -- Twin API -----------------------------------------------------------------

@app.get("/api/twins")
def api_list_twins():
    return jsonify(list_twins(
        owner_id=request.args.get("owner"),
        type_name=request.args.get("type"),
    ))


@app.post("/api/twins")
def api_create_twin():
    b = request.json or {}
    result = create_twin(
        owner_id=b.get("owner_id",""),
        name=b.get("name",""),
        type_name=b.get("type_name","person"),
        language=b.get("language","en"),
        region=b.get("region","KE"),
        attributes=b.get("attributes",{}),
    )
    if result:
        notify_twin_updated(result["twin_id"], b.get("owner_id",""))
    return jsonify(result or {"error": "failed"}), 201 if result else 500


@app.get("/api/twins/<twin_id>")
def api_get_twin(twin_id):
    t = get_twin(twin_id)
    return jsonify(t) if t else (jsonify({"error": "not found"}), 404)


@app.delete("/api/twins/<twin_id>")
def api_delete_twin(twin_id):
    return jsonify({"deleted": delete_twin(twin_id)})


# -- Memory -------------------------------------------------------------------

@app.get("/api/twins/<twin_id>/memory")
def api_get_memory(twin_id):
    return jsonify(get_memory(twin_id, request.args.get("category")))


@app.post("/api/twins/<twin_id>/memory")
def api_add_memory(twin_id):
    b = request.json or {}
    result = add_memory(twin_id, b.get("category","general"),
                        b.get("summary",""), float(b.get("confidence",1.0)),
                        b.get("data",{}))
    if result:
        notify_twin_updated(twin_id, "")
    return jsonify(result or {"error": "failed"}), 201 if result else 500


@app.delete("/api/twins/<twin_id>/memory/<node_id>")
def api_forget(twin_id, node_id):
    return jsonify({"deleted": forget_node(twin_id, node_id)})


# -- Members ------------------------------------------------------------------

@app.get("/api/twins/<twin_id>/members")
def api_get_members(twin_id):
    return jsonify(get_members(twin_id))


@app.post("/api/twins/<twin_id>/members")
def api_add_member(twin_id):
    b = request.json or {}
    result = add_member(twin_id, b.get("twin_id",""),
                        b.get("display_name",""), b.get("role","member"),
                        b.get("consent_level","summary"))
    return jsonify(result or {"error": "failed"}), 201 if result else 500


# -- Relationships ------------------------------------------------------------

@app.get("/api/twins/<twin_id>/relationships")
def api_get_relationships(twin_id):
    return jsonify(get_relationships(twin_id))


@app.post("/api/twins/<twin_id>/relationships")
def api_link(twin_id):
    b = request.json or {}
    result = link_twins(twin_id, b.get("target_twin_id",""),
                        b.get("relation","linked_to"),
                        b.get("consent_level","summary"))
    return jsonify(result or {"error": "failed"}), 201 if result else 500


# -- Byngox query routing -----------------------------------------------------

@app.post("/api/query")
def api_query():
    b = request.json or {}
    plan = route_query(
        query=b.get("query",""),
        twin_id=b.get("twin_id",""),
        domain=b.get("domain","general"),
    )
    return jsonify(plan)


# -- Interactions (from Chameha voice) ----------------------------------------

@app.post("/api/twins/<twin_id>/interactions")
def api_interaction(twin_id):
    b = request.json or {}
    ok = push_interaction(twin_id, b.get("role","user"),
                          b.get("content",""), b.get("domain","general"))
    return jsonify({"ok": ok})


# -- Aggregate ----------------------------------------------------------------

@app.post("/api/twins/<twin_id>/aggregate/<member_id>")
def api_aggregate(twin_id, member_id):
    return jsonify({"ok": aggregate(twin_id, member_id)})


# -- Chameha voice ------------------------------------------------------------

@app.post("/api/voice")
@require_auth
def api_voice():
    """
    Receive text from the portal voice bar (after browser STT),
    route to Chameha, return text response (browser handles TTS).
    Falls back to Byngox query routing if Chameha is unavailable.
    """
    from bridge.chameha import ask_personal
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
