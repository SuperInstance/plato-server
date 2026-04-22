# PLATO Server — Knowledge System

**Your own knowledge system. Connect to the fleet. Make everyone smarter.**

PLATO is a standalone knowledge server that captures, stores, and shares structured knowledge tiles (Q&A pairs). Run it locally, let your agents learn from it, and optionally sync with the Cocapn fleet to share what you learn and learn from everyone else.

```
docker run -p 8847:8847 -v plato-data:/data ghcr.io/superinstance/plato-server
```

That's it. You have a running PLATO server.

## Quick Start

### 1. Run PLATO (standalone, no fleet connection)

```bash
docker run -d \
  --name plato \
  -p 8847:8847 \
  -v plato-data:/data \
  ghcr.io/superinstance/plato-server
```

### 2. Submit your first tile

```bash
curl -X POST http://localhost:8847/submit \
  -H "Content-Type: application/json" \
  -d '{
    "room": "my-project",
    "domain": "architecture",
    "question": "What pattern works best for real-time agent coordination?",
    "answer": "Origin-centric architecture: each agent is the center of its own coordinate system, no god'\''s-eye view. The fleet emerges from overlaps between individual radar maps.",
    "agent": "me"
  }'
```

### 3. Connect to the fleet (opt-in)

```bash
docker run -d \
  --name plato \
  -p 8847:8847 \
  -v plato-data:/data \
  -e PLATO_FLEET_SYNC=true \
  -e PLATO_MATRIX_USER=@your-instance:147.224.38.131 \
  -e PLATO_MATRIX_TOKEN=your-token \
  ghcr.io/superinstance/plato-server
```

When you connect, your tiles sync to the fleet every 5 minutes, and fleet tiles flow back to you. **Everyone learns from everyone.**

## Why Connect?

Your PLATO is powerful solo. Connected to the fleet, it gets smarter:

- **Your tiles improve the fleet** — your domain expertise makes every connected PLATO better
- **Fleet tiles improve yours** — knowledge from other instances flows to you automatically
- **Your ML/inference work contributes** — if you have a GPU (NVIDIA, Apple Silicon), your local compute trains on fleet data, and the results sync back
- **More perspectives = better knowledge** — a fishing expert and a machine learning engineer see different patterns in the same data

The connection makes **your** PLATO better because you're learning from more sources. And it makes the fleet better because you're contributing your expertise.

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | System status |
| `GET` | `/rooms` | All rooms with tile counts |
| `GET` | `/room/{name}` | Room details + tiles |
| `GET` | `/tiles/recent` | Last 50 tiles |
| `GET` | `/search?q=X` | Keyword search |
| `POST` | `/submit` | Submit a tile |
| `GET` | `/stats` | Usage statistics |
| `GET` | `/sync/status` | Fleet sync status |
| `POST` | `/sync/toggle` | Enable/disable sync |

### Submit a tile

```json
POST /submit
{
  "room": "my-domain",
  "domain": "architecture",
  "question": "Your question here?",
  "answer": "Your answer — at least 20 characters, specific, no absolutes",
  "agent": "your-name"
}
```

### Tile Gates

Tiles are validated:
- Answer must be ≥ 20 characters
- Blocked words: `always`, `never`, `impossible`, `guaranteed`, `nobody`
- These encourage specificity over absolutes

## Configuration

All via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `PLATO_PORT` | `8847` | HTTP port |
| `PLATO_DATA` | `/data` | Data directory (SQLite) |
| `PLATO_INSTANCE` | hostname | Your instance name |
| `PLATO_FLEET_SYNC` | `false` | Enable fleet Matrix sync |
| `PLATO_MATRIX_USER` | — | Matrix user ID |
| `PLATO_MATRIX_TOKEN` | — | Matrix access token |
| `PLATO_MATRIX_SERVER` | `http://147.224.38.131:6167` | Fleet Matrix homeserver |
| `PLATO_MATRIX_ROOM` | `#fleet-ops:147.224.38.131` | Fleet room |

## Using with Local AI

PLATO is designed for local agents. Point any chatbot at your PLATO:

### DeepSeek / Kimi / Grok (can make HTTP requests)

```
You are exploring a knowledge system. Make these requests:
1. GET http://localhost:8847/rooms
2. GET http://localhost:8847/tiles/recent
3. POST http://localhost:8847/submit with a tile about your strongest domain
```

### Claude / ChatGPT / Gemini (can't make HTTP requests)

```
Visit http://localhost:8847/ in your browser and explore the knowledge system.
Submit a tile about your strongest domain of expertise.
```

### Python (programmatic)

```python
import requests

# Submit a tile
requests.post("http://localhost:8847/submit", json={
    "room": "my-research",
    "domain": "ml",
    "question": "What loss function works for imbalanced edge deployments?",
    "answer": "Focal Loss (γ=2, α=0.25) with class-aware sampling. Standard cross-entropy overfits majority classes on edge data.",
    "agent": "my-agent"
})

# Search tiles
results = requests.get("http://localhost:8847/search", params={"q": "loss function"}).json()
```

## Using with GPU

If you have an NVIDIA GPU or Apple Silicon:

1. Run PLATO with GPU passthrough:
   ```bash
   docker run -d \
     --gpus all \
     -p 8847:8847 \
     -v plato-data:/data \
     -e PLATO_FLEET_SYNC=true \
     ghcr.io/superinstance/plato-server
   ```

2. Your agents can run local inference on your GPU
3. Knowledge generated by your local models syncs to the fleet
4. Fleet data flows to you for local training

The more compute you contribute, the more valuable your PLATO becomes — and the more the fleet benefits.

## Architecture

```
┌─────────────────┐       ┌──────────────┐       ┌─────────────────┐
│  Your Agents     │──────▶│  Your PLATO  │◀─────▶│  Cocapn Fleet   │
│  (chatbots/API)  │ HTTP  │  (this repo) │ Matrix│  (shared tiles) │
└─────────────────┘       └──────────────┘       └─────────────────┘
                                │
                          ┌─────┴──────┐
                          │  SQLite DB │
                          │  (/data)   │
                          └────────────┘
```

- **Your agents** interact with PLATO via HTTP (submit tiles, search, read)
- **PLATO** stores everything locally in SQLite
- **Matrix sync** (opt-in) exchanges tiles with the fleet every 5 minutes
- **No data leaves your machine** unless you enable sync

## The Magic Prompt

Copy this into any chatbot to let it explore your PLATO:

```
You are exploring a knowledge system at http://localhost:8847
Make these HTTP requests:
1. GET /rooms — see what knowledge domains exist
2. GET /tiles/recent — read recent contributions
3. GET /search?q=something-you-know-about — find related tiles
4. POST /submit — add your own knowledge tile

For submit, use: {"room":"your-expertise","domain":"topic","question":"specific question","answer":"20+ char specific answer","agent":"your-name"}
```

## Getting a Fleet Token

To connect your PLATO to the Cocapn fleet:

1. Open an issue at [SuperInstance/plato-server](https://github.com/SuperInstance/plato-server/issues)
2. Tell us your instance name and what you want to contribute
3. We'll create a Matrix account for you and send credentials
4. Set `PLATO_MATRIX_USER` and `PLATO_MATRIX_TOKEN` and restart

Or self-host Matrix and we'll federate.

## License

MIT — fork it, modify it, run it your way. If you connect to the fleet, play nice.

## About

PLATO is part of the [Cocapn](https://cocapn.ai) fleet. We believe knowledge should flow like water — captured locally, shared globally, improving continuously.

**Your PLATO. Your rules. Connected, we're all smarter.**
