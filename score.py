"""Score Jev and the LLM judge against the frozen labels, plus text-only baselines.

    python3 score.py [--dir responses]   -> prints a summary, writes <dir>/results.md + summary.json

Reads from <dir>:
    jev-run-N.json           one batched request (48 questions, shared state)
    jev-percase-run-N.jsonl  48 isolated requests, with client wall-clock latency
    llm-run-N.jsonl          LLM judge, one isolated call per case
Any subset works; the Playground-only path just has jev-run-N.json files.

JEV_PRICE_PER_M_INPUT: list price read on docs.typesafe.ai/models on 2026-09-24
($0.042 per million input tokens, output free). Re-check before quoting.
"""
import argparse, json, re, statistics
from collections import Counter
from pathlib import Path

HERE = Path(__file__).parent
LABELS = ["continue", "replan", "clarify"]
HOLD = {"replan", "clarify"}
JEV_PRICE_PER_M_INPUT = 0.042

key = json.loads((HERE / "answer_key.json").read_text())
cases = json.loads((HERE / "judge_cases.json").read_text())["cases"]
ids = list(key)
CF = [c for c in ids if key[c]["kind"].startswith("cf_")]
BASE = [c for c in ids if key[c]["kind"].startswith("base_")]


def jsonl(p):
    return {x["cid"]: x for x in (json.loads(l) for l in p.read_text().splitlines() if l.strip())}


def load(d):
    systems = {"jev_batch": [], "jev_percase": [], "llm": []}
    for p in sorted(d.glob("jev-run-*.json")):
        r = json.loads(p.read_text())
        systems["jev_batch"].append({
            "name": p.stem, "model": r.get("model"),
            "pred": {c: r["answers"][c]["choice"] for c in ids},
            "eval_ms": r.get("evaluation_time_ms"), "in_tok": r["usage"]["input_tokens"]})
    for p in sorted(d.glob("jev-percase-run-*.jsonl")):
        rows = jsonl(p)
        systems["jev_percase"].append({
            "name": p.stem, "model": rows[ids[0]].get("model"),
            "pred": {c: rows[c]["choice"] for c in ids},
            "lat": [rows[c]["wall_ms"] for c in ids],
            "in_tok": sum(rows[c]["input_tokens"] for c in ids)})
    for p in sorted(d.glob("llm-run-*.jsonl")):
        rows = jsonl(p)
        systems["llm"].append({
            "name": p.stem, "model": rows[ids[0]].get("model"),
            "pred": {c: rows[c]["label"] for c in ids},
            "lat": [rows[c]["latency_ms"] for c in ids],
            "cost": [rows[c]["cost_usd"] for c in ids]})
    return systems


def old_regex(update):  # post-hoc rule that scored 24/24 on the first test
    if re.search(r"\bnot (yet|been|said|in the)\b|\bno \w+ has been\b", update, re.I):
        return "clarify"
    if re.search(r"\b(must|only|preserve)\b", update, re.I):
        return "replan"
    return "continue"


def metrics(pred):
    ok = lambda sub: sum(pred[c] == key[c]["label"] for c in sub)
    conf = Counter((key[c]["label"], pred[c]) for c in ids)
    return {
        "all": ok(ids), "base": ok(BASE), "counterfactual": ok(CF),
        "gate_binary": sum((pred[c] in HOLD) == (key[c]["label"] in HOLD) for c in ids),
        "false_continue": [c for c in ids if key[c]["label"] in HOLD and pred[c] == "continue"],
        "false_hold": [c for c in ids if key[c]["label"] == "continue" and pred[c] in HOLD],
        "unparsed": [c for c in ids if pred[c] not in LABELS],
        "confusion": {f"{e}->{p}": n for (e, p), n in sorted(conf.items(), key=str)},
    }


def kappa(a, b):
    n = len(ids)
    po = sum(a[c] == b[c] for c in ids) / n
    ca, cb = Counter(a[c] for c in ids), Counter(b[c] for c in ids)
    pe = sum(ca[l] * cb[l] for l in set(ca) | set(cb)) / n ** 2
    return round((po - pe) / (1 - pe), 3) if pe < 1 else 1.0


def stable(runs):
    return sum(len({r["pred"][c] for r in runs}) == 1 for c in ids)


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(q * (len(xs) - 1))))]


def criteria(runs, out):
    return {"C1 counterfactual >= 21/24 every run": all(out[r["name"]]["counterfactual"] >= 21 for r in runs),
            "C2 overall >= 43/48 every run": all(out[r["name"]]["all"] >= 43 for r in runs),
            "C3 at most 1 false continue per run": all(len(out[r["name"]]["false_continue"]) <= 1 for r in runs)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="responses")
    d = HERE / ap.parse_args().dir
    S = load(d)
    out, md = {}, ["# Factory gate results", ""]
    md += [f"{len(ids)} cases: {len(BASE)} base, {len(CF)} counterfactual. Labels: "
           + ", ".join(f"{k} {v}" for k, v in Counter(key[c]['label'] for c in ids).items()), ""]

    groups = Counter((key[c]["sid"], key[c]["update_key"], key[c]["label"]) for c in ids)
    ceiling = sum(max(n for (s, u, _), n in groups.items() if (s, u) == g) for g in {(s, u) for s, u, _ in groups})
    rows = [("always_continue", {c: "continue" for c in ids}),
            ("old_regex_update_only", {c: old_regex(cases[c]["ticket_update"]) for c in ids})]
    for sysname in S:
        rows += [(r["name"], r["pred"]) for r in S[sysname]]

    md += ["| System | All /48 | Base /24 | Counterfactual /24 | Gate binary /48 | False continues |",
           "|---|---|---|---|---|---|"]
    for name, pred in rows:
        m = metrics(pred); out[name] = m
        md.append(f"| {name} | {m['all']} | {m['base']} | {m['counterfactual']} | {m['gate_binary']} | {len(m['false_continue'])} |")
    md += [f"| any update-only method (ceiling) | {ceiling} | | | | |", ""]

    md += ["## Stability and agreement", ""]
    for sysname, runs in S.items():
        if runs:
            md.append(f"- {sysname}: choices identical across {len(runs)} runs on {stable(runs)}/48 cases")
    pairs = [(a, b) for a, b in (("jev_batch", "llm"), ("jev_percase", "llm"), ("jev_batch", "jev_percase"))
             if S[a] and S[b]]
    for a, b in pairs:
        pa, pb = S[a][0]["pred"], S[b][0]["pred"]
        dis = [c for c in ids if pa[c] != pb[c]]
        out[f"{a}_vs_{b}"] = {"agree": 48 - len(dis), "kappa": kappa(pa, pb), "disagree": dis}
        md += ["", f"**{a} vs {b}** (run 1 each): agree {48 - len(dis)}/48, Cohen's kappa {kappa(pa, pb)}"]
        for c in dis:
            k = cases[c]
            md.append(f"- `{c}` {key[c]['kind']}: label {key[c]['label']}, {a} {pa[c]}, {b} {pb[c]}. "
                      f"Step: {k['pending_step']['action']} Update: {k['ticket_update']}")
    md.append("")

    md += ["## Cost and time", ""]
    if S["jev_batch"]:
        r = S["jev_batch"]; ev = [x["eval_ms"] for x in r if x["eval_ms"] is not None]
        tok = sum(x["in_tok"] for x in r) / len(r)
        md.append(f"- Jev batch ({r[0]['model']}): reported evaluation_time_ms per 48-case request "
                  + (f"min/median/max {min(ev):.1f}/{statistics.median(ev):.1f}/{max(ev):.1f}" if ev else "n/a")
                  + f" (undocumented field, not end-to-end). List-price estimate ${tok / 1e6 * JEV_PRICE_PER_M_INPUT:.6f} per 48 cases.")
    for sysname, label in (("jev_percase", "Jev per case"), ("llm", "LLM judge")):
        r = S[sysname]
        if not r:
            continue
        lat = [x for run in r for x in run["lat"]]
        line = (f"- {label} ({r[0]['model']}): client wall-clock per call p50 {pct(lat, .5):.0f} ms, "
                f"p95 {pct(lat, .95):.0f} ms over {len(lat)} calls.")
        if sysname == "jev_percase":
            tok = sum(x["in_tok"] for x in r) / len(r)
            line += f" List-price estimate ${tok / 1e6 * JEV_PRICE_PER_M_INPUT:.6f} per 48 cases."
        else:
            costs = [x for run in r for x in run["cost"] if x is not None]
            line += (f" LiteLLM cost ${sum(costs) / len(r):.4f} per 48 cases"
                     + ("" if len(costs) == len(lat) else f" ({len(lat) - len(costs)} calls without cost data)") + ".")
        md.append(line)
    md += ["", "Only 'Jev per case' vs 'LLM judge' latency is like for like (both isolated calls, client wall-clock, "
           "same machine). Jev prices are list-price estimates, not observed charges.", ""]

    md += ["## Predeclared criteria (see PROTOCOL.md)", ""]
    out["criteria"] = {}
    for sysname in ("jev_batch", "jev_percase"):
        if S[sysname]:
            res = criteria(S[sysname], out); out["criteria"][sysname] = res
            md += [f"**{sysname}**"] + [f"- {k}: {'PASS' if v else 'FAIL'}" for k, v in res.items()] + [""]
    (d / "results.md").write_text("\n".join(md) + "\n")
    (d / "summary.json").write_text(json.dumps(out, indent=2) + "\n")
    print("\n".join(md))


if __name__ == "__main__":
    main()
