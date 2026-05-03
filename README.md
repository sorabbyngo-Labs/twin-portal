# twin-portal

> Web interface for the Novela digital twin ecosystem.
> Powered by Chameha (voice) and Byngox (8-agent swarm reasoning).

## What it is

Twin Portal is the face of the digital twin ecosystem. Users create, manage,
and interact with any twin type — person, church, farm, hospital, organisation —
through a voice-first web interface powered by Chameha and Byngox.

## Architecture
User (voice/text)
|
Chameha (STT -> intent -> TTS)
|
Byngox coordination_agent (ACP routing)
|-- context_agent     -> loads twin memory
|-- health_agent      -> medical twin queries
|-- learning_agent    -> twin improvement
|-- security_agent    -> auth + cyberwall
|
digital-twin API (port 8741)
|
Twin Factory (any entity type)
## Stack

| Layer | Tech |
|-------|------|
| Frontend | HTML + vanilla JS — offline-capable |
| Voice | Chameha (Whisper STT + Coqui TTS) |
| Reasoning | Byngox 8-agent swarm via NATS ACP |
| Twin API | digital-twin REST API (port 8741) |
| Bridge | Python/Flask (port 5050) |
| Auth | Chameha TwinSession via identity.py |

## Quick start

```bash
pip install -r requirements.txt
python3 main.py    # portal on port 5050
```

## Part of Sorabbyngo ecosystem

| Repo | Role |
|------|------|
| chameha | Voice layer |
| digital-twin | Twin factory + API |
| byngox | Swarm reasoning |
| cml | Safety filter |
| byngonet | Mesh network |
| sorabbyngo-os | Kernel |

Sorabbyngo Company · Kisii, Kenya · 2026
Rhythm of Digital Life
