"""
bridge/byngox.py -- Bridge to Byngox 8-agent swarm via NATS ACP
Portal routes complex queries through the swarm instead of calling
the twin API directly. Byngox coordination_agent decides which
agents handle the query.

ACP topic: sorabbyngo.byngox.acp.<target_agent>
"""
from __future__ import annotations
import asyncio, json, logging, os, time, uuid
from typing import Optional

log = logging.getLogger("portal.bridge.byngox")

NATS_URL   = os.getenv("NATS_URL", "nats://localhost:4222")
ACP_PREFIX = "sorabbyngo.byngox.acp"
TIMEOUT_S  = float(os.getenv("BYNGOX_TIMEOUT_S", "8"))


def _acp_message(from_agent: str, to_agent: str,
                 action: str, payload: dict) -> dict:
    return {
        "from":      from_agent,
        "to":        to_agent,
        "action":    action,
        "payload":   payload,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "request_id": str(uuid.uuid4()),
    }


async def _publish(subject: str, message: dict) -> None:
    try:
        import nats
        nc = await nats.connect(NATS_URL)
        await nc.publish(subject, json.dumps(message).encode())
        await nc.drain()
    except Exception as e:
        log.warning("byngox publish failed: %s", e)


def route_query(query: str, twin_id: str,
                domain: str = "general") -> dict:
    """
    Route a portal query through the Byngox coordination_agent.
    Returns a routing plan — which agents will handle the query.

    In production this is async over NATS. Here we return the
    routing plan synchronously so the portal can show the user
    which agents are active before the response arrives.
    """
    agent_map = {
        "medical":   ["coordination_agent", "health_agent", "drug_agent"],
        "clinical":  ["coordination_agent", "health_agent"],
        "financial": ["coordination_agent", "context_agent"],
        "legal":     ["coordination_agent", "context_agent"],
        "security":  ["coordination_agent", "security_agent"],
        "network":   ["coordination_agent", "network_agent"],
        "learning":  ["coordination_agent", "learning_agent"],
        "general":   ["coordination_agent", "context_agent"],
    }
    agents = agent_map.get(domain, agent_map["general"])
    msg = _acp_message(
        from_agent="twin_portal",
        to_agent="coordination_agent",
        action="route_query",
        payload={"query": query, "twin_id": twin_id, "domain": domain},
    )
    asyncio.run(_publish(f"{ACP_PREFIX}.coordination_agent", msg))
    return {
        "request_id": msg["request_id"],
        "agents":     agents,
        "domain":     domain,
        "twin_id":    twin_id,
        "status":     "routed",
    }


def notify_twin_updated(twin_id: str, owner_id: str) -> None:
    """Tell context_agent that a twin has been updated — refresh memory."""
    msg = _acp_message(
        from_agent="twin_portal",
        to_agent="context_agent",
        action="twin_updated",
        payload={"twin_id": twin_id, "owner_id": owner_id},
    )
    asyncio.run(_publish(f"{ACP_PREFIX}.context_agent", msg))


def notify_safety_flag(twin_id: str, domain: str, confidence: float) -> None:
    """Alert security_agent of a low-confidence high-stakes response."""
    msg = _acp_message(
        from_agent="twin_portal",
        to_agent="security_agent",
        action="safety_flag",
        payload={"twin_id": twin_id, "domain": domain, "confidence": confidence},
    )
    asyncio.run(_publish(f"{ACP_PREFIX}.security_agent", msg))
