"""SQLite storage. One connection + a lock: simple, safe for a single
process, and enough for this service's scale. Swap for Postgres later
without changing the routers/services (they only use this module's API).

Tables:
  messages          every outbound message + its delivery state
  otp_codes         OTP hashes only (plaintext only in DEV_MODE, see below)
  inbound_messages  messages received via webhooks
  idempotency_keys  Idempotency-Key header -> stored response
"""

import json
import os
import sqlite3
import threading
import time
import uuid

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    to_phone TEXT NOT NULL,
    channel TEXT NOT NULL,
    provider TEXT NOT NULL,
    body TEXT,
    template_name TEXT,
    status TEXT NOT NULL,
    provider_message_id TEXT,
    fallback_channel TEXT,
    error TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS otp_codes (
    id TEXT PRIMARY KEY,
    phone TEXT NOT NULL,
    code_hash TEXT NOT NULL,
    dev_code TEXT,
    channel TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS inbound_messages (
    id TEXT PRIMARY KEY,
    from_phone TEXT,
    channel TEXT NOT NULL,
    provider TEXT NOT NULL,
    body TEXT,
    raw TEXT,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS idempotency_keys (
    key TEXT PRIMARY KEY,
    response_json TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_phone ON messages(to_phone);
CREATE INDEX IF NOT EXISTS idx_otp_phone ON otp_codes(phone, status);
"""


class Database:
    def __init__(self, path: str) -> None:
        if path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # -- generic helpers -------------------------------------------------
    def _execute(self, sql: str, params=()):
        with self._lock:
            cur = self._conn.execute(sql, params)
            self._conn.commit()
            return cur

    def _fetchone(self, sql: str, params=()):
        with self._lock:
            return self._conn.execute(sql, params).fetchone()

    def _fetchall(self, sql: str, params=()):
        with self._lock:
            return self._conn.execute(sql, params).fetchall()

    # -- messages --------------------------------------------------------
    def insert_message(self, *, to_phone, channel, provider, body,
                       template_name=None, fallback_channel=None) -> dict:
        now = time.time()
        row = {
            "id": uuid.uuid4().hex,
            "to_phone": to_phone,
            "channel": channel,
            "provider": provider,
            "body": body,
            "template_name": template_name,
            "status": "queued",
            "provider_message_id": None,
            "fallback_channel": fallback_channel,
            "error": None,
            "created_at": now,
            "updated_at": now,
        }
        self._execute(
            "INSERT INTO messages VALUES (:id, :to_phone, :channel, :provider,"
            " :body, :template_name, :status, :provider_message_id,"
            " :fallback_channel, :error, :created_at, :updated_at)", row)
        return row

    def update_message(self, message_id: str, **fields) -> None:
        fields["updated_at"] = time.time()
        assignments = ", ".join(f"{k} = :{k}" for k in fields)
        self._execute(
            f"UPDATE messages SET {assignments} WHERE id = :id",
            {**fields, "id": message_id})

    def get_message(self, message_id: str):
        row = self._fetchone("SELECT * FROM messages WHERE id = ?", (message_id,))
        return dict(row) if row else None

    def get_message_by_provider_id(self, provider_message_id: str):
        row = self._fetchone(
            "SELECT * FROM messages WHERE provider_message_id = ?",
            (provider_message_id,))
        return dict(row) if row else None

    def list_messages(self, *, status=None, channel=None, limit=50):
        sql = "SELECT * FROM messages"
        clauses, params = [], []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if channel:
            clauses.append("channel = ?")
            params.append(channel)
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return [dict(r) for r in self._fetchall(sql, params)]

    # -- OTP -------------------------------------------------------------
    def insert_otp(self, *, phone, code_hash, dev_code, channel, expires_at) -> dict:
        row = {
            "id": uuid.uuid4().hex,
            "phone": phone,
            "code_hash": code_hash,
            "dev_code": dev_code,
            "channel": channel,
            "attempts": 0,
            "status": "active",
            "created_at": time.time(),
            "expires_at": expires_at,
        }
        self._execute("INSERT INTO otp_codes VALUES (:id, :phone, :code_hash,"
                      " :dev_code, :channel, :attempts, :status, :created_at,"
                      " :expires_at)", row)
        return row

    def invalidate_active_otps(self, phone: str) -> None:
        self._execute(
            "UPDATE otp_codes SET status = 'superseded' WHERE phone = ?"
            " AND status = 'active'", (phone,))

    def get_active_otp(self, phone: str):
        row = self._fetchone(
            "SELECT * FROM otp_codes WHERE phone = ? AND status = 'active'"
            " ORDER BY created_at DESC LIMIT 1", (phone,))
        return dict(row) if row else None

    def get_latest_otp(self, phone: str):
        row = self._fetchone(
            "SELECT * FROM otp_codes WHERE phone = ?"
            " ORDER BY created_at DESC LIMIT 1", (phone,))
        return dict(row) if row else None

    def get_dev_code(self, phone: str):
        row = self._fetchone(
            "SELECT dev_code FROM otp_codes WHERE phone = ? AND status = 'active'"
            " ORDER BY created_at DESC LIMIT 1", (phone,))
        return row["dev_code"] if row and row["dev_code"] else None

    def update_otp(self, otp_id: str, **fields) -> None:
        assignments = ", ".join(f"{k} = :{k}" for k in fields)
        self._execute(
            f"UPDATE otp_codes SET {assignments} WHERE id = :id",
            {**fields, "id": otp_id})

    def count_recent_otp_sends(self, phone: str, since: float) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) AS n FROM otp_codes WHERE phone = ?"
            " AND created_at >= ?", (phone, since))
        return row["n"]

    def last_otp_sent_at(self, phone: str):
        row = self._fetchone(
            "SELECT created_at FROM otp_codes WHERE phone = ?"
            " ORDER BY created_at DESC LIMIT 1", (phone,))
        return row["created_at"] if row else None

    # -- inbound + idempotency -------------------------------------------
    def insert_inbound(self, *, from_phone, channel, provider, body, raw) -> dict:
        row = {
            "id": uuid.uuid4().hex,
            "from_phone": from_phone,
            "channel": channel,
            "provider": provider,
            "body": body,
            "raw": json.dumps(raw),
            "created_at": time.time(),
        }
        self._execute("INSERT INTO inbound_messages VALUES (:id, :from_phone,"
                      " :channel, :provider, :body, :raw, :created_at)", row)
        return row

    def get_idempotency(self, key: str):
        row = self._fetchone(
            "SELECT response_json FROM idempotency_keys WHERE key = ?", (key,))
        return json.loads(row["response_json"]) if row else None

    def save_idempotency(self, key: str, response: dict) -> None:
        self._execute(
            "INSERT OR IGNORE INTO idempotency_keys VALUES (?, ?, ?)",
            (key, json.dumps(response), time.time()))
