"""SQLite persistence with user-scoped reads and salted password derivation."""
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
import time
import uuid
from pathlib import Path


class Store:
    def __init__(self, path=None):
        self.path = Path(path or os.environ.get("TRENDWATCHER_DB", "data/trendwatcher.sqlite3"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, username TEXT UNIQUE, salt TEXT, digest TEXT);
                CREATE TABLE IF NOT EXISTS attempts(username TEXT PRIMARY KEY, count INTEGER, until REAL);
                CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY, user_id TEXT, created REAL, payload TEXT);
                CREATE TABLE IF NOT EXISTS cache(user_id TEXT, key TEXT, payload TEXT, PRIMARY KEY(user_id,key));
                CREATE TABLE IF NOT EXISTS notes(user_id TEXT, article_id TEXT, payload TEXT, PRIMARY KEY(user_id,article_id));
            """)

    def connect(self):
        return sqlite3.connect(self.path, timeout=15)

    @staticmethod
    def digest(password, salt):
        return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()

    def register(self, username, password):
        username = username.strip().casefold()
        if not re.fullmatch(r"[a-z0-9_-]{3,32}", username):
            raise ValueError("Логин: 3–32 символа, латинские буквы, цифры, _ или -.")
        if not 10 <= len(password) <= 256:
            raise ValueError("Пароль должен содержать от 10 до 256 символов.")
        salt, user_id = secrets.token_hex(16), uuid.uuid4().hex
        try:
            with self.connect() as db:
                db.execute("INSERT INTO users VALUES (?,?,?,?)", (user_id, username, salt, self.digest(password, salt)))
        except sqlite3.IntegrityError:
            raise ValueError("Этот логин уже занят.") from None
        return {"id": user_id, "username": username}

    def login(self, username, password):
        username = username.strip().casefold()[:32]
        if len(password) > 256:
            return None
        with self.connect() as db:
            # Serialize attempt accounting across concurrent sessions.
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT count,until FROM attempts WHERE username=?", (username,)).fetchone()
            now = time.time()
            if row and row[0] >= 5 and row[1] > now:
                raise ValueError("Слишком много попыток. Повторите вход через 15 минут.")
            user = db.execute("SELECT id,username,salt,digest FROM users WHERE username=?", (username,)).fetchone()
            actual = self.digest(password, user[2] if user else "00"*16)
            if user and hmac.compare_digest(actual, user[3]):
                db.execute("DELETE FROM attempts WHERE username=?", (username,))
                return {"id": user[0], "username": user[1]}
            count = row[0] + 1 if row and row[1] > now else 1
            db.execute("INSERT OR REPLACE INTO attempts VALUES (?,?,?)", (username, count, now + 900))
        return None

    def save_run(self, user_id, results):
        run_id = uuid.uuid4().hex
        with self.connect() as db:
            db.execute("INSERT INTO runs VALUES (?,?,?,?)", (run_id, user_id, time.time(), json.dumps(results, ensure_ascii=False)))
            db.execute("DELETE FROM runs WHERE user_id=? AND id NOT IN (SELECT id FROM runs WHERE user_id=? ORDER BY created DESC LIMIT 50)", (user_id, user_id))
        return run_id

    def runs(self, user_id):
        with self.connect() as db:
            rows = db.execute("SELECT id,payload FROM runs WHERE user_id=? ORDER BY created DESC LIMIT 50", (user_id,)).fetchall()
        return [{"id": r[0], **json.loads(r[1])} for r in rows]

    def cache_get(self, user_id, key):
        with self.connect() as db:
            r = db.execute("SELECT payload FROM cache WHERE user_id=? AND key=?", (user_id, key)).fetchone()
        return json.loads(r[0]) if r else None

    def cache_put(self, user_id, key, value):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?)", (user_id, key, json.dumps(value, ensure_ascii=False)))

    def annotations(self, user_id):
        with self.connect() as db:
            rows = db.execute("SELECT article_id,payload FROM notes WHERE user_id=?", (user_id,)).fetchall()
        return {r[0]: json.loads(r[1]) for r in rows}

    def annotate(self, user_id, article_id, data):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO notes VALUES (?,?,?)", (user_id, article_id, json.dumps(data, ensure_ascii=False)))
