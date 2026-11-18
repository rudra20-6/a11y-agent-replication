"""Local web dashboard: start runs, watch them live, read reports. Standard library only.

    python -m a11y_agent dashboard            ->  http://127.0.0.1:8800/
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from .config import ROOT, RUNS, SETTINGS

PAGE = (Path(__file__).parent / "dashboard.html").read_text(encoding="utf-8")
PROCS: dict[str, subprocess.Popen] = {}
RUN_ID = re.compile(r"^[\w.-]+$")
LIVE_IMG = re.compile(r"^[\w-]+\.jpg$")  # live/<task>_<profile>.jpg or live/planner.jpg


def _json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _alive(pid: int | None) -> bool:
    if not pid:
        return False
    if sys.platform == "win32":
        out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True).stdout
        return str(pid) in out
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def list_runs() -> list[dict]:
    out = []
    for d in sorted(RUNS.glob("*/meta.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        m = _json(d) or {}
        run = d.parent.name
        if m.get("status") == "running":
            # Batch runs (experiments/) record no pid: they count as running while their event log is still being written.
            ev = d.parent / "events.jsonl"
            fresh = ev.exists() and time.time() - ev.stat().st_mtime < 300
            if not (_alive(m.get("pid")) if m.get("pid") else fresh):
                m["status"] = "interrupted"
        res = _json(d.parent / "results.json", {}) or {}
        rs = res.get("results", [])
        agent = lambda f: (f.get("evidence") or {}).get("source") == "agent"
        # v3 (D97): what the agents found (kept reports, stalls) is counted apart from the rule findings
        m.update(id=run, findings=sum(1 for r in rs for f in r.get("findings", []) if not agent(f)),
                 agent_findings=sum(sum(1 for x in r.get("agent_reports", []) if x.get("kept")) + len(r.get("agent_findings", []))
                                    + sum(1 for f in r.get("findings", []) if agent(f)) for r in rs))
        out.append(m)
    return out


def start_run(url: str, tasks: int, profiles: str, agents: bool) -> str:
    run_id = time.strftime("%Y%m%d-%H%M%S")
    run_dir = RUNS / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-u", "-m", "a11y_agent", "run", url, "--tasks", str(tasks), "--profiles", profiles,
           "--run-dir", str(run_dir)] + ([] if agents else ["--no-agents"])
    log = (run_dir / "console.log").open("w", encoding="utf-8")
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1")
    p = subprocess.Popen(cmd, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT, creationflags=flags, env=env)
    PROCS[run_id] = p
    (run_dir / "meta.json").write_text(json.dumps({"url": url, "tasks": tasks, "profiles": profiles.split(","),
                                                   "agents": agents, "status": "running", "stage": "starting",
                                                   "started": time.time(), "pid": p.pid, "model": SETTINGS.nav_model}),
                                       encoding="utf-8")
    return run_id


def stop_run(run_id: str) -> bool:
    meta_p = RUNS / run_id / "meta.json"
    meta = _json(meta_p, {}) or {}
    pid = meta.get("pid")
    if not pid:
        return False
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
    else:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    meta.update(status="stopped", stage="stopped", ended=time.time())
    meta_p.write_text(json.dumps(meta), encoding="utf-8")
    return True


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, body, code=200, ctype="application/json", cache="no-store"):
        data = body if isinstance(body, bytes) else (body if isinstance(body, str) else json.dumps(body, default=str)).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", ctype if ctype.startswith("image/") else ctype + "; charset=utf-8")
        self.send_header("Cache-Control", cache)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        parts = [p for p in u.path.split("/") if p]
        if not parts:
            return self._send(PAGE, ctype="text/html")
        if parts == ["favicon.ico"]:
            self.send_response(204)
            self.end_headers()
            return None
        if parts == ["api", "status"]:
            return self._send({"model": SETTINGS.nav_model, "key": bool(SETTINGS.gemini_api_key), "runs_dir": str(RUNS)})
        if parts == ["api", "runs"]:
            return self._send(list_runs())
        if len(parts) >= 3 and parts[:2] == ["api", "runs"] and RUN_ID.match(parts[2]):
            d = RUNS / parts[2]
            if not d.is_dir():
                return self._send({"error": "no such run"}, 404)
            what = parts[3] if len(parts) > 3 else ""
            if what == "":
                meta = next((r for r in list_runs() if r["id"] == parts[2]), _json(d / "meta.json", {}))
                return self._send({"meta": meta, "plan": _json(d / "plan.json"), "results": _json(d / "results.json")})
            if what == "events":
                since = int(q.get("since", ["0"])[0])
                lines = (d / "events.jsonl").read_text(encoding="utf-8").splitlines() if (d / "events.jsonl").exists() else []
                return self._send({"next": len(lines), "events": [json.loads(x) for x in lines[since:] if x.strip()]})
            if what == "log":
                p = d / "console.log"
                text = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
                return self._send({"text": text[-40000:]})
            if what == "report":
                p = d / "report.md"
                return self._send({"markdown": p.read_text(encoding="utf-8") if p.exists() else None})
            if what == "live" and len(parts) == 5 and LIVE_IMG.match(parts[4]):
                p = d / "live" / parts[4]
                if not p.exists():
                    return self._send({"error": "no screenshot yet"}, 404)
                # Each step requests ?v=<step>, so a cached copy is never stale.
                return self._send(p.read_bytes(), ctype="image/jpeg", cache="private, max-age=600")
        return self._send({"error": "not found"}, 404)

    def do_POST(self):
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        if parts == ["api", "runs"]:
            url = (body.get("url") or "").strip()
            if not re.match(r"^https?://", url):
                return self._send({"error": "Enter a full URL starting with http:// or https://"}, 400)
            if not SETTINGS.gemini_api_key:
                return self._send({"error": "No GEMINI_API_KEY in .env"}, 400)
            profiles = ",".join(p for p in body.get("profiles", ["P1", "P2", "P3", "P4", "P5"]) if p in ("P1", "P2", "P3", "P4", "P5"))
            run_id = start_run(url, max(1, min(8, int(body.get("tasks", 3)))), profiles or "P1,P2,P3,P4,P5", bool(body.get("agents", True)))
            return self._send({"id": run_id})
        if len(parts) == 4 and parts[:2] == ["api", "runs"] and parts[3] == "stop" and RUN_ID.match(parts[2]):
            return self._send({"stopped": stop_run(parts[2])})
        return self._send({"error": "not found"}, 404)


def serve_dashboard(port: int = 8800, open_browser: bool = True) -> None:
    RUNS.mkdir(exist_ok=True)
    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}/"
    print(f"Dashboard: {url}  (Ctrl+C to stop)")
    if open_browser:
        try:
            webbrowser.open(url)
        except Exception:
            pass
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.shutdown()
