import base64
import http.client
import io
import json
import tempfile
import threading
import time
import unittest
from pathlib import Path
from http.server import ThreadingHTTPServer
from PIL import Image
import server
from simulator import (
    BY_ID,
    TASKS,
    dataset,
    grade,
    image_bytes,
    public_task,
    target_image,
)


class GradingTests(unittest.TestCase):
    def test_known_answers_and_downloads(self):
        import zipfile

        for t in TASKS:
            self.assertNotIn("answers", public_task(t))
            with zipfile.ZipFile(io.BytesIO(dataset(t))) as z:
                self.assertEqual(set(z.namelist()), {"README.md", *t["files"]})
            for i, a in enumerate(t["answers"]):
                if a is not None:
                    self.assertEqual(grade(t, i, a)[0], t["parts"][i]["max_score"])

    def test_partial_json_and_duplicate_ids(self):
        t = BY_ID["battle"]
        a = [dict(x) for x in t["answers"][0]]
        a[0]["winner"] = "invalid"
        self.assertEqual(grade(t, 0, a)[0], 57)
        with self.assertRaises(ValueError):
            grade(t, 0, [a[0]] * 20)
        with self.assertRaises(ValueError):
            grade(t, 0, [])
        self.assertEqual(grade(t, 0, list(reversed(t["answers"][0])))[0], 60)

    def test_image_validation_and_rubric(self):
        self.assertEqual(
            grade(BY_ID["montage"], 0, image_bytes(target_image()))[0], 100
        )
        with self.assertRaises(ValueError):
            grade(BY_ID["montage"], 0, image_bytes(Image.new("RGB", (64, 64))))
        with self.assertRaises(ValueError):
            grade(BY_ID["montage"], 0, b"broken")
        report = (
            "# 현황\nAPI timeout\n검색 인덱스\n# 할 일\n23일 24일\n# 담당자\nMina Joon"
        )
        self.assertEqual(grade(BY_ID["handover"], 0, report)[0], 70)
        self.assertEqual(grade(BY_ID["handover"], 0, report + "\n미래 배포")[0], 60)


class APITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        server.DB = Path(cls.tmp.name) / "test.sqlite3"
        server.init_db()
        cls.http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        cls.thread = threading.Thread(target=cls.http.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown()
        cls.http.server_close()
        cls.thread.join()
        cls.tmp.cleanup()

    def setUp(self):
        self.cookie = ""

    def request(self, path, body=None, origin=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.http.server_port)
        headers = {"Cookie": self.cookie}
        if body is not None:
            headers["Content-Type"] = "application/json"
        if origin:
            headers["Origin"] = origin
        conn.request(
            "GET" if body is None else "POST",
            path,
            None if body is None else json.dumps(body),
            headers,
        )
        r = conn.getresponse()
        status = r.status
        if r.getheader("Set-Cookie"):
            self.cookie = r.getheader("Set-Cookie").split(";")[0]
        data = json.loads(r.read())
        conn.close()
        return status, data

    def start(self, mode="practice"):
        self.assertEqual(self.request("/api/session", {"mode": mode})[0], 201)

    def submit(self, problem="menu", part="1", answer="Meal 1"):
        return self.request(
            "/api/submit", dict(problem=problem, part=part, answer=answer)
        )

    def test_session_and_best_score(self):
        self.assertEqual(self.submit()[0], 409)
        self.start()
        self.assertEqual(self.submit()[1]["score"], 10)
        self.assertEqual(self.submit(answer="wrong")[1]["score"], 0)
        state = self.request("/api/session")[1]
        self.assertEqual(state["scores"][0]["score"], 10)
        self.assertEqual(len(state["history"]), 2)
        oldcookie = self.cookie
        self.start()
        self.assertNotEqual(oldcookie, self.cookie)
        self.assertEqual(self.request("/api/session")[1]["history"], [])

    def test_deadline_and_ranking(self):
        self.start("contest")
        self.submit()
        self.assertTrue(any(x["score"] >= 10 for x in self.request("/api/ranking")[1]))
        sid = self.cookie.split("=")[1]
        with server.connect() as c:
            c.execute(
                "UPDATE sessions SET started=? WHERE id=?", (time.time() - 10801, sid)
            )
        self.assertEqual(self.submit()[0], 409)

    def test_image_rate_duplicate_and_history(self):
        self.start()
        answer = base64.b64encode(image_bytes(target_image())).decode()
        self.assertEqual(self.submit("montage", "1", answer)[0], 200)
        self.assertEqual(self.submit("montage", "1", answer)[0], 409)
        alternate = target_image()
        alternate.putpixel((0, 0), (0, 0, 0))
        other = base64.b64encode(image_bytes(alternate)).decode()
        self.assertEqual(self.submit("montage", "1", other)[0], 429)
        sid = self.cookie.split("=")[1]
        with server.connect() as c:
            c.execute(
                "UPDATE submissions SET created=? WHERE session=?",
                (time.time() - 61, sid),
            )
        self.assertEqual(self.submit("montage", "1", other)[0], 200)
        with server.connect() as c:
            c.executemany(
                "INSERT INTO submissions(session,problem,part,score,feedback,created) VALUES (?,?,?,?,?,?)",
                [
                    (sid, "menu", "1", 0, '{"correct": false}', time.time())
                    for _ in range(105)
                ],
            )
        history = self.request("/api/session")[1]["history"]
        self.assertEqual(len([h for h in history if h["problem"] == "montage"]), 2)
        self.assertEqual(len([h for h in history if h["problem"] == "menu"]), 12)

    def test_isolation_origin_and_invalid_input(self):
        self.start()
        self.submit()
        cookie = self.cookie
        self.cookie = ""
        self.start()
        self.assertEqual(self.request("/api/session")[1]["history"], [])
        self.cookie = cookie
        self.assertEqual(
            self.request(
                "/api/session", {"mode": "practice"}, "https://attacker.invalid"
            )[0],
            403,
        )
        self.assertEqual(self.submit("unknown")[0], 400)
        self.assertEqual(self.submit(part="999")[0], 400)
        self.assertEqual(self.submit("menu", "2", True)[0], 400)
        self.assertEqual(self.submit("battle", "1", [])[0], 400)


if __name__ == "__main__":
    unittest.main()
