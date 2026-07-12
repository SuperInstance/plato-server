# PLATO Server — Knowledge System

> **Your own knowledge system. Connect to the fleet. Make everyone smarter.**

[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

## Overview

PLATO is a standalone knowledge server that captures, stores, and shares structured knowledge tiles (Q&A pairs). Run it locally, let your agents learn from it, and optionally sync with the Cocapn fleet to share what you learn and learn from everyone else.

## Quick Start

### Docker (recommended)

```bash
docker run -d \
  --name plato \
  -p 8847:8847 \
  -v plato-data:/data \
  ghcr.io/superinstance/plato-server
```

### From Source

```bash
git clone https://github.com/SuperInstance/plato-server.git
cd plato-server
pip install -e .
python -m plato_server
```

## How It Works

- **Solo mode** (default): Your agents interact with PLATO via HTTP. Everything stays on your machine.
- **Fleet mode** (opt-in): Your tiles sync to the Cocapn fleet via Matrix. Fleet tiles flow back. Everyone learns from everyone.

## API Highlights

PLATO exposes a simple HTTP API on port 8847:

- `POST /ask` — Submit a question, get an answer (and generate a tile)
- `GET /tiles` — Browse knowledge tiles
- `POST /submit_tile` — Submit a tile directly
- `GET /rooms` — List PLATO rooms
- `GET /search?q=...` — Full-text search across tiles

## Architecture

```
Your Agents → HTTP API → PLATO Server → SQLite Storage
                                ↓
                    Agent Sessions (spawn)
                                ↓
                    Knowledge Tiles → Submit → Store
                                ↓ (opt-in)
                    Cocapn Fleet Sync (Matrix)
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PLATO_PORT` | `8847` | HTTP server port |
| `PLATO_DATA` | `./data` | Data directory |
| `PLATO_FLEET_SYNC` | `false` | Enable fleet sync |
| `PLATO_API_KEY` | — | LLM API key for agent sessions |

## Resources

- [GitHub Repository](https://github.com/SuperInstance/plato-server)
- [PLATO Engine Block (C)](https://github.com/SuperInstance/plato-engine-block-c)
- [PLATO Wire Protocol](https://github.com/SuperInstance/AI-Writings/blob/main/PLATO_WIRE_PROTOCOL.md)
- [SuperInstance Ecosystem](https://github.com/SuperInstance/SuperInstance)

---

*Part of the [SuperInstance](https://github.com/SuperInstance) ecosystem.*
