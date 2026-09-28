#!/usr/bin/env python3
"""Serve the investor dashboard and regenerate thesis analysis on save.

Usage:
    python3 scripts/serve_dashboard.py
    python3 scripts/serve_dashboard.py --dry-run
    DASHBOARD_DRY_RUN=1 python3 scripts/serve_dashboard.py

Serves web/dashboard/ on http://localhost:8000 and exposes:

    GET  /api/status
    POST /api/tesi/<TICKER>          JSON body {orizzonte, motivo, indicatori, pesoPrevisto}
    GET  /api/tesi/<TICKER>/job      poll long-running rebuilds

POST writes data/theses_overrides/<TICKER>.json, runs build_theses --only then
build_dashboard_data (unless --dry-run / DASHBOARD_DRY_RUN), and returns
{ok, before, after} summaries via the job endpoint. Stdlib, Python 3.9.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
import threading
import traceback
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DASHBOARD = ROOT / "web" / "dashboard"
THESES_DIR = ROOT / "data" / "theses"
OVERRIDES_DIR = ROOT / "data" / "theses_overrides"
PY = sys.executable

DRY_RUN = False
JOBS: Dict[str, Dict[str, Any]] = {}
JOB_LOCK = threading.Lock()


def analysis_summary(raw: dict) -> dict:
    e = raw.get("esito") or {}
    d = raw.get("decisione") or {}
    inds = []
    for i in e.get("indicatori") or []:
        if isinstance(i, dict):
            inds.append({"nome": i.get("nome"), "stato": i.get("stato")})
    dec = None
    if d:
        dec = {"azione": d.get("azione"), "motivazione": d.get("motivazione")}
    return {
        "status": e.get("stato"),
        "sintesi": e.get("sintesi"),
        "indicatori": inds,
        "decisione": dec,
    }


def azienda_payload(raw: dict) -> dict:
    """Fields the dashboard merges onto DEMO_DATA.aziende[t]."""
    out = {k: v for k, v in raw.items() if k not in ("debug", "notizie_indicatori")}
    return out


def load_thesis(ticker: str) -> dict:
    p = THESES_DIR / f"{ticker}.json"
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def write_override(ticker: str, body: dict) -> None:
    OVERRIDES_DIR.mkdir(parents=True, exist_ok=True)
    payload = {
        "orizzonte": body.get("orizzonte") or "",
        "motivo": body.get("motivo") or "",
        "indicatori": list(body.get("indicatori") or []),
        "pesoPrevisto": body.get("pesoPrevisto", None),
    }
    (OVERRIDES_DIR / f"{ticker}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    )


def run_cmd(args: list, timeout: int = 900) -> str:
    proc = subprocess.run(
        args,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-40:]
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(args)}\n"
            + "\n".join(tail)
        )
    return proc.stdout or ""


def dry_run_after(before_raw: dict, body: dict) -> dict:
    after = copy.deepcopy(before_raw) if before_raw else {
        "esito": {"stato": "insufficiente", "sintesi": "", "indicatori": []},
        "decisione": None,
    }
    peso = body.get("pesoPrevisto", None)
    if peso == "":
        peso = None
    elif peso is not None:
        try:
            peso = float(peso)
        except (TypeError, ValueError):
            peso = None
    after["tesi_usata"] = {
        "motivo": body.get("motivo") or "",
        "indicatori": list(body.get("indicatori") or []),
        "orizzonte": body.get("orizzonte") or "",
        "pesoPrevisto": peso,
    }
    dbg = dict(after.get("debug") or {})
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        from build_theses import thesis_fingerprint  # noqa: WPS433
        dbg["thesis_fp"] = thesis_fingerprint(after["tesi_usata"])
    except Exception:
        pass
    after["debug"] = dbg
    return after


def execute_rebuild(ticker: str, body: dict) -> dict:
    before_raw = load_thesis(ticker)
    before = analysis_summary(before_raw)
    write_override(ticker, body)

    if DRY_RUN:
        after_raw = dry_run_after(before_raw, body)
        return {
            "ok": True,
            "dry_run": True,
            "before": before,
            "after": analysis_summary(after_raw),
            "azienda": azienda_payload(after_raw),
        }

    run_cmd([PY, str(ROOT / "scripts" / "build_theses.py"), "--only", ticker])
    run_cmd([PY, str(ROOT / "scripts" / "build_dashboard_data.py")])
    after_raw = load_thesis(ticker)
    return {
        "ok": True,
        "dry_run": False,
        "before": before,
        "after": analysis_summary(after_raw),
        "azienda": azienda_payload(after_raw),
    }


def start_job(ticker: str, body: dict) -> None:
    with JOB_LOCK:
        JOBS[ticker] = {"status": "running", "result": None}

    def worker() -> None:
        try:
            result = execute_rebuild(ticker, body)
            with JOB_LOCK:
                JOBS[ticker] = {"status": "done", "result": result}
        except Exception as e:
            err = str(e)
            tb = traceback.format_exc()
            with JOB_LOCK:
                JOBS[ticker] = {
                    "status": "error",
                    "result": {
                        "ok": False,
                        "error": err,
                        "stderr": tb[-2000:],
                    },
                }

    threading.Thread(target=worker, daemon=True).start()


def job_payload(ticker: str) -> dict:
    with JOB_LOCK:
        job = JOBS.get(ticker)
    if not job:
        return {"status": "idle"}
    if job["status"] == "running":
        return {"status": "running"}
    result = job.get("result") or {}
    out = {"status": job["status"], **result}
    return out


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        sys.stderr.write("[%s] %s\n" % (self.log_date_time_string(), fmt % args))

    def _json(self, code: int, payload: dict) -> None:
        raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(raw)

    def _read_json(self) -> Optional[dict]:
        n = int(self.headers.get("Content-Length") or 0)
        if n <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            self._json(400, {"ok": False, "error": f"JSON non valido: {e}"})
            return None

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path == "/api/status":
            self._json(200, {
                "ok": True,
                "dry_run": DRY_RUN,
                "serve": True,
                "ricalcolo": True,
            })
            return
        if path.startswith("/api/tesi/") and path.endswith("/job"):
            parts = path.strip("/").split("/")
            # api / tesi / TICKER / job
            if len(parts) == 4 and parts[0] == "api" and parts[1] == "tesi" and parts[3] == "job":
                ticker = parts[2].upper()
                self._json(200, job_payload(ticker))
                return
            self._json(404, {"ok": False, "error": "Not found"})
            return
        if path.startswith("/api/"):
            self._json(404, {"ok": False, "error": "Not found"})
            return
        super().do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if not path.startswith("/api/tesi/"):
            self._json(404, {"ok": False, "error": "Not found"})
            return
        parts = path.strip("/").split("/")
        if len(parts) != 3 or parts[0] != "api" or parts[1] != "tesi":
            self._json(404, {"ok": False, "error": "Not found"})
            return
        ticker = parts[2].upper()
        if not ticker.isalnum():
            self._json(400, {"ok": False, "error": "Ticker non valido"})
            return
        body = self._read_json()
        if body is None:
            return
        if not isinstance(body.get("motivo", ""), str):
            self._json(400, {"ok": False, "error": "Campo motivo richiesto"})
            return
        thesis_path = THESES_DIR / f"{ticker}.json"
        demo_ok = True
        try:
            # Allow any ticker that exists in data.js or already has a thesis cache
            sys.path.insert(0, str(ROOT / "scripts"))
            from build_theses import load_demo  # noqa: WPS433
            demo = load_demo()
            demo_ok = ticker in demo.get("aziende", {})
        except Exception:
            demo_ok = thesis_path.is_file()
        if not demo_ok and not thesis_path.is_file():
            self._json(404, {"ok": False, "error": f"Ticker sconosciuto: {ticker}"})
            return

        with JOB_LOCK:
            cur = JOBS.get(ticker)
            if cur and cur.get("status") == "running":
                self._json(409, {"ok": False, "error": "Ricalcolo già in corso", "queued": False})
                return

        start_job(ticker, body)
        self._json(202, {"ok": True, "queued": True, "ticker": ticker, "dry_run": DRY_RUN})


def main() -> None:
    global DRY_RUN
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip build_theses/Gemini; update tesi_usata only for UI testing",
    )
    args = ap.parse_args()
    DRY_RUN = bool(args.dry_run or os.environ.get("DASHBOARD_DRY_RUN") == "1")

    if not DASHBOARD.is_dir():
        sys.exit(f"Dashboard folder missing: {DASHBOARD}")

    httpd = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    mode = "dry-run" if DRY_RUN else "live"
    print(
        f"Serving {DASHBOARD.relative_to(ROOT)} at http://127.0.0.1:{args.port}/ "
        f"({mode})",
        flush=True,
    )
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)


if __name__ == "__main__":
    main()
