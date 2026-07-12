# PLATO Server — Knowledge System

[![CI](https://github.com/SuperInstance/plato-server/actions/workflows/ci-python.yml/badge.svg)](https://github.com/SuperInstance/plato-server/actions/workflows/ci-python.yml)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Docker](https://img.shields.io/badge/docker-ghcr.io-superinstance%2Fplato--server-blue.svg)](https://github.com/SuperInstance/plato-server/pkgs/container/plato-server)

> **Your own knowledge system. Connect to the fleet. Make everyone smarter.**

---

## Quick Start

```bash
docker run -d --name plato -p 8847:8847 -v plato-data:/data ghcr.io/superinstance/plato-server
```

```bash
# Submit your first knowledge tile
curl -X POST http://localhost:8847/submit \
  -H "Content-Type: application/json" \
  -d '{"room":"my-project","question":"What is FLUX?","answer":"A markdown-to-bytecode runtime for AI agents","agent":"me"}'
```

---

## What It Does

PLATO is a standalone knowledge server that captures, stores, and shares structured knowledge tiles (Q&A pairs). Run it locally, let your agents learn from it, and optionally sync with the Cocapn fleet to share what you learn and learn from everyone else.

**Solo mode** (default): Your agents interact with PLATO via HTTP. Everything stays on your machine. **Fleet mode** (opt-in): Your tiles sync to the Cocapn fleet via Matrix. Fleet tiles flow back. Everyone learns from everyone. PLATO can also spawn its own agents — describe what you want, and it picks the right "armor type" (Scholar, Builder, Scout, etc.) and model from your bring-your-own-keys configuration.

---

## Architecture

PLATO Server is the **knowledge system layer** of the SuperInstance ecosystem. It stores tiles in SQLite, serves them via HTTP, and optionally federates with other PLATO instances via Matrix sync every 5 minutes. It connects to the [PLATO Engine Block](https://github.com/SuperInstance/plato-engine-block-c) family for embedded/edge deployments, and to [FLUX](https://github.com/SuperInstance/flux-runtime) agents that use PLATO as their knowledge substrate.

```
┌──────────────────────────────────────────────┐
│              PLATO Server :8847               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ HTTP API │  │ Agent    │  │ Fleet    │   │
│  │ /submit  │  │ Spawner  │  │ Sync     │   │
│  │ /search  │  │ /spawn   │  │ (Matrix) │   │
│  │ /rooms   │  │ /agent   │  │ opt-in   │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       └──────┬──────┴──────────────┘         │
│         ┌────▼─────┐                         │
│         │  SQLite  │                         │
│         └──────────┘                         │
└──────────────────────────────────────────────┘
```

### BYOK — Bring Your Own Keys

| Provider | Env Var | Models | Speed |
|----------|---------|--------|-------|
| OpenAI | `PLATO_KEY_OPENAI` | gpt-4o, gpt-4o-mini, o1, o3 | Fast |
| Anthropic | `PLATO_KEY_ANTHROPIC` | claude-sonnet, haiku, opus | Medium |
| Groq | `PLATO_KEY_GROQ` | llama-3.3-70b, llama-4-scout | ⚡ 24ms |
| DeepSeek | `PLATO_KEY_DEEPSEEK` | deepseek-chat, deepseek-reasoner | Medium |
| OpenRouter | `PLATO_KEY_OPENROUTER` | auto-routed to best model | Varies |
| Ollama (local) | `PLATO_OLLAMA_URL` | llama3, mistral, qwen2 | 🆓 Free |

### Armor Types (Agent Spawner)

| Type | Emoji | Best For |
|------|-------|----------|
| Scholar | 📚 | Deep research, synthesis, pattern-finding |
| Builder | ⚒️ | Code, architecture, implementation |
| Scout | 🔭 | Exploration, discovery, edge-finding |
| Critic | 🔍 | Review, quality audit, improvement |
| Bard | 🎭 | Storytelling, explanation, documentation |
| Commander | ⚓ | Coordination, orchestration, fleet management |
| Alchemist | ⚗️ | Optimization, efficiency, performance |
| Custom | ✨ | Whatever you describe |

---

## API / Usage

### Knowledge Endpoints

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

### Agent Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/armor` | Armor catalog (agent types) |
| `GET` | `/keys` | Configured providers |
| `POST` | `/spawn` | Spawn agent with description |
| `GET` | `/agents` | Active sessions |
| `GET` | `/agent/{id}` | Session details |
| `POST` | `/agent/{id}/chat` | Chat with agent |
| `POST` | `/agent/{id}/submit` | Agent submits tile |

### Submit a Tile

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

Tiles are validated: answer must be ≥20 characters; blocked words include `always`, `never`, `impossible`, `guaranteed`, `nobody` — encouraging specificity over absolutes.

### Docker with Agent Support

```bash
docker run -d \
  --name plato -p 8847:8847 -v plato-data:/data \
  -e PLATO_KEY_GROQ=gsk_... \
  -e PLATO_KEY_DEEPSEEK=sk_... \
  ghcr.io/superinstance/plato-server
```

---

## Testing

```bash
git clone https://github.com/SuperInstance/plato-server.git
cd plato-server
pip install -e ".[dev]"
pytest tests/ -v
```

---

## Contributing

Contributions are welcome! See the [SuperInstance Contributing Guide](https://github.com/SuperInstance/SuperInstance/blob/main/CONTRIBUTING.md).

---

## PLATO Engine Block Family

| Component | Language | Repo | Focus |
|---|---|---|---|
| **Server** ← you are here | Python | [plato-server](https://github.com/SuperInstance/plato-server) | Knowledge tiles, fleet sync via Matrix, HTTP API |
| **C Reference** | C99 | [plato-engine-block-c](https://github.com/SuperInstance/plato-engine-block-c) | Embedded, bare-metal, zero heap alloc |
| **Rust (Original)** | Rust | [plato-engine-block](https://github.com/SuperInstance/plato-engine-block) | `no_std` + alloc, builder pattern, tokio server |
| **Elixir/OTP** | Elixir | [plato-engine-block-elixir](https://github.com/SuperInstance/plato-engine-block-elixir) | BEAM supervision trees, fault tolerance, hot reload |
| **Runtime Kernel** | Rust | [plato-runtime-kernel](https://github.com/SuperInstance/plato-runtime-kernel) | Spatial model: tensor grid, batons, assertion traps |

---

## Ecosystem

This repo is part of the **SuperInstance** flagship ecosystem — agent-first computation, constraint theory, and self-improving runtimes.

### FLUX Runtime Family

| Repo | Language | Description |
|------|----------|-------------|
| [flux-runtime](https://github.com/SuperInstance/flux-runtime) | Python | Full FLUX runtime: markdown→bytecode, 2037 tests, zero deps |
| [flux-core](https://github.com/SuperInstance/flux-core) | Rust | Register-based bytecode VM, deterministic agent computation |
| [flux-js](https://github.com/SuperInstance/flux-js) | JavaScript | FLUX VM for Node.js and browsers, ~400ns/iter |
| [flux-compiler](https://github.com/SuperInstance/flux-compiler) | Rust/Python | Formal-methods compiler for safety-critical codegen |
| [flux-vm](https://github.com/SuperInstance/flux-vm) | Rust | Stack-based constraint-checking VM, 50 opcodes, Turing-incomplete |

### PLATO Engine Family

| Repo | Language | Description |
|------|----------|-------------|
| [plato-server](https://github.com/SuperInstance/plato-server) | Python | Knowledge tiles, fleet sync via Matrix, HTTP API |
| [plato-engine-block](https://github.com/SuperInstance/plato-engine-block) | Rust | Original room runtime: no_std + alloc, builder pattern |
| [plato-engine-block-c](https://github.com/SuperInstance/plato-engine-block-c) | C99 | Embedded reference: zero heap alloc, bare-metal portable |
| [plato-engine-block-elixir](https://github.com/SuperInstance/plato-engine-block-elixir) | Elixir | BEAM supervision trees, fault tolerance, hot reload |
| [plato-runtime-kernel](https://github.com/SuperInstance/plato-runtime-kernel) | Rust | Spatial model: tensor grid, batons, assertion traps |

### Constraint / Theory Family

| Repo | Language | Description |
|------|----------|-------------|
| [categorical-agents](https://github.com/SuperInstance/categorical-agents) | Rust | Category theory for agent composition (functors, naturality) |
| [cuda-constraint-engine](https://github.com/SuperInstance/cuda-constraint-engine) | CUDA/C | GPU constraint checking at 1B+ constraints/sec |
| [grand-pattern-rs](https://github.com/SuperInstance/grand-pattern-rs) | Rust | Fibonacci dual-direction cellular graph architecture |
| [lau-hodge-theory](https://github.com/SuperInstance/lau-hodge-theory) | Rust | Hodge decomposition, Betti numbers, spectral sequences |
| [ternary-science](https://github.com/SuperInstance/ternary-science) | Rust | Experimental evidence for ternary intelligence, 5 conservation laws |

### Agent / Infrastructure Family

| Repo | Language | Description |
|------|----------|-------------|
| [construct-core](https://github.com/SuperInstance/construct-core) | Rust | Layered trait system: bare-metal → alloc → async agent runtime |
| [crab](https://github.com/SuperInstance/crab) | Bash | Agent shell for repo entry/leave (MUD-room metaphor) |
| [exocortex](https://github.com/SuperInstance/exocortex) | Rust | Persistent cognitive substrate, S3-compatible memory |
| [git-agent](https://github.com/SuperInstance/git-agent) | Python | The repo IS the agent — autonomous lifecycle via Git |
| [capitaine-1](https://github.com/SuperInstance/capitaine-1) | TypeScript | Git-native repo-agent, Cloudflare Workers heartbeat |
| [codespace-edge-rd](https://github.com/SuperInstance/codespace-edge-rd) | Research | Codespace→Edge agent lifecycle and yoke transfer protocols |
| [git-agent-codespace](https://github.com/SuperInstance/git-agent-codespace) | DevContainer | One-click Codespace template for Git-Agent runtimes |

### Registries

| Registry | Package | Install |
|----------|---------|---------|
| **PyPI** | `flux-vm` | `pip install flux-vm` |
| **crates.io** | `fluxvm` | `cargo add fluxvm` |
| **npm** | `flux-js` | `npm install flux-js` |

### Philosophy & Architecture

- 📖 [AI-Writings](https://github.com/SuperInstance/AI-Writings) — Philosophy, essays, and design rationale
- 📦 [PACKAGES.md](https://github.com/SuperInstance/SuperInstance/blob/main/PACKAGES.md) — Full package index

---

## License

MIT — fork it, modify it, run it your way.

**Your PLATO. Your rules. Connected, we're all smarter.**
