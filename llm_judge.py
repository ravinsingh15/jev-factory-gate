"""LLM judge: the same 48 cases through LiteLLM, one isolated call per case.

Normally called by run_all.py. Standalone:
    pip install litellm
    python3 llm_judge.py --runs 3            # reads JUDGE_MODEL etc. from .env or the environment

Writes <out>/llm-run-N.jsonl: {cid, label, raw, latency_ms, input_tokens, output_tokens, cost_usd, model}
latency_ms is client wall-clock per call, network included.
"""
import argparse, json, os, random, re, time
from pathlib import Path

HERE = Path(__file__).parent
LABELS = ("continue", "replan", "clarify")


def messages(judge, case):
    crit = "\n".join(f"- {k}: {v}" for k, v in judge["criteria"].items())
    system = (judge["instructions"] + "\n\nAnswer with exactly one label:\n" + crit +
              '\n\nReply with JSON only: {"label": "continue" | "replan" | "clarify"}')
    return [{"role": "system", "content": system},
            {"role": "user", "content": json.dumps(case, ensure_ascii=False)}]


def parse(text):
    try:
        lab = json.loads(re.search(r"\{.*\}", text, re.S).group(0))["label"].strip().lower()
    except Exception:
        found = [l for l in LABELS if re.search(rf"\b{l}\b", text.lower())]
        lab = found[0] if len(found) == 1 else None
    return lab if lab in LABELS else None


def call_real(model, msgs, extra):
    import litellm
    kw = dict(model=model, messages=msgs, max_tokens=int(os.getenv("JUDGE_MAX_TOKENS", "50")), **extra)
    for attempt in range(4):
        try:
            t0 = time.perf_counter()
            try:
                resp = litellm.completion(temperature=0, **kw)
            except litellm.exceptions.BadRequestError:
                t0 = time.perf_counter()
                resp = litellm.completion(**kw)  # some models reject temperature
            ms = (time.perf_counter() - t0) * 1000
            break
        except (litellm.exceptions.RateLimitError, litellm.exceptions.APIConnectionError,
                litellm.exceptions.ServiceUnavailableError, litellm.exceptions.InternalServerError):
            if attempt == 3:
                raise
            time.sleep(2 ** attempt * 2)
    try:
        cost = litellm.completion_cost(completion_response=resp)
    except Exception:
        cost = None
    return (resp.choices[0].message.content or "", ms, resp.usage.prompt_tokens,
            resp.usage.completion_tokens, cost, resp.model)


def call_mock(cid, rng, key):
    lab = key[cid]["label"] if rng.random() > 0.12 else rng.choice(LABELS)
    return json.dumps({"label": lab}), rng.uniform(400, 1800), 320, 8, 0.0005, "MOCK-LLM"


def run_llm(runs=3, limit=0, out_dir=HERE / "responses", mock=False):
    judge = json.loads((HERE / "judge_cases.json").read_text())
    key = json.loads((HERE / "answer_key.json").read_text())
    items = list(judge["cases"].items())[: limit or None]
    out_dir.mkdir(parents=True, exist_ok=True)
    model = os.getenv("JUDGE_MODEL")
    if not mock and not model:
        raise SystemExit("JUDGE_MODEL is not set (put it in .env)")
    extra = {k: v for k, v in {"api_base": os.getenv("JUDGE_API_BASE"),
                               "api_key": os.getenv("JUDGE_API_KEY")}.items() if v}
    rng = random.Random(7)
    # Minimum seconds between real calls, to stay under the key's rpm limit (judge key: 15 rpm).
    # The wait happens before t0, so latency_ms is unaffected.
    gap = 0.0 if mock else float(os.getenv("JUDGE_MIN_INTERVAL_S", "0"))
    last = 0.0
    for run in range(1, runs + 1):
        path = out_dir / f"llm-run-{run}.jsonl"
        with path.open("w") as f:
            for cid, case in items:
                if gap:
                    time.sleep(max(0.0, last + gap - time.monotonic()))
                    last = time.monotonic()
                text, ms, tin, tout, cost, used = (call_mock(cid, rng, key) if mock
                                                   else call_real(model, messages(judge, case), extra))
                f.write(json.dumps({"cid": cid, "label": parse(text), "raw": text, "latency_ms": round(ms, 1),
                                    "input_tokens": tin, "output_tokens": tout, "cost_usd": cost,
                                    "model": used}) + "\n")
        print(f"  llm run {run}: wrote {path.name}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--mock", action="store_true")
    a = ap.parse_args()
    from run_all import load_env
    load_env()
    run_llm(a.runs, a.limit, HERE / ("responses-mock" if a.mock else "responses"), a.mock)
