# Factory gate: does a fast gate read the pending step?

**Question.** In an agentic delivery pipeline (Spec, Research, Coding, Review, Judge), a ticket gets edited mid-run. Should the queued step still run?

| Label | Pipeline branch |
|---|---|
| continue | Run the step |
| replan | Send the ticket back to Spec |
| clarify | Pause and wait for a human |

**What's new versus the first test.** Every update text appears twice, with two different pending steps and two different labels. Any method that only reads the update scores at most 24/48 by construction. The regex that scored 24/24 last time scores 24/48 here.

**Set.** 8 invented tickets × 6 cases = 48.
- Base cases (24): the original step, with each of the three updates.
- Counterfactual cases (24): the same update text with a different step, so the label flips.
- Labels: 24 continue, 16 replan, 8 clarify.
- Order is shuffled and IDs are random (seed 20260924).

## Steps

**0. Review the labels yourself (about 15 min).** You're the independent human reviewer that the first test lacked. Read the cases in `build.py`. I'm least sure about these three:
- `dependency` B (pin LibX 2.x). Labelled continue. Reviewed: the replan update originally only said "stay on Runtime 18", so pinning 2.x invented a new goal. It now also says "use the latest LibX 2.x until then", matching how `region` and `retention` state the new value.
- `api` D (add a field to v1 for the mobile app). I labelled it replan, because the mobile app no longer uses v1. Reviewed: kept.
- `rollout` base clarify (EU opt-in check). Clarify, because a 100% rollout may or may not be allowed. Reviewed: kept.

Change any label you disagree with, then run `python3 build.py`.

**1. One-time setup.**
```
pip install litellm
cp .env.example .env      # TYPESAFE_API_KEY, JUDGE_MODEL, optional LiteLLM proxy base/key
python3 run_all.py mock   # rehearsal: whole pipeline with fake data, no network, no cost
```

**2. Freeze.** Run `python3 run_all.py freeze`. It rebuilds the set and commits it to a local git repo. Nothing is pushed: this experiment stays local. The local commit and the SHA-256 hashes in `FREEZE.txt` record the labels before any run, but they are not public proof. `.env` is git-ignored.

**3. Run.** Run `python3 run_all.py run`. It won't start if the test set has changed since the freeze, and it asks you to type RUN before any billable call. It then runs, 3 times each:
- a Jev batch request (48 questions in one request);
- Jev per-case requests (48 isolated calls);
- the LLM judge (48 isolated calls).

Every raw response is kept in `responses/`, along with `manifest.json` (commit, hashes, request IDs, times). Scoring then runs automatically, producing `responses/results.md`.

Why run Jev per case too: it gives a like-for-like comparison with the LLM judge (isolated calls, client wall-clock on the same machine). It also shows whether the shared state in the batch request affects the answers.

**No API key?** Paste `jev_request.json` into the Playground 3 times and save each response as `responses/jev-run-N.json`. Then run `python3 llm_judge.py --runs 3` and `python3 score.py`.

## Predeclared criteria (Jev, every run)

- **C1:** counterfactual cases ≥ 21/24. This is the main test: it shows the verdict depends on the pending step.
- **C2:** overall ≥ 43/48.
- **C3:** at most 1 false continue. A false continue means the label is replan or clarify but Jev said continue. It's the costly error for a gate.

The LLM judge comparison is descriptive: agreement, kappa, the disagreements, latency and cost. It has no pass/fail.

## What each outcome lets you say

| Result | Claim |
|---|---|
| C1 to C3 pass | "On 48 invented cases built so wording alone can't decide, Jev's verdict tracked the pending step" (quote the numbers) |
| Jev within 2 cases of the LLM on both subsets | "It matched my LLM judge on this set", plus the cost per 48 cases for each |
| C1 fails | "My gate keyed on the update wording", and show where. That's still a useful post. |
| Many false continues for either system | Lead with this. It's the governance point. |

## What you still can't claim

- Production accuracy.
- Calibration.
- Determinism.
- Savings.
- A latency ratio from anything other than the per-case wall-clock numbers. Jev's `evaluation_time_ms` is an undocumented batch field.
