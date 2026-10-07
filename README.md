# Factory gate: does a fast gate read the pending step?

In an agentic delivery pipeline (Spec → Research → Coding → Review → Judge), a ticket gets edited while a run is in progress. Should the queued step still run?

| Label | What the pipeline does |
|---|---|
| `continue` | Run the step |
| `replan` | Send the ticket back to Spec |
| `clarify` | Pause and wait for a human |

I run a pipeline like this at work, so this is a real decision for me. I compared **Jev**, a fast gate model, with an **LLM judge** (Claude Sonnet 4.5) on it. All tickets in the test are invented.

## The test is built so the update text can't decide the label

Every update text appears **twice**, each time with a different pending step and a different correct label. A method that reads only the update can score at most **24/48** by construction. A regex that scored 24/24 on an earlier version of this test scores 24/48 here.

- 8 invented tickets × 6 cases = 48 (24 base, 24 counterfactual)
- Labels: 24 continue, 16 replan, 8 clarify
- **Pass criteria were set before any run.** The test set was frozen and hashed ([`FREEZE.txt`](FREEZE.txt)), and the runner refuses to start if the set has changed since the freeze.
- Each system ran 3 times. Every raw response is in [`responses/`](responses/).

Full method: [`PROTOCOL.md`](PROTOCOL.md).

## Results

| System | Overall /48 | Base /24 | Counterfactual /24 | False continues |
|---|---|---|---|---|
| Always `continue` (baseline) | 24 | 8 | 16 | 24 |
| Update-only regex (baseline) | 24 | 13 | 11 | 19 |
| Jev, batch request (3 runs) | 35 / 35 / 34 | 23 / 23 / 23 | 12 / 12 / 11 | 0 / 0 / 1 |
| Jev, per-case requests (3 runs) | 34 / 34 / 34 | 22 / 21 / 22 | 12 / 13 / 12 | 0 / 0 / 0 |
| LLM judge (3 runs) | 35 / 35 / 34 | 23 / 23 / 22 | 12 / 12 / 12 | 0 / 0 / 0 |

**Predeclared criteria for Jev:** C1 (counterfactual ≥ 21/24) **failed**. C2 (overall ≥ 43/48) **failed**. C3 (at most 1 false continue per run) **passed**.

Per-call latency, client wall-clock on the same machine: Jev p50 625 ms (p95 736 ms), LLM judge p50 3,180 ms (p95 5,125 ms).

Full tables, agreement and kappa: [`responses/results.md`](responses/results.md). Post-hoc analysis of every miss: [`responses/miss_review.md`](responses/miss_review.md).

## What I take from it

1. **Neither system reliably reads the pending step.** Both scored about 12/24 on the counterfactual cases, so on this set the gate's verdict mostly follows how alarming the update sounds.
2. **The errors lean safe.** There was 1 false continue in 432 answers. Six cases were missed by all three systems in every run, and all six were over-caution: they replanned or paused a step that didn't depend on the update.
3. **The two gates aren't interchangeable.** They agree on 42–43 of 48 cases (κ ≈ 0.80–0.84), but each misses some cases the other gets right.
4. **Jev matched the LLM judge on accuracy and answered about 5× faster per call** on this set.

## What this does *not* show

Production accuracy, calibration, determinism, or cost savings. The 48 cases are invented. The freeze commit was made locally and the repo was published after the run, so the timestamps aren't independent public proof.

## Reproduce

```bash
pip install litellm
cp .env.example .env        # API keys, judge model
python3 run_all.py mock     # full pipeline with fake data, no network, no cost
python3 run_all.py run      # real run; asks you to type RUN before any billable call
```
