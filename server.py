"""Local-only practice service with durable scores and server-side grading."""

import base64
import hashlib
import json
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from simulator import BY_ID, TASKS, dataset, grade, markdown, public_task

ROOT = Path(__file__).parent
DB = Path(os.environ.get("SIM_DB", str(ROOT / "practice.sqlite3")))
DURATION = 3 * 60 * 60
MAX_BODY = 14 * 1024 * 1024
ALLOWED_HOSTS = {"localhost", "127.0.0.1", *filter(None, os.environ.get("ALLOWED_HOSTS", "").split(","))}


@contextmanager
def connect():
    c = sqlite3.connect(DB, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        with c:
            yield c
    finally:
        c.close()


def init_db():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, started REAL, mode TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS submissions (id INTEGER PRIMARY KEY, session TEXT NOT NULL,
        problem TEXT NOT NULL, part TEXT NOT NULL, score REAL NOT NULL, feedback TEXT NOT NULL,
        created REAL NOT NULL, hash TEXT);
        CREATE INDEX IF NOT EXISTS history ON submissions(session,problem,part);
        """)


class Handler(BaseHTTPRequestHandler):
    def send(self, status, body, kind="application/json; charset=utf-8", extra=None):
        if isinstance(body, (dict, list)):
            body = json.dumps(body, ensure_ascii=False).encode()
        if isinstance(body, str):
            body = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", kind)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' blob:; object-src 'none'; frame-ancestors 'none'",
        )
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def session(self, c):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            return None
        sid = cookie["session"].value if "session" in cookie else ""
        return c.execute("SELECT * FROM sessions WHERE id=?", (sid,)).fetchone()

    def state(self, c, s):
        scores = [
            dict(x)
            for x in c.execute(
                "SELECT problem,part,MAX(score) score FROM submissions WHERE session=? GROUP BY problem,part",
                (s["id"],),
            )
        ]
        history = [
            dict(x)
            for x in c.execute(
                """SELECT id,problem,part,score,feedback,created FROM
                (SELECT *, ROW_NUMBER() OVER (PARTITION BY problem ORDER BY id DESC) AS rn
                FROM submissions WHERE session=?) WHERE rn<=12 ORDER BY id DESC""",
                (s["id"],),
            )
        ]
        for x in history:
            x["feedback"] = json.loads(x["feedback"])
        return dict(
            mode=s["mode"],
            started=s["started"],
            expires=s["started"] + DURATION if s["mode"] == "contest" else None,
            server_time=time.time(),
            scores=scores,
            history=history,
        )

    def valid_host(self):
        try:
            host = urlsplit("http://" + self.headers.get("Host", "")).hostname
        except ValueError:
            host = None
        if host not in ALLOWED_HOSTS:
            self.send(403, {"error": "허용되지 않은 호스트입니다."})
            return False
        return True

    def do_GET(self):
        if not self.valid_host():
            return
        path = urlsplit(self.path).path
        if path in ("/", "/app.js", "/style.css"):
            f = ROOT / "static" / ({"/": "index.html"}.get(path, path[1:]))
            return self.send(
                200,
                f.read_bytes(),
                {
                    "html": "text/html; charset=utf-8",
                    "js": "text/javascript; charset=utf-8",
                    "css": "text/css; charset=utf-8",
                }[f.suffix[1:]],
            )
        if path == "/api/problems":
            return self.send(200, [public_task(t) for t in TASKS])
        parts = path.strip("/").split("/")
        if len(parts) == 4 and parts[:2] == ["api", "problems"] and parts[2] in BY_ID:
            t = BY_ID[parts[2]]
            if parts[3] == "dataset":
                return self.send(
                    200,
                    dataset(t),
                    "application/zip",
                    {
                        "Content-Disposition": f'attachment; filename="{t["id"]}-dataset.zip"'
                    },
                )
            if parts[3] == "markdown":
                return self.send(200, markdown(t), "text/plain; charset=utf-8")
        with connect() as c:
            if path == "/api/session":
                s = self.session(c)
                return (
                    self.send(200, self.state(c, s))
                    if s
                    else self.send(
                        200,
                        {
                            "mode": None,
                            "scores": [],
                            "history": [],
                            "server_time": time.time(),
                        },
                    )
                )
            if path == "/api/ranking":
                rows = c.execute(
                    """SELECT session, SUM(score) score FROM
                (SELECT session,problem,part,MAX(score) score FROM submissions GROUP BY session,problem,part)
                JOIN sessions ON sessions.id=session WHERE mode='contest' GROUP BY session ORDER BY score DESC,session LIMIT 20"""
                ).fetchall()
                return self.send(
                    200,
                    [
                        {
                            "rank": i + 1,
                            "name": f'참가 {x["session"][:6]}',
                            "score": x["score"],
                        }
                        for i, x in enumerate(rows)
                    ],
                )
        self.send(404, {"error": "찾을 수 없습니다."})

    def do_POST(self):
        if not self.valid_host():
            return
        # JSON-only endpoints plus an Origin check prevent cross-site local-server writes.
        origin = self.headers.get("Origin")
        if origin and origin not in (
            "http://" + self.headers.get("Host", ""),
            "https://" + self.headers.get("Host", ""),
        ):
            return self.send(403, {"error": "다른 출처의 요청은 허용하지 않습니다."})
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
            return self.send(415, {"error": "application/json만 지원합니다."})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= MAX_BODY:
                return self.send(413, {"error": "요청 크기 제한을 초과했습니다."})
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("JSON 객체가 필요합니다.")
            path = urlsplit(self.path).path
            with connect() as c:
                c.execute("BEGIN IMMEDIATE")
                s = self.session(c)
                if path == "/api/session":
                    mode = body.get("mode")
                    if mode not in ("practice", "contest"):
                        raise ValueError("연습 또는 대회 모드를 선택하세요.")
                    sid = secrets.token_hex(16)
                    c.execute(
                        "INSERT INTO sessions VALUES (?,?,?)", (sid, time.time(), mode)
                    )
                    # Each explicit start creates a new attempt; the previous attempt remains in ranking.
                    s = c.execute(
                        "SELECT * FROM sessions WHERE id=?", (sid,)
                    ).fetchone()
                    result = self.state(c, s)
                    c.commit()
                    return self.send(
                        201,
                        result,
                        extra={
                            "Set-Cookie": f"session={sid}; HttpOnly; SameSite=Strict; Path=/; Max-Age=2592000"
                        },
                    )
                if path != "/api/submit":
                    return self.send(404, {"error": "찾을 수 없습니다."})
                if not s:
                    return self.send(
                        409, {"error": "먼저 연습 또는 대회를 시작하세요."}
                    )
                now = time.time()
                if s["mode"] == "contest" and now >= s["started"] + DURATION:
                    return self.send(409, {"error": "대회 시간이 종료되었습니다."})
                t = BY_ID.get(body.get("problem"))
                if not t:
                    raise ValueError("유효한 문제를 선택하세요.")
                part = body.get("part")
                if type(part) is not str or part not in [p["id"] for p in t["parts"]]:
                    raise ValueError("유효한 하위 문항을 선택하세요.")
                answer = body.get("answer")
                digest = None
                if t["parts"][int(part) - 1]["type"] == "image":
                    if not isinstance(answer, str):
                        raise ValueError("이미지 파일이 필요합니다.")
                    try:
                        answer = base64.b64decode(answer, validate=True)
                    except ValueError:
                        raise ValueError("이미지 인코딩이 잘못되었습니다.")
                    if len(answer) > 10 * 1024 * 1024:
                        raise ValueError("10MB 이하 이미지만 제출하세요.")
                    digest = hashlib.sha256(answer).hexdigest()
                    if c.execute(
                        "SELECT 1 FROM submissions WHERE session=? AND problem=? AND hash=?",
                        (s["id"], t["id"], digest),
                    ).fetchone():
                        return self.send(409, {"error": "이미 평가한 파일입니다."})
                    last = c.execute(
                        "SELECT MAX(created) FROM submissions WHERE session=? AND problem=?",
                        (s["id"], t["id"]),
                    ).fetchone()[0]
                    if last is not None and now - last < 60:
                        return self.send(
                            429,
                            {
                                "error": f"{int(60-(now-last))+1}초 후에 다시 제출하세요."
                            },
                        )
                score, feedback = grade(t, int(part) - 1, answer)
                c.execute(
                    "INSERT INTO submissions(session,problem,part,score,feedback,created,hash) VALUES (?,?,?,?,?,?,?)",
                    (s["id"], t["id"], part, score, json.dumps(feedback), now, digest),
                )
                result = dict(score=score, feedback=feedback, state=self.state(c, s))
                c.commit()
                return self.send(200, result)
        except (ValueError, TypeError, KeyError) as e:
            self.send(400, {"error": str(e) or "입력을 확인하세요."})
        except sqlite3.Error:
            self.send(
                503, {"error": "저장소가 사용 중입니다. 잠시 후 다시 시도하세요."}
            )


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", "7101"))
    if not 1 <= port <= 65535:
        raise SystemExit("PORT must be between 1 and 65535")
    server = ThreadingHTTPServer((os.environ.get("HOST", "127.0.0.1"), port), Handler)
    print(f"AI TOP100 practice: http://localhost:{port}", flush=True)
    server.serve_forever()
