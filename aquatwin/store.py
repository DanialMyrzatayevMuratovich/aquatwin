"""Remembers each user's language between bot restarts (Postgres). Optional.

Without DATABASE_URL the store is switched off and languages live in memory only.
A database problem never breaks a reply: errors are logged and the store rests for a while.
Only the Telegram user id and the chosen language are stored; locations never are.
"""
from __future__ import annotations

import logging
import os
import threading
import time

log = logging.getLogger(__name__)

REST_S = 300          # after a failure the database is not tried again for this long
CONNECT_TIMEOUT_S = 5
_lock = threading.Lock()
_conn = None
_down_until = 0.0


def _url() -> str:
    return os.environ.get("DATABASE_URL", "")


def enabled() -> bool:
    return bool(_url())


def _run(sql: str, params: tuple):
    """Run one statement on a kept-alive connection; reconnect once if the connection has gone."""
    global _conn, _down_until
    if not enabled() or time.monotonic() < _down_until:
        return None
    import psycopg  # imported here so the bot runs without the driver when the store is off

    with _lock:
        for _ in range(2):
            try:
                if _conn is None or _conn.closed:
                    # prepare_threshold=None: Supabase's transaction pooler does not keep prepared statements
                    _conn = psycopg.connect(_url(), connect_timeout=CONNECT_TIMEOUT_S, autocommit=True,
                                            prepare_threshold=None)
                with _conn.cursor() as cur:
                    cur.execute(sql, params)
                    return cur.fetchone() if cur.description else ()
            except psycopg.Error as e:
                log.warning("language store: %s", str(e).strip().splitlines()[0] if str(e).strip() else type(e).__name__)
                try:
                    if _conn is not None:
                        _conn.close()
                except psycopg.Error:
                    pass
                _conn = None
        _down_until = time.monotonic() + REST_S
        return None


def ping() -> bool:
    """Open the connection at start-up, so the first user does not wait for it; logs the outcome."""
    if not enabled():
        log.info("language store is off (DATABASE_URL is not set)")
        return False
    ok = _run("select 1", ()) is not None
    log.info("language store: %s", "connected" if ok else "unavailable, languages are kept in memory")
    return ok


def get_lang(user_id: int) -> str | None:
    row = _run("select lang from aquatwin.bot_users where user_id = %s", (user_id,))
    return row[0] if row else None


def set_lang(user_id: int, lang: str) -> None:
    _run("insert into aquatwin.bot_users (user_id, lang) values (%s, %s) "
         "on conflict (user_id) do update set lang = excluded.lang, updated_at = now()", (user_id, lang))
