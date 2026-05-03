"""
bridge/chameha.py -- Chameha voice bridge
Connects the portal voice bar to Chameha STT/TTS via NATS.
In offline mode, falls back to browser Web Speech API (handled in JS).

NATS topics used:
  publish: sorabbyngo.chameha.public.voice.input  (send audio/text to Chameha)
  subscribe: sorabbyngo.chameha.public.voice.output (receive Chameha response)
  publish: sorabbyngo.chameha.personal.{user_id}.voice.input
  subscribe: sorabbyngo.chameha.personal.{user_id}.voice.output
"""
from __future__ import annotations
import asyncio, json, logging, os, time
from typing import Optional

log = logging.getLogger("portal.chameha")

NATS_URL   = os.getenv("NATS_URL", "nats://localhost:4222")
CHAMEHA_TIMEOUT = float(os.getenv("CHAMEHA_TIMEOUT_S", "10"))


async def _send_to_chameha(topic: str, text: str,
                            twin_id: str = "", domain: str = "general") -> Optional[str]:
    """Send text to Chameha via NATS and wait for response."""
    try:
        import nats
        nc = await nats.connect(NATS_URL)
        reply_topic = f"portal.reply.{int(time.time()*1000)}"
        sub = await nc.subscribe(reply_topic)
        await nc.publish(topic, json.dumps({
            "text":      text,
            "twin_id":   twin_id,
            "domain":    domain,
            "reply_to":  reply_topic,
        }).encode())
        try:
            msg = await asyncio.wait_for(sub.next_msg(), timeout=CHAMEHA_TIMEOUT)
            data = json.loads(msg.data.decode())
            await nc.drain()
            return data.get("response", "")
        except asyncio.TimeoutError:
            log.warning("chameha response timeout")
            await nc.drain()
            return None
    except Exception as e:
        log.warning("chameha bridge error: %s", e)
        return None


def ask_public(text: str, domain: str = "general") -> Optional[str]:
    """Send a query to Public Chameha (no personal twin context)."""
    topic = "sorabbyngo.chameha.public.voice.input"
    return asyncio.run(_send_to_chameha(topic, text, domain=domain))


def ask_personal(text: str, owner_id: str,
                 twin_id: str = "", domain: str = "general") -> Optional[str]:
    """Send a query to Personal Chameha (twin context loaded)."""
    topic = f"sorabbyngo.chameha.personal.{owner_id}.voice.input"
    return asyncio.run(_send_to_chameha(topic, text, twin_id=twin_id, domain=domain))
