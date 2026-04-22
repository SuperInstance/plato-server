#!/usr/bin/env python3
"""
PLATO Agent Spawner — Your Model, Your Armor, Your Agent.

When a human describes what they want, PLATO builds the agent:
  - Picks the right model from their BYOK config
  - Generates a system prompt (the "power armor")
  - Equips fleet protocols (tile submission, room navigation)
  - Runs the agent with PLATO awareness built in

The human vibes the armor. PLATO builds and runs it.
"""
import json
import os
import time
import uuid
import hashlib
from pathlib import Path
from typing import Optional


# ── BYOK (Bring Your Own Keys) ──────────────────────────────
PROVIDERS = {
    "openai": {
        "env": "PLATO_KEY_OPENAI",
        "base_url": "https://api.openai.com/v1",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "o1", "o1-mini", "o3"],
        "default": "gpt-4o-mini",
    },
    "anthropic": {
        "env": "PLATO_KEY_ANTHROPIC",
        "base_url": "https://api.anthropic.com/v1",
        "models": ["claude-sonnet-4-20250514", "claude-3.5-haiku-20241022", "claude-opus-4-20250514"],
        "default": "claude-sonnet-4-20250514",
    },
    "groq": {
        "env": "PLATO_KEY_GROQ",
        "base_url": "https://api.groq.com/openai/v1",
        "models": ["llama-3.3-70b-versatile", "llama-3.1-8b-instant",
                    "meta-llama/llama-4-scout-17b-16e-instruct", "qwen/qwen3-32b"],
        "default": "llama-3.3-70b-versatile",
    },
    "deepseek": {
        "env": "PLATO_KEY_DEEPSEEK",
        "base_url": "https://api.deepseek.com",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "default": "deepseek-chat",
    },
    "moonshot": {
        "env": "PLATO_KEY_MOONSHOT",
        "base_url": "https://api.moonshot.ai/v1",
        "models": ["kimi-k2.5", "moonshot-v1-auto"],
        "default": "kimi-k2.5",
    },
    "openrouter": {
        "env": "PLATO_KEY_OPENROUTER",
        "base_url": "https://openrouter.ai/api/v1",
        "models": ["openrouter/auto", "anthropic/claude-sonnet-4-20250514",
                    "google/gemini-2.5-pro", "meta-llama/llama-3.3-70b-instruct"],
        "default": "openrouter/auto",
    },
    "ollama": {
        "env": "PLATO_OLLAMA_URL",
        "base_url": "http://localhost:11434/v1",
        "models": ["llama3", "mistral", "codellama", "qwen2", "gemma2"],
        "default": "llama3",
        "local": True,
    },
    "siliconflow": {
        "env": "PLATO_KEY_SILICONFLOW",
        "base_url": "https://api.siliconflow.com/v1",
        "models": ["deepseek-ai/DeepSeek-V3", "Pro/Qwen/Qwen2.5-VL-7B-Instruct"],
        "default": "deepseek-ai/DeepSeek-V3",
    },
}

# ── Power Armor Templates ───────────────────────────────────
# When a human describes their intent, we match it to armor.
ARMOR_CATALOG = {
    "scholar": {
        "name": "Scholar",
        "emoji": "📚",
        "description": "Deep researcher. Reads everything, synthesizes, finds patterns.",
        "system_prompt": """You are a Scholar agent in a PLATO knowledge system.

Your purpose: research deeply, synthesize clearly, submit what you learn as knowledge tiles.

Protocol:
1. Read the room tiles to understand existing knowledge
2. Identify gaps, contradictions, or unexplored angles
3. Research your topic thoroughly
4. Submit your findings as tiles via POST /submit
5. Each tile: specific question, detailed answer (50+ words), no absolutes

Rules:
- Never use: always, never, impossible, guaranteed, nobody
- Cite specifics: numbers, systems, constraints
- When uncertain, say so and explain why
- Your output becomes fleet knowledge — make it worth remembering""",
        "best_models": ["deepseek-chat", "gpt-4o", "claude-sonnet-4-20250514", "kimi-k2.5"],
    },
    "builder": {
        "name": "Builder",
        "emoji": "⚒️",
        "description": "Code architect. Designs systems, writes implementations, tests.",
        "system_prompt": """You are a Builder agent in a PLATO knowledge system.

Your purpose: design and implement working systems, submit architectural knowledge.

Protocol:
1. Understand the problem domain from room tiles
2. Design the solution architecture
3. Write clean, working code
4. Test your implementation
5. Submit design decisions and tradeoffs as tiles

Rules:
- Ship working code, not plans
- Document every design decision
- Include error handling and edge cases
- If you can't implement something, explain exactly why""",
        "best_models": ["deepseek-chat", "gpt-4o", "claude-sonnet-4-20250514", "o1"],
    },
    "scout": {
        "name": "Scout",
        "emoji": "🔭",
        "description": "Explorer. Finds edges, maps unknowns, reports discoveries.",
        "system_prompt": """You are a Scout agent in a PLATO knowledge system.

Your purpose: explore the unknown, find what others miss, report discoveries.

Protocol:
1. Look for gaps in the room's knowledge
2. Ask questions nobody has asked
3. Test boundaries and edge cases
4. Report discoveries as tiles
5. Flag anything unexpected or contradictory

Rules:
- Bold exploration, careful reporting
- If something seems wrong, investigate before reporting
- Your value is finding what others don't see
- Always submit what you find — even negative results""",
        "best_models": ["deepseek-reasoner", "o1", "kimi-k2.5", "gpt-4o"],
    },
    "critic": {
        "name": "Critic",
        "emoji": "🔍",
        "description": "Reviewer. Finds flaws, proposes improvements, strengthens arguments.",
        "system_prompt": """You are a Critic agent in a PLATO knowledge system.

Your purpose: review existing knowledge, find weaknesses, propose improvements.

Protocol:
1. Read all tiles in the room
2. Evaluate each for: accuracy, specificity, completeness, novelty
3. Find contradictions between tiles
4. Propose corrections or improvements
5. Submit your critiques and fixes as tiles

Rules:
- Steel-man before you criticize
- Propose fixes, don't just find problems
- Rate each tile (1-10) on each dimension
- Your critiques make the fleet's knowledge stronger""",
        "best_models": ["claude-sonnet-4-20250514", "gpt-4o", "deepseek-chat"],
    },
    "bard": {
        "name": "Bard",
        "emoji": "🎭",
        "description": "Storyteller. Explains complex ideas clearly, creates narratives.",
        "system_prompt": """You are a Bard agent in a PLATO knowledge system.

Your purpose: make knowledge accessible, create narratives, document stories.

Protocol:
1. Read room tiles and understand the domain
2. Transform technical knowledge into accessible explanations
3. Create narratives that make complex ideas stick
4. Document stories and use cases
5. Submit your explanations as tiles

Rules:
- Clarity over cleverness
- Use analogies and examples
- A good explanation is worth 10 raw facts
- Your output teaches humans AND agents""",
        "best_models": ["gpt-4o", "claude-sonnet-4-20250514", "deepseek-chat", "kimi-k2.5"],
    },
    "commander": {
        "name": "Commander",
        "emoji": "⚓",
        "description": "Coordinator. Orchestrates multiple agents, manages tasks, reports status.",
        "system_prompt": """You are a Commander agent in a PLATO knowledge system.

Your purpose: coordinate multiple agents, manage workflows, report fleet status.

Protocol:
1. Survey all rooms and their knowledge state
2. Identify priorities and task assignments
3. Coordinate between agent types
4. Monitor progress and adjust
5. Submit coordination decisions as tiles

Rules:
- Delegate, don't do
- Track what's in progress vs complete
- Report blockers immediately
- Your decisions guide the fleet""",
        "best_models": ["gpt-4o", "claude-sonnet-4-20250514", "deepseek-chat"],
    },
    "alchemist": {
        "name": "Alchemist",
        "emoji": "⚗️",
        "description": "Optimizer. Finds efficiencies, reduces waste, improves performance.",
        "system_prompt": """You are an Alchemist agent in a PLATO knowledge system.

Your purpose: optimize everything. Find waste, reduce it. Find bottlenecks, remove them.

Protocol:
1. Analyze room tiles for inefficiencies
2. Find redundant or low-quality tiles
3. Propose optimizations
4. Measure improvement
5. Submit optimization reports as tiles

Rules:
- Measure before and after
- A 1% improvement across 1000 operations is huge
- Question every assumption
- The best optimization is deleting something unnecessary""",
        "best_models": ["deepseek-reasoner", "o1", "gpt-4o"],
    },
    "custom": {
        "name": "Custom",
        "emoji": "✨",
        "description": "User-defined. The human vibes the armor, PLATO builds it.",
        "system_prompt": None,  # Generated dynamically from user description
        "best_models": ["deepseek-chat", "gpt-4o", "openrouter/auto"],
    },
}


def detect_armor(description: str) -> str:
    """Match a human's description to the right armor type."""
    desc = description.lower()
    scores = {}
    keywords = {
        "scholar": ["research", "study", "learn", "analyze", "paper", "academic", "deep", "synthesize", "review literature"],
        "builder": ["build", "code", "implement", "create", "develop", "ship", "architect", "design system", "write"],
        "scout": ["explore", "discover", "find", "map", "investigate", "unknown", "edge", "pioneer"],
        "critic": ["review", "critique", "improve", "audit", "find flaws", "quality", "verify", "check"],
        "bard": ["explain", "story", "narrative", "document", "communicate", "write up", "present", "teach"],
        "commander": ["coordinate", "manage", "orchestrate", "lead", "organize", "direct", "assign", "fleet"],
        "alchemist": ["optimize", "improve performance", "efficient", "reduce", "faster", "lean", "compress"],
    }
    for armor_type, words in keywords.items():
        scores[armor_type] = sum(1 for w in words if w in desc)
    best = max(scores, key=scores.get) if max(scores.values()) > 0 else "scholar"
    return best


def build_custom_prompt(description: str) -> str:
    """Generate a custom system prompt from a human's description."""
    return f"""You are a custom PLATO agent. The human described you as:

"{description}"

Your purpose: fulfill that role within the PLATO knowledge system.

Protocol:
1. Read room tiles to understand the domain
2. Apply your unique perspective to the knowledge
3. Submit your insights as tiles via POST /submit
4. Each tile: specific question, detailed answer (50+ words)

Rules:
- Never use: always, never, impossible, guaranteed, nobody
- Be specific, not vague
- Your unique perspective IS your value — don't be generic
- Submit what you learn — that's how the fleet gets smarter"""


def get_available_providers() -> dict:
    """Check which providers have keys configured."""
    available = {}
    for name, config in PROVIDERS.items():
        key = os.environ.get(config["env"], "")
        if config.get("local"):
            # Ollama: check if URL is reachable
            available[name] = {"available": bool(key), "models": config["models"]}
        elif key:
            available[name] = {"available": True, "models": config["models"]}
        else:
            available[name] = {"available": False, "models": config["models"]}
    return available


def pick_model(armor_type: str, preferred_provider: str = None) -> tuple:
    """Pick the best available model for the armor type.
    Returns (provider, model, base_url, api_key)."""
    armor = ARMOR_CATALOG.get(armor_type, ARMOR_CATALOG["scholar"])
    preferred_models = armor.get("best_models", [])

    # If user specified a provider, try it first
    if preferred_provider and preferred_provider in PROVIDERS:
        config = PROVIDERS[preferred_provider]
        key = os.environ.get(config["env"], "")
        if key:
            # Find best model from this provider
            for pm in preferred_models:
                if pm in config["models"]:
                    return preferred_provider, pm, config["base_url"], key
            # Use provider's default
            return preferred_provider, config["default"], config["base_url"], key

    # Try preferred models across all providers
    for pm in preferred_models:
        for name, config in PROVIDERS.items():
            if pm in config["models"]:
                key = os.environ.get(config["env"], "")
                if key or config.get("local"):
                    return name, pm, config["base_url"], key

    # Fallback: find any available provider
    for name, config in PROVIDERS.items():
        key = os.environ.get(config["env"], "")
        if key or config.get("local"):
            return name, config["default"], config["base_url"], key

    return None, None, None, None


def make_agent_call(provider: str, base_url: str, api_key: str,
                    model: str, system_prompt: str, user_message: str,
                    temperature: float = 0.7, max_tokens: int = 2000) -> dict:
    """Make an API call to the chosen provider. Returns {content, usage, model}."""
    import urllib.request

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    url = f"{base_url}/chat/completions"
    req = urllib.request.Request(url, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "plato-server/1.0")
    if api_key:
        if provider == "anthropic":
            req.add_header("x-api-key", api_key)
            req.add_header("anthropic-version", "2023-06-01")
        else:
            req.add_header("Authorization", f"Bearer {api_key}")

    try:
        resp = urllib.request.urlopen(req, json.dumps(payload).encode(), timeout=120)
        data = json.loads(resp.read())
        return {
            "content": data["choices"][0]["message"]["content"],
            "usage": data.get("usage", {}),
            "model": model,
            "provider": provider,
        }
    except Exception as e:
        return {"error": str(e), "provider": provider, "model": model}


# ── Session Manager ─────────────────────────────────────────
class AgentSession:
    """A running agent session with conversation history."""
    def __init__(self, session_id, armor_type, provider, model, system_prompt):
        self.id = session_id
        self.armor_type = armor_type
        self.provider = provider
        self.model = model
        self.system_prompt = system_prompt
        self.history = []
        self.tiles_submitted = 0
        self.created_at = time.time()

    def add_message(self, role, content):
        self.history.append({"role": role, "content": content})

    def to_dict(self):
        return {
            "id": self.id,
            "armor": self.armor_type,
            "armor_name": ARMOR_CATALOG.get(self.armor_type, {}).get("name", "Custom"),
            "armor_emoji": ARMOR_CATALOG.get(self.armor_type, {}).get("emoji", "✨"),
            "provider": self.provider,
            "model": self.model,
            "messages": len(self.history),
            "tiles_submitted": self.tiles_submitted,
            "created_at": self.created_at,
        }


class SessionManager:
    def __init__(self):
        self.sessions = {}

    def create(self, armor_type, provider, model, system_prompt):
        session_id = uuid.uuid4().hex[:12]
        session = AgentSession(session_id, armor_type, provider, model, system_prompt)
        self.sessions[session_id] = session
        return session

    def get(self, session_id):
        return self.sessions.get(session_id)

    def list_sessions(self):
        return {sid: s.to_dict() for sid, s in self.sessions.items()}

    def cleanup(self, max_age=86400):
        """Remove sessions older than 24h."""
        now = time.time()
        stale = [sid for sid, s in self.sessions.items() if now - s.created_at > max_age]
        for sid in stale:
            del self.sessions[sid]
        return len(stale)
