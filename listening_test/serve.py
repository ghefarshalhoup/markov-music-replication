"""The listening test's local server: serves the built app and stores every answer in SQLite.

    python listening_test/serve.py            then open http://127.0.0.1:8765

Only Python's standard library is used. Everything stays on this laptop.

Storage (results/listening/):
    listening.sqlite   research data: sessions and trials. No names.
    names.sqlite       optional participant names, linked only by participant id
    trials_log.jsonl   an append-only copy of every trial as it arrived (a second safety net)

Rules the server enforces:
    - The trial order is drawn here, once, when a session starts, and stored. A refresh can never change it.
    - A trial is keyed by (session id, trial index). Sending it again (a retry) is accepted but stored once.
    - A trial must be for the clip that the stored order puts at that index, and only after consent.
    - Conditions live in results/listening/clip_key.json and are joined in only for the CSV export;
      the browser never receives them.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import mimetypes
import secrets
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from random import Random
from urllib.parse import urlparse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
DIST = HERE / "dist"
CLIP_DIR = HERE / "public" / "clips"
MANIFEST = HERE / "clips.json"
KEY = ROOT / "results" / "listening" / "clip_key.json"
DATA = ROOT / "results" / "listening"
DB = DATA / "listening.sqlite"
NAMES_DB = DATA / "names.sqlite"
LOG = DATA / "trials_log.jsonl"

SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    session_id     TEXT PRIMARY KEY,
    participant_id TEXT NOT NULL UNIQUE,
    group_no       INTEGER NOT NULL CHECK (group_no IN (1, 2)),
    pilot          INTEGER NOT NULL CHECK (pilot IN (0, 1)),
    seed           INTEGER NOT NULL,
    trial_order    TEXT NOT NULL,             -- JSON list of clip ids, in presentation order
    created_at     TEXT NOT NULL,
    consent_at     TEXT,
    experience     TEXT CHECK (experience IN ('none', 'some', 'trained')),
    soundcheck_at  TEXT,
    completed_at   TEXT,
    status         TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'completed', 'abandoned')),
    user_agent     TEXT
);
CREATE TABLE IF NOT EXISTS trials (
    session_id   TEXT NOT NULL REFERENCES sessions(session_id),
    trial_index  INTEGER NOT NULL,            -- 0-based position in the session's order
    clip_id      TEXT NOT NULL,
    liking       INTEGER NOT NULL CHECK (liking BETWEEN 1 AND 5),
    ending       INTEGER NOT NULL CHECK (ending BETWEEN 1 AND 5),
    attribution  TEXT NOT NULL CHECK (attribution IN ('person', 'computer')),
    replays      INTEGER NOT NULL CHECK (replays >= 0),
    response_ms  INTEGER NOT NULL CHECK (response_ms >= 0),
    answered_at  TEXT NOT NULL,              -- the participant's clock
    received_at  TEXT NOT NULL,              -- the server's clock
    PRIMARY KEY (session_id, trial_index)
);
"""
NAMES_SCHEMA = """
CREATE TABLE IF NOT EXISTS names (
    participant_id TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    created_at     TEXT NOT NULL
);
"""
EXPERIENCE = ("none", "some", "trained")
LOCK = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class Store:
    """All reads and writes, one at a time, each committed before the answer goes back."""

    def __init__(self, db: Path, names_db: Path, log: Path):
        db.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(db, check_same_thread=False, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.execute("PRAGMA journal_mode = WAL")
        self.db.execute("PRAGMA synchronous = FULL")
        self.db.executescript(SCHEMA)
        self.names = sqlite3.connect(names_db, check_same_thread=False, isolation_level=None)
        self.names.execute("PRAGMA synchronous = FULL")
        self.names.executescript(NAMES_SCHEMA)
        self.log = log
        self.manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        self.key = json.loads(KEY.read_text(encoding="utf-8"))

    # --- the stimuli -----------------------------------------------------------------------------------
    def group_clips(self, group: int) -> list[str]:
        return list(self.manifest["groups"][str(group)]) + list(self.manifest["attention"])

    def missing_audio(self) -> list[str]:
        ids = self.group_clips(1) + self.group_clips(2) + [self.manifest["practice"]]
        return sorted({i for i in ids if not (CLIP_DIR / f"{i}.mp3").is_file()})

    # --- sessions ---------------------------------------------------------------------------------------
    def state(self) -> dict:
        with LOCK:
            rows = self.db.execute("SELECT pilot, status, group_no FROM sessions").fetchall()
            trials = self.db.execute("SELECT COUNT(*) FROM trials").fetchone()[0]
            real = [r for r in rows if not r["pilot"] and r["status"] != "abandoned"]
            ones = sum(r["group_no"] == 1 for r in real)
            return {
                "completed": sum(1 for r in rows if not r["pilot"] and r["status"] == "completed"),
                "pilot": sum(1 for r in rows if r["pilot"]),
                "active": sum(1 for r in rows if r["status"] == "active"),
                "abandoned": sum(1 for r in rows if r["status"] == "abandoned"),
                "responses": trials,
                "group_counts": {"1": ones, "2": len(real) - ones},
                "next_group": 1 if ones <= len(real) - ones else 2,
                "next_id": {"real": self._next_id(0, peek=True), "pilot": self._next_id(1, peek=True)},
                "trials_per_session": len(self.group_clips(1)),
                "practice": self.manifest["practice"],
                "missing_audio": self.missing_audio(),
                "database": str(DB),
            }

    def _next_id(self, pilot: int, peek: bool = False) -> str:
        prefix = "T" if pilot else "P"
        n = self.db.execute("SELECT COUNT(*) FROM sessions WHERE pilot = ?", (pilot,)).fetchone()[0]
        return f"{prefix}{n + 1:02d}"

    def create_session(self, group: int, pilot: bool, name: str, user_agent: str) -> dict:
        if group not in (1, 2):
            raise ValueError("group must be 1 or 2")
        seed = secrets.randbits(32)
        order = self.group_clips(group)
        Random(seed).shuffle(order)
        with LOCK:
            pid = self._next_id(int(pilot))
            sid = str(uuid.uuid4())
            self.db.execute(
                "INSERT INTO sessions (session_id, participant_id, group_no, pilot, seed, trial_order, created_at, user_agent)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (sid, pid, group, int(pilot), seed, json.dumps(order), now(), user_agent[:300]))
            if name.strip():
                self.names.execute("INSERT OR REPLACE INTO names VALUES (?, ?, ?)", (pid, name.strip()[:200], now()))
        return self.session(sid)

    def session(self, sid: str) -> dict | None:
        row = self.db.execute("SELECT * FROM sessions WHERE session_id = ?", (sid,)).fetchone()
        if row is None:
            return None
        trials = self.db.execute(
            "SELECT trial_index, clip_id, liking, ending, attribution, replays, response_ms, answered_at"
            " FROM trials WHERE session_id = ? ORDER BY trial_index", (sid,)).fetchall()
        s = {k: row[k] for k in row.keys() if k not in ("seed", "user_agent")}
        s["trial_order"] = json.loads(row["trial_order"])
        s["pilot"] = bool(row["pilot"])
        s["trials"] = [dict(t) for t in trials]
        s["practice"] = self.manifest["practice"]
        return s

    def event(self, sid: str, kind: str, value: str | None) -> dict:
        with LOCK:
            s = self.session(sid)
            if s is None:
                raise LookupError("unknown session")
            if s["status"] != "active":
                return s
            if kind == "consent":
                self.db.execute("UPDATE sessions SET consent_at = COALESCE(consent_at, ?) WHERE session_id = ?", (now(), sid))
            elif kind == "experience":
                if value not in EXPERIENCE:
                    raise ValueError("experience must be none, some or trained")
                if not s["consent_at"]:
                    raise PermissionError("no consent recorded")
                self.db.execute("UPDATE sessions SET experience = ? WHERE session_id = ?", (value, sid))
            elif kind == "soundcheck":
                self.db.execute("UPDATE sessions SET soundcheck_at = COALESCE(soundcheck_at, ?) WHERE session_id = ?", (now(), sid))
            elif kind == "complete":
                if len(s["trials"]) < len(s["trial_order"]):
                    raise PermissionError(f"only {len(s['trials'])} of {len(s['trial_order'])} trials saved")
                self.db.execute("UPDATE sessions SET status = 'completed', completed_at = ? WHERE session_id = ?", (now(), sid))
            elif kind == "abandon":
                self.db.execute("UPDATE sessions SET status = 'abandoned' WHERE session_id = ?", (sid,))
            else:
                raise ValueError(f"unknown event {kind}")
            return self.session(sid)

    def save_trial(self, sid: str, t: dict) -> dict:
        with LOCK:
            s = self.session(sid)
            if s is None:
                raise LookupError("unknown session")
            if not s["consent_at"]:
                raise PermissionError("no consent recorded")
            i = int(t["trial_index"])
            if not 0 <= i < len(s["trial_order"]) or s["trial_order"][i] != t["clip_id"]:
                raise ValueError("the clip does not match the stored order at this position")
            liking, ending, replays, ms = int(t["liking"]), int(t["ending"]), int(t["replays"]), int(t["response_ms"])
            if not (1 <= liking <= 5 and 1 <= ending <= 5) or t["attribution"] not in ("person", "computer") \
                    or replays < 0 or ms < 0:
                raise ValueError("answer out of range")
            record = (sid, i, t["clip_id"], liking, ending, t["attribution"], replays, ms, str(t["answered_at"])[:40], now())
            # only a repeat of the same (session, trial) is skipped; any other problem raises
            cur = self.db.execute("INSERT INTO trials VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
                                  " ON CONFLICT (session_id, trial_index) DO NOTHING", record)
            duplicate = cur.rowcount == 0
            if not duplicate:
                with self.log.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"session_id": sid, "participant_id": s["participant_id"], **t,
                                         "received_at": record[-1]}) + "\n")
            return {"saved": True, "duplicate": duplicate, "trial_index": i}

    # --- exports ---------------------------------------------------------------------------------------
    def answers_csv(self) -> str:
        rows = self.db.execute(
            "SELECT s.participant_id, s.session_id, s.group_no, s.pilot, s.status, s.experience, t.*"
            " FROM trials t JOIN sessions s USING (session_id)"
            " ORDER BY s.created_at, t.trial_index").fetchall()
        out = io.StringIO()
        w = csv.writer(out, lineterminator="\n")
        w.writerow(["participant_id", "session_id", "group", "pilot", "session_status", "experience",
                    "presentation_order", "clip_id", "condition", "clip_number", "attention_check",
                    "liking", "ending", "attribution", "replays", "response_ms", "answered_at", "received_at"])
        for r in rows:
            k = self.key.get(r["clip_id"], {})
            attention = k.get("condition") == "attention"
            w.writerow([r["participant_id"], r["session_id"], r["group_no"], r["pilot"], r["status"], r["experience"],
                        r["trial_index"] + 1, r["clip_id"], k.get("condition", "unknown"), k.get("index", ""),
                        k.get("source", {}).get("clip", "") if attention else "",
                        r["liking"], r["ending"], r["attribution"], r["replays"], r["response_ms"],
                        r["answered_at"], r["received_at"]])
        return out.getvalue()

    def sessions_csv(self) -> str:
        rows = self.db.execute("SELECT * FROM sessions ORDER BY created_at").fetchall()
        counts = dict(self.db.execute("SELECT session_id, COUNT(*) FROM trials GROUP BY session_id").fetchall())
        out = io.StringIO()
        w = csv.writer(out, lineterminator="\n")
        w.writerow(["participant_id", "session_id", "group", "pilot", "status", "experience", "trials_saved",
                    "seed", "trial_order", "created_at", "consent_at", "soundcheck_at", "completed_at"])
        for r in rows:
            w.writerow([r["participant_id"], r["session_id"], r["group_no"], r["pilot"], r["status"], r["experience"],
                        counts.get(r["session_id"], 0), r["seed"], " ".join(json.loads(r["trial_order"])),
                        r["created_at"], r["consent_at"], r["soundcheck_at"], r["completed_at"]])
        return out.getvalue()

    def names_csv(self) -> str:
        out = io.StringIO()
        w = csv.writer(out, lineterminator="\n")
        w.writerow(["participant_id", "name", "created_at"])
        w.writerows(self.names.execute("SELECT participant_id, name, created_at FROM names ORDER BY participant_id"))
        return out.getvalue()


class Handler(SimpleHTTPRequestHandler):
    store: Store

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST), **kwargs)

    def log_message(self, fmt, *args):
        if "/api/" in str(args[0] if args else "") or fmt.startswith("code"):
            super().log_message(fmt, *args)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store" if self.path.startswith("/api/") else "no-cache")
        super().end_headers()

    # --- helpers ---
    def send_json(self, body, status=HTTPStatus.OK):
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_csv(self, text: str, filename: str):
        data = ("﻿" + text).encode("utf-8")          # BOM so Excel reads the UTF-8 correctly
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/csv; charset=utf-8")
        self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_audio(self, name: str):
        """MP3 with byte ranges, so the browser can rewind for a replay."""
        file = DIST / "clips" / name
        if "/" in name or "\\" in name or not file.is_file():
            return self.send_error(HTTPStatus.NOT_FOUND)
        data = file.read_bytes()
        start, end = 0, len(data) - 1
        ranged = self.headers.get("Range", "").startswith("bytes=")
        if ranged:
            a, _, b = self.headers["Range"][6:].split(",")[0].partition("-")
            start = int(a) if a else max(0, len(data) - int(b))
            end = min(int(b), len(data) - 1) if a and b else end
            if start > end:
                self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
                self.send_header("Content-Range", f"bytes */{len(data)}")
                return self.end_headers()
        self.send_response(HTTPStatus.PARTIAL_CONTENT if ranged else HTTPStatus.OK)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Accept-Ranges", "bytes")
        if ranged:
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
        self.send_header("Content-Length", str(end - start + 1))
        self.end_headers()
        self.wfile.write(data[start:end + 1])

    def body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n) or b"{}") if n else {}

    def guarded(self, fn):
        try:
            fn()
        except LookupError as e:
            self.send_json({"error": str(e)}, HTTPStatus.NOT_FOUND)
        except PermissionError as e:
            self.send_json({"error": str(e)}, HTTPStatus.CONFLICT)
        except (ValueError, KeyError, TypeError, json.JSONDecodeError, sqlite3.IntegrityError) as e:
            self.send_json({"error": f"bad request: {e}"}, HTTPStatus.BAD_REQUEST)

    # --- routes ---
    def do_GET(self):
        path = urlparse(self.path).path
        s = self.store
        stamp = time.strftime("%Y%m%d-%H%M")
        if path == "/api/state":
            return self.send_json(s.state())
        if path.startswith("/api/session/"):
            def go():
                found = s.session(path.rsplit("/", 1)[1])
                if found is None:
                    raise LookupError("unknown session")
                self.send_json(found)
            return self.guarded(go)
        if path == "/api/export/answers.csv":
            return self.send_csv(s.answers_csv(), f"listening_answers_{stamp}.csv")
        if path == "/api/export/sessions.csv":
            return self.send_csv(s.sessions_csv(), f"listening_sessions_{stamp}.csv")
        if path == "/api/export/names.csv":
            return self.send_csv(s.names_csv(), f"listening_names_{stamp}.csv")
        if path.startswith("/api/"):
            return self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
        if path.startswith("/clips/") and path.endswith(".mp3"):
            return self.send_audio(path.rsplit("/", 1)[1])
        if not (DIST / path.lstrip("/")).is_file() or path == "/":
            self.path = "/index.html"                    # single-page app
        return super().do_GET()

    def do_POST(self):
        path = urlparse(self.path).path
        s = self.store
        if path == "/api/session":
            def go():
                b = self.body()
                self.send_json(s.create_session(int(b["group"]), bool(b.get("pilot")), str(b.get("name") or ""),
                                                self.headers.get("User-Agent", "")), HTTPStatus.CREATED)
            return self.guarded(go)
        parts = path.strip("/").split("/")                # api/session/<id>/<action>
        if len(parts) == 4 and parts[:2] == ["api", "session"]:
            sid, action = parts[2], parts[3]
            if action == "trial":
                return self.guarded(lambda: self.send_json(s.save_trial(sid, self.body())))
            if action == "event":
                def go():
                    b = self.body()
                    self.send_json(s.event(sid, str(b["type"]), b.get("value")))
                return self.guarded(go)
        self.send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data", type=Path, default=DATA,
                        help="folder for the databases (default results/listening); use another one for trial runs")
    args = parser.parse_args()
    global DB
    DB = args.data / DB.name
    if not (DIST / "index.html").is_file():
        raise SystemExit("listening_test/dist is missing: run `npm run build` in listening_test first.")
    mimetypes.add_type("audio/mpeg", ".mp3")
    mimetypes.add_type("text/javascript", ".js")
    Handler.store = Store(DB, args.data / NAMES_DB.name, args.data / LOG.name)
    missing = Handler.store.missing_audio()
    if missing:
        print("WARNING, audio files missing:", ", ".join(missing))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"Listening test running at http://127.0.0.1:{args.port}  (data: {DB})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
