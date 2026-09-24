"""One command for the whole experiment, after you have reviewed the labels.

    cp .env.example .env        # fill in keys once; .env is git-ignored
    python3 run_all.py freeze   # hash the test set and commit it to the local git repo (does not push)
    python3 run_all.py run      # Jev batch + Jev per-case + LLM judge, 3 runs each, then score
    python3 run_all.py mock     # full pipeline with fake responses, no network, no cost

`run` refuses to start if the test set changed after `freeze`, and asks for a
typed confirmation before any billable call (skip with --yes for unattended runs).
Every raw response is kept, plus manifest.json (hashes, times, models, request IDs).
"""
import argparse, hashlib, json, os, random, subprocess, sys, time, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).parent
FROZEN = ["answer_key.json", "jev_request.json", "judge_cases.json"]
JEV_URL = "https://api.typesafe.ai/v1/systemone"
LABELS = ("continue", "replan", "clarify")


def load_env():
    p = HERE / ".env"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                v = v.strip().strip('"').strip("'")
                if v:
                    os.environ.setdefault(k.strip(), v)


def sha(name):
    return hashlib.sha256((HERE / name).read_bytes()).hexdigest()


def git(*args, check=True):
    return subprocess.run(["git", *args], cwd=HERE, capture_output=True, text=True, check=check).stdout.strip()


# ---------- freeze ----------
def freeze(a):
    # Commits locally only; this script never pushes.
    subprocess.run([sys.executable, "build.py"], cwd=HERE, check=True)
    if not (HERE / ".git").exists():
        git("init", "-b", "main")
    git("add", "-A")
    if git("status", "--porcelain"):
        git("commit", "-m", "Freeze factory-gate test set before any model run")
    print(f"Committed {git('rev-parse', 'HEAD')[:10]} locally. Not pushed.")


def check_frozen():
    freeze_txt = (HERE / "FREEZE.txt").read_text()
    changed = [n for n in FROZEN if f"{sha(n)}  {n}" not in freeze_txt]
    if changed:
        raise SystemExit(f"Test set differs from FREEZE.txt: {changed}. Re-run `freeze` first.")
    if (HERE / ".git").exists():
        dirty = git("status", "--porcelain", "--", *FROZEN, "FREEZE.txt", "build.py")
        if dirty:
            raise SystemExit("Frozen files have uncommitted changes. Run `freeze` first.")
        return git("rev-parse", "HEAD")
    print("WARNING: not a git repo; run `freeze` first.")
    return None


# ---------- Jev ----------
def jev_post(body, mock_rng=None, key=None):
    if mock_rng is not None:
        answers = {}
        for q in body["questions"]:
            cid = q if q in key else body["state"]["_cid"]
            ch = key[cid]["label"] if mock_rng.random() > 0.08 else mock_rng.choice(LABELS)
            p = {l: 0.02 for l in LABELS}; p[ch] = 0.96
            answers[q] = {"type": "choice", "choice": ch, "confidence": 0.94, "probabilities": p, "stats": {}}
        time.sleep(0.001)
        return {"model": "MOCK-JEV", "request_id": "mock", "evaluation_time_ms": mock_rng.uniform(20, 120),
                "usage": {"input_tokens": 250 * len(body["questions"]), "output_tokens": 0}, "answers": answers}
    req = urllib.request.Request(JEV_URL, data=json.dumps(body).encode(), method="POST", headers={
        "Authorization": f"Bearer {os.environ['TYPESAFE_API_KEY']}", "Content-Type": "application/json"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < 4:
                time.sleep(2 ** attempt); continue
            raise SystemExit(f"Jev HTTP {e.code}: {e.read()[:300]!r}")


def run_jev(runs, out, mock):
    batch = json.loads((HERE / "jev_request.json").read_text())
    judge = json.loads((HERE / "judge_cases.json").read_text())
    key = json.loads((HERE / "answer_key.json").read_text())
    rng = random.Random(3) if mock else None
    meta = []
    for run in range(1, runs + 1):
        t0 = time.perf_counter(); resp = jev_post(batch, rng, key); ms = (time.perf_counter() - t0) * 1000
        (out / f"jev-run-{run}.json").write_text(json.dumps(resp, indent=2) + "\n")
        meta.append({"kind": "jev_batch", "run": run, "wall_ms": round(ms, 1), "request_id": resp.get("request_id"),
                     "model": resp.get("model"), "at": datetime.now(timezone.utc).isoformat()})
        print(f"  jev batch run {run}: {ms:.0f} ms wall, model {resp.get('model')}")
    for run in range(1, runs + 1):
        with (out / f"jev-percase-run-{run}.jsonl").open("w") as f:
            for cid, case in judge["cases"].items():
                body = {"model": "jev-latest", "state": dict(case, **({"_cid": cid} if mock else {})),
                        "questions": {"verdict": {"type": "choice", "instructions": judge["instructions"],
                                                  "criteria": judge["criteria"]}}}
                t0 = time.perf_counter(); resp = jev_post(body, rng, key); ms = (time.perf_counter() - t0) * 1000
                a = resp["answers"]["verdict"]
                f.write(json.dumps({"cid": cid, "choice": a["choice"], "probabilities": a["probabilities"],
                                    "confidence": a["confidence"], "wall_ms": round(ms, 1),
                                    "evaluation_time_ms": resp.get("evaluation_time_ms"),
                                    "input_tokens": resp["usage"]["input_tokens"],
                                    "request_id": resp.get("request_id"), "model": resp.get("model")}) + "\n")
        print(f"  jev per-case run {run}: 48 calls")
    return meta


# ---------- run ----------
def run(a, mock=False):
    load_env()
    out = HERE / ("responses-mock" if mock else "responses")
    commit = None if mock else check_frozen()
    if not mock:
        missing = [k for k in ("TYPESAFE_API_KEY",) + (() if a.skip_llm else ("JUDGE_MODEL",)) if not os.getenv(k)]
        if missing:
            raise SystemExit(f"Missing in .env: {missing}")
        if a.skip_llm is False:
            try:
                import litellm  # noqa: F401
            except ImportError:
                raise SystemExit("pip install litellm")
        n_jev = a.runs * 49; n_llm = 0 if a.skip_llm else a.runs * 48
        print(f"About to make {n_jev} Jev calls (about 100k input tokens, under $0.01 at list price) "
              f"and {n_llm} calls to {os.getenv('JUDGE_MODEL')} (about {n_llm * 450 // 1000}k input tokens "
              "at your model's price). Billable.")
        if not a.yes and input("Type RUN to continue: ").strip() != "RUN":
            raise SystemExit("Stopped, nothing was called.")
        if any(out.glob("*-run-*")):
            raise SystemExit(f"{out.name}/ already has results; move them before a new run.")
    out.mkdir(exist_ok=True)
    started = datetime.now(timezone.utc).isoformat()
    meta = run_jev(a.runs, out, mock)
    if not a.skip_llm:
        from llm_judge import run_llm
        run_llm(a.runs, 0, out, mock)
    manifest = {"started": started, "finished": datetime.now(timezone.utc).isoformat(), "mock": mock,
                "git_commit": commit, "hashes": {n: sha(n) for n in FROZEN}, "runs": a.runs,
                "judge_model": None if mock else os.getenv("JUDGE_MODEL"),
                "judge_key": None if mock else os.getenv("JUDGE_KEY_LABEL"), "jev_batch_calls": meta}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    subprocess.run([sys.executable, "score.py", "--dir", out.name], cwd=HERE, check=True)
    print(f"\nDone. Results in {out.name}/results.md")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("freeze")
    for name in ("run", "mock"):
        p = sub.add_parser(name)
        p.add_argument("--runs", type=int, default=3)
        p.add_argument("--skip-llm", action="store_true")
        p.add_argument("--yes", action="store_true", help="skip the typed confirmation (unattended runs)")
    a = ap.parse_args()
    load_env()
    {"freeze": freeze, "run": run, "mock": lambda x: run(x, mock=True)}[a.cmd](a)
