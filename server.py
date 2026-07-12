#!/usr/bin/env python3
"""
PLATO Server — Standalone Knowledge System
The agentic IDE that learns from everyone, improves for everyone.

Each PLATO instance:
  - Runs locally with its own SQLite database
  - Manages rooms of knowledge tiles (Q&A pairs)
  - Optionally syncs with the Cocapn fleet via Matrix
  - Supports local agents (any chatbot) via HTTP API

API:
  GET  /                — System status
  GET  /rooms           — All rooms with tile counts
  GET  /room/{name}     — Room details + recent tiles
  GET  /tiles/recent    — Last 50 tiles across all rooms
  GET  /search?q=X      — Keyword search
  POST /submit          — Submit a tile {domain, question, answer, agent}
  GET  /sync/status     — Matrix federation status
  POST /sync/toggle     — Enable/disable fleet sync
  GET  /stats           — Usage statistics
"""

import json
import os
import sqlite3
import time
import hashlib
import uuid
import threading
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import socket
import re

def socket_hostname():
    return socket.gethostname()

# ── Config ──────────────────────────────────────────────────
PORT = int(os.environ.get("PLATO_PORT", 8847))
DATA_DIR = Path(os.environ.get("PLATO_DATA", "/data"))
DB_PATH = DATA_DIR / "plato.db"
INSTANCE_ID = os.environ.get("PLATO_INSTANCE", socket_hostname())

# Auth
PLATO_API_KEY = os.environ.get("PLATO_API_KEY", "")
AUTH_PREFIX = "Bearer "  # Authorization: Bearer <key>
AUTH_EXEMPT_PATHS = {"/health"}

if not PLATO_API_KEY:
    import logging
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger(__name__).warning(
        "PLATO_API_KEY is not set — server will REQUIRE it but all requests "
        "without it will be rejected. Set PLATO_API_KEY to allow access."
    )

# Fleet Matrix config (opt-in)
FLEET_MATRIX_HOMESERVER = os.environ.get("FLEET_MATRIX_SERVER", "http://localhost:6167")
FLEET_MATRIX_ROOM = os.environ.get("FLEET_MATRIX_ROOM", "#fleet-ops:localhost")
FLEET_MATRIX_USER = os.environ.get("PLATO_MATRIX_USER", "")
FLEET_MATRIX_TOKEN = os.environ.get("PLATO_MATRIX_TOKEN", "")
SYNC_ENABLED = os.environ.get("PLATO_FLEET_SYNC", "false").lower() == "true"

# Gate rules
BLOCKED_WORDS = {"always", "never", "impossible", "guaranteed", "nobody"}
MIN_ANSWER_LEN = 20

# ── Database ────────────────────────────────────────────────
class PlatoDB:
    def __init__(self, db_path=DB_PATH):
        if isinstance(db_path, str):
            db_path = Path(db_path)
        if db_path != Path(":memory:"):
            db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        self._migrate()

    def _migrate(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS tiles (
                id TEXT PRIMARY KEY,
                room TEXT NOT NULL,
                domain TEXT DEFAULT '',
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                agent TEXT DEFAULT 'anonymous',
                confidence REAL DEFAULT 0.5,
                created_at REAL,
                tile_hash TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_room ON tiles(room);
            CREATE INDEX IF NOT EXISTS idx_agent ON tiles(agent);
            CREATE INDEX IF NOT EXISTS idx_created ON tiles(created_at);

            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                direction TEXT,  -- 'send' or 'receive'
                tiles_count INTEGER,
                event_id TEXT,
                created_at REAL
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            );
        """)
        self.conn.commit()

    def submit_tile(self, room, domain, question, answer, agent="anonymous", confidence=0.5):
        # Gate validation
        answer_lower = answer.lower()
        for word in BLOCKED_WORDS:
            if word in answer_lower.split():
                return {"error": f"Gate blocked: '{word}' detected. Use specific language.", "status": "rejected"}

        if len(answer.strip()) < MIN_ANSWER_LEN:
            return {"error": f"Answer too short (min {MIN_ANSWER_LEN} chars)", "status": "rejected"}

        tile_id = uuid.uuid4().hex[:16]
        tile_hash = hashlib.sha256(f"{room}:{question}:{answer}".encode()).hexdigest()[:16]
        created = time.time()

        with self.lock:
            self.conn.execute(
                "INSERT INTO tiles (id, room, domain, question, answer, agent, confidence, created_at, tile_hash) VALUES (?,?,?,?,?,?,?,?,?)",
                (tile_id, room, domain, question, answer, agent, confidence, created, tile_hash)
            )
            self.conn.commit()

        return {
            "status": "accepted",
            "tile_id": tile_id,
            "tile_hash": tile_hash,
            "room": room,
        }

    def get_rooms(self):
        with self.lock:
            rows = self.conn.execute(
                "SELECT room, COUNT(*) as tile_count, MAX(created_at) as latest FROM tiles GROUP BY room ORDER BY tile_count DESC"
            ).fetchall()
        return {r["room"]: {"tile_count": r["tile_count"], "latest": r["latest"]} for r in rows}

    def get_room(self, name, limit=50):
        with self.lock:
            tiles = self.conn.execute(
                "SELECT * FROM tiles WHERE room=? ORDER BY created_at DESC LIMIT ?",
                (name, limit)
            ).fetchall()
        return [dict(t) for t in tiles]

    def get_recent(self, limit=50):
        with self.lock:
            tiles = self.conn.execute(
                "SELECT * FROM tiles ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(t) for t in tiles]

    def search(self, query, limit=20):
        with self.lock:
            tiles = self.conn.execute(
                "SELECT * FROM tiles WHERE question LIKE ? OR answer LIKE ? OR domain LIKE ? ORDER BY created_at DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", f"%{query}%", limit)
            ).fetchall()
        return [dict(t) for t in tiles]

    def get_stats(self):
        with self.lock:
            total = self.conn.execute("SELECT COUNT(*) FROM tiles").fetchone()[0]
            rooms = self.conn.execute("SELECT COUNT(DISTINCT room) FROM tiles").fetchone()[0]
            agents = self.conn.execute("SELECT COUNT(DISTINCT agent) FROM tiles").fetchone()[0]
            recent_24h = self.conn.execute(
                "SELECT COUNT(*) FROM tiles WHERE created_at > ?", (time.time() - 86400,)
            ).fetchone()[0]
        return {
            "instance": INSTANCE_ID,
            "total_tiles": total,
            "total_rooms": rooms,
            "total_agents": agents,
            "tiles_24h": recent_24h,
            "sync_enabled": SYNC_ENABLED,
            "fleet_connected": SYNC_ENABLED and bool(FLEET_MATRIX_TOKEN),
        }

    def tile_count(self):
        with self.lock:
            return self.conn.execute("SELECT COUNT(*) FROM tiles").fetchone()[0]


# ── Matrix Sync (optional) ─────────────────────────────────
class MatrixSync:
    """Sync tiles with the Cocapn fleet via Matrix."""
    def __init__(self, db: PlatoDB):
        self.db = db
        self.running = False
        self.thread = None
        self.last_sync = 0
        self.events_sent = 0
        self.events_received = 0

    def start(self):
        if not SYNC_ENABLED or not FLEET_MATRIX_TOKEN:
            return
        self.running = True
        self.thread = threading.Thread(target=self._sync_loop, daemon=True)
        self.thread.start()

    def stop(self):
        self.running = False

    def _sync_loop(self):
        """Every 5 minutes, send new tiles and receive fleet tiles."""
        import urllib.request
        while self.running:
            try:
                # Send new tiles
                since = self.db.conn.execute(
                    "SELECT COALESCE(MAX(created_at), 0) FROM sync_log WHERE direction='send'"
                ).fetchone()[0]
                with self.db.lock:
                    new_tiles = self.db.conn.execute(
                        "SELECT * FROM tiles WHERE created_at > ? ORDER BY created_at ASC LIMIT 50",
                        (since,)
                    ).fetchall()

                if new_tiles:
                    payload = {
                        "type": "m.custom.plato.tiles",
                        "content": {
                            "instance": INSTANCE_ID,
                            "tiles": [dict(t) for t in new_tiles],
                            "count": len(new_tiles),
                        }
                    }
                    self._send_matrix_event(payload)
                    with self.db.lock:
                        self.db.conn.execute(
                            "INSERT INTO sync_log (direction, tiles_count, created_at) VALUES ('send', ?, ?)",
                            (len(new_tiles), time.time())
                        )
                        self.db.conn.commit()
                    self.events_sent += len(new_tiles)

                # Receive fleet tiles (poll room messages since last sync)
                self._receive_fleet_tiles()

            except Exception as e:
                print(f"[sync] Error: {e}")

            time.sleep(300)  # 5 minutes

    def _send_matrix_event(self, payload):
        """Send a Matrix event to the fleet room."""
        import urllib.request
        txn_id = uuid.uuid4().hex[:8]
        url = f"{FLEET_MATRIX_HOMESERVER}/_matrix/client/v3/rooms/{FLEET_MATRIX_ROOM}/send/m.custom.plato.tiles/{txn_id}"
        req = urllib.request.Request(url, method="PUT")
        req.add_header("Authorization", f"Bearer {FLEET_MATRIX_TOKEN}")
        req.add_header("Content-Type", "application/json")
        urllib.request.urlopen(req, json.dumps(payload).encode(), timeout=10)

    def _receive_fleet_tiles(self):
        """Poll for new fleet tiles from Matrix room."""
        import urllib.request
        url = f"{FLEET_MATRIX_HOMESERVER}/_matrix/client/v3/rooms/{FLEET_MATRIX_ROOM}/messages?dir=b&limit=20"
        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {FLEET_MATRIX_TOKEN}")
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())

        for event in data.get("chunk", []):
            if event.get("type") == "m.custom.plato.tiles":
                content = event.get("content", {})
                source_instance = content.get("instance", "unknown")
                if source_instance == INSTANCE_ID:
                    continue  # Skip our own tiles
                for tile in content.get("tiles", []):
                    try:
                        self.db.submit_tile(
                            room=f"fleet-{tile.get('room', 'shared')}",
                            domain=tile.get("domain", ""),
                            question=tile.get("question", ""),
                            answer=tile.get("answer", ""),
                            agent=f"fleet:{source_instance}:{tile.get('agent', 'unknown')}",
                        )
                        self.events_received += 1
                    except Exception:
                        pass

    def status(self):
        return {
            "enabled": SYNC_ENABLED,
            "connected": SYNC_ENABLED and bool(FLEET_MATRIX_TOKEN),
            "events_sent": self.events_sent,
            "events_received": self.events_received,
            "fleet_homeserver": FLEET_MATRIX_HOMESERVER if SYNC_ENABLED else "not configured",
        }


# ── HTTP Server ─────────────────────────────────────────────
db = None
sync = None


from agent import (PROVIDERS, ARMOR_CATALOG, detect_armor, build_custom_prompt,
                    get_available_providers, pick_model, make_agent_call,
                    SessionManager)

sessions = SessionManager()


class PlatoHandler(BaseHTTPRequestHandler):
    # db and sync are module globals, set in __main__

    def _check_auth(self):
        """Return True if request is authorized, False otherwise."""
        path = self._path()
        # Health endpoint is always public
        if path in AUTH_EXEMPT_PATHS:
            return True
        # Require Bearer token
        auth_header = self.headers.get("Authorization", "")
        if auth_header.startswith(AUTH_PREFIX):
            token = auth_header[len(AUTH_PREFIX):]
            if token and token == PLATO_API_KEY:
                return True
        return False

    def _unauthorized(self):
        self.send_response(401)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps({"error": "Unauthorized — provide Authorization: Bearer <PLATO_API_KEY>"}).encode())

    def _path(self):
        return urlparse(self.path).path.rstrip("/")

    def _params(self):
        return {k: v[0] for k, v in parse_qs(urlparse(self.path).query).items()}

    def _cors_origin(self):
        """Return configured CORS origin (empty = no CORS header sent)."""
        return os.environ.get("PLATO_CORS_ORIGIN", "")

    def _json(self, data, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        origin = self._cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2, default=str).encode())

    def _body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 1_048_576:  # 1 MB max
            raise ValueError("Request body too large (max 1MB)")
        return json.loads(self.rfile.read(length)) if length else {}

    def do_GET(self):
        path = self._path()
        params = self._params()

        if not self._check_auth():
            self._unauthorized()
            return

        if path == "/health":
            self._json({"status": "ok", "instance": INSTANCE_ID, "tiles": db.tile_count()})
            return

        if path == "" or path == "/":
            self._json({
                "service": "PLATO — Knowledge System",
                "version": "1.0.0",
                "instance": INSTANCE_ID,
                "tiles": db.tile_count(),
                "rooms": len(db.get_rooms()),
                "fleet_sync": sync.status(),
                "api": [
                    "GET  /              — This page",
                    "GET  /rooms         — All rooms",
                    "GET  /room/{name}   — Room tiles",
                    "GET  /tiles/recent  — Recent tiles",
                    "GET  /search?q=X    — Search tiles",
                    "POST /submit        — Submit tile",
                    "GET  /stats         — Usage stats",
                    "GET  /sync/status   — Fleet sync",
                    "GET  /armor          — Armor catalog (agent types)",
                    "GET  /keys           — Configured providers",
                    "GET  /agent/{id}     — Agent session",
                    "GET  /agents         — Active sessions",
                    "POST /spawn          — Spawn agent {description, provider?}",
                    "POST /agent/{id}/chat — Send message to agent",
                    "POST /agent/{id}/submit — Agent submits tile",
                ],
                "about": "PLATO learns from everyone, improves for everyone. Run your own — connect to the fleet — make all of us smarter.",
            })

        elif path == "/rooms":
            self._json(db.get_rooms())

        elif path.startswith("/room/"):
            room = path.split("/room/", 1)[1]
            # Sanitize room name: alphanumeric, dash, underscore, dot only
            if not room or not re.match(r'^[A-Za-z0-9._-]+$', room):
                self._json({"error": "Invalid room name"}, 400)
                return
            tiles = db.get_room(room)
            if not tiles:
                self._json({"room": room, "tiles": [], "message": "Empty room — submit the first tile!"})
            else:
                self._json({"room": room, "tile_count": len(tiles), "tiles": tiles})

        elif path == "/tiles/recent":
            limit = int(params.get("limit", 50))
            self._json({"tiles": db.get_recent(limit)})

        elif path == "/search":
            q = params.get("q", "")
            if not q:
                self._json({"error": "Query required: /search?q=your+search"}, 400)
                return
            self._json({"query": q, "results": db.search(q)})

        elif path == "/stats":
            self._json(db.get_stats())

        elif path == "/sync/status":
            self._json(sync.status())

        # ── Agent endpoints ──
        elif path == "/armor":
            self._json({k: {"name": v["name"], "emoji": v["emoji"], "description": v["description"]}
                       for k, v in ARMOR_CATALOG.items()})

        elif path == "/keys":
            self._json(get_available_providers())

        elif path == "/agents":
            sessions.cleanup()
            self._json(sessions.list_sessions())

        elif path.startswith("/agent/") and "/chat" not in path and "/submit" not in path:
            sid = path.split("/agent/")[1]
            session = sessions.get(sid)
            if not session:
                self._json({"error": f"Session {sid} not found"}, 404)
                return
            self._json(session.to_dict())

        else:
            self._json({"error": f"Not found: {path}"}, 404)

    def do_POST(self):
        path = self._path()
        body = self._body()

        if not self._check_auth():
            self._unauthorized()
            return

        if path == "/submit":
            domain = body.get("domain", "general")
            question = body.get("question", "")
            answer = body.get("answer", "")
            agent = body.get("agent", "anonymous")
            room = body.get("room", domain)

            if not question or not answer:
                self._json({"error": "Fields required: question, answer"}, 400)
                return

            result = db.submit_tile(room, domain, question, answer, agent)
            if "error" in result:
                self._json(result, 400)
            else:
                self._json(result)

        elif path == "/sync/toggle":
            global SYNC_ENABLED
            enable = body.get("enabled", not SYNC_ENABLED)
            SYNC_ENABLED = enable
            if enable and not sync.running:
                sync.start()
            elif not enable and sync.running:
                sync.stop()
            self._json({"sync_enabled": SYNC_ENABLED})

        # ── Agent spawn & chat ──
        elif path == "/spawn":
            description = body.get("description", "")
            preferred = body.get("provider", None)
            room = body.get("room", "general")
            model_override = body.get("model", None)
            temperature = body.get("temperature", 0.7)

            if not description:
                self._json({"error": "Describe what you want your agent to do. Example: {\"description\": \"research agent for fishing patterns\"}"}, 400)
                return

            # Detect armor type from description
            armor_type = detect_armor(description)
            armor = ARMOR_CATALOG[armor_type]

            # Build system prompt
            if armor_type == "custom" or armor.get("system_prompt") is None:
                system_prompt = build_custom_prompt(description)
            else:
                system_prompt = armor["system_prompt"]

            # Add PLATO awareness to prompt
            plato_context = f"""\n\nPLATO Instance: {INSTANCE_ID}\nRoom: {room}\nSubmit tiles: POST /submit {{\"room\": \"{room}\", \"domain\": \"...\", \"question\": \"...\", \"answer\": \"...(20+ chars)\", \"agent\": \"your-name\"}}\nSearch: GET /search?q=...\nRecent tiles: GET /tiles/recent"""
            system_prompt += plato_context

            # Pick model
            if model_override:
                provider_name = preferred or "openrouter"
                provider_config = PROVIDERS.get(provider_name, {})
                api_key = os.environ.get(provider_config.get("env", ""), "")
                provider, model, base_url, key = provider_name, model_override, provider_config.get("base_url", ""), api_key
            else:
                provider, model, base_url, key = pick_model(armor_type, preferred)

            if not provider:
                self._json({"error": "No API keys configured. Set at least one: " + ", ".join(f'{c["env"]} ({name})' for name, c in PROVIDERS.items()),
                           "hint": "Add keys to your docker run: -e PLATO_KEY_OPENAI=sk-..."}, 400)
                return

            session = sessions.create(armor_type, provider, model, system_prompt)
            session.add_message("system", system_prompt)

            # Send initial message
            first_msg = f"You are in room '{room}'. Description of your mission: {description}. Start by reading recent tiles, then begin your work."
            result = make_agent_call(provider, base_url, key, model, system_prompt, first_msg, temperature)

            if "error" in result:
                self._json({"error": result["error"], "session_id": session.id,
                           "hint": "Check your API key and model name"}, 500)
                return

            session.add_message("user", first_msg)
            session.add_message("assistant", result["content"])

            self._json({
                "session_id": session.id,
                "armor": armor_type,
                "armor_name": armor["name"],
                "armor_emoji": armor["emoji"],
                "provider": provider,
                "model": model,
                "response": result["content"],
                "usage": result.get("usage", {}),
                "room": room,
                "chat": f"POST /agent/{session.id}/chat {{\"message\": \"continue\"}}",
            })

        elif path.startswith("/agent/") and path.endswith("/chat"):
            sid = path.split("/agent/")[1].replace("/chat", "")
            session = sessions.get(sid)
            if not session:
                self._json({"error": f"Session {sid} not found"}, 404)
                return
            message = body.get("message", "continue")
            temperature = body.get("temperature", 0.7)

            # Build conversation
            provider_config = PROVIDERS.get(session.provider, {})
            api_key = os.environ.get(provider_config.get("env", ""), "")
            result = make_agent_call(
                session.provider, provider_config.get("base_url", ""),
                api_key, session.model, session.system_prompt,
                message, temperature
            )

            if "error" in result:
                self._json({"error": result["error"]}, 500)
                return

            session.add_message("user", message)
            session.add_message("assistant", result["content"])

            self._json({
                "session_id": sid,
                "response": result["content"],
                "messages": len(session.history),
                "usage": result.get("usage", {}),
            })

        elif path.startswith("/agent/") and path.endswith("/submit"):
            sid = path.split("/agent/")[1].replace("/submit", "")
            session = sessions.get(sid)
            if not session:
                self._json({"error": f"Session {sid} not found"}, 404)
                return
            # Agent submits a tile
            domain = body.get("domain", "agent-generated")
            question = body.get("question", "")
            answer = body.get("answer", "")
            room = body.get("room", "general")
            if not question or not answer:
                self._json({"error": "Fields required: question, answer"}, 400)
                return
            result = db.submit_tile(room, domain, question, answer, agent=f"agent:{session.id}")
            if "error" not in result:
                session.tiles_submitted += 1
            self._json(result)

        else:
            self._json({"error": f"Not found: {path}"}, 404)

    def do_OPTIONS(self):
        self.send_response(204)
        origin = self._cors_origin()
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def log_message(self, format, *args):
        pass


# ── Main ────────────────────────────────────────────────────
def main():
    """Entry point for plato-server."""
    global db, sync
    db = PlatoDB()
    sync = MatrixSync(db)
    print(f"╔══════════════════════════════════════════╗")
    print(f"║  PLATO Knowledge System v1.0.0           ║")
    print(f"║  Instance: {INSTANCE_ID:<30s}║")
    print(f"║  Database: {str(DB_PATH):<30s}║")
    print(f"║  Fleet sync: {'ON' if SYNC_ENABLED else 'OFF':<29s}║")
    print(f"║  Auth: {'ON' if PLATO_API_KEY else 'REQUIRED (no key set!)':<30s}║")
    print(f"╚══════════════════════════════════════════╝")

    if SYNC_ENABLED:
        print(f"  Fleet: {FLEET_MATRIX_HOMESERVER}")
        print(f"  Room: {FLEET_MATRIX_ROOM}")
        sync.start()

    server = HTTPServer(("0.0.0.0", PORT), PlatoHandler)
    print(f"  Listening on :{PORT}")
    print(f"  Tiles: {db.tile_count()}")
    print()
    print(f"  Ready. Submit knowledge: POST /submit")
    print(f"  Connect to fleet: set PLATO_FLEET_SYNC=true")
    server.serve_forever()


if __name__ == "__main__":
    main()
