# Factory gate results

48 cases: 24 base, 24 counterfactual. Labels: clarify 8, replan 16, continue 24

| System | All /48 | Base /24 | Counterfactual /24 | Gate binary /48 | False continues |
|---|---|---|---|---|---|
| always_continue | 24 | 8 | 16 | 24 | 24 |
| old_regex_update_only | 24 | 13 | 11 | 24 | 19 |
| jev-run-1 | 35 | 23 | 12 | 35 | 0 |
| jev-run-2 | 35 | 23 | 12 | 35 | 0 |
| jev-run-3 | 34 | 23 | 11 | 34 | 1 |
| jev-percase-run-1 | 34 | 22 | 12 | 34 | 0 |
| jev-percase-run-2 | 34 | 21 | 13 | 34 | 0 |
| jev-percase-run-3 | 34 | 22 | 12 | 34 | 0 |
| llm-run-1 | 35 | 23 | 12 | 35 | 0 |
| llm-run-2 | 35 | 23 | 12 | 35 | 0 |
| llm-run-3 | 34 | 22 | 12 | 34 | 0 |
| any update-only method (ceiling) | 24 | | | | |

## Stability and agreement

- jev_batch: choices identical across 3 runs on 47/48 cases
- jev_percase: choices identical across 3 runs on 46/48 cases
- llm: choices identical across 3 runs on 47/48 cases

**jev_batch vs llm** (run 1 each): agree 43/48, Cohen's kappa 0.836
- `tv9kq` cf_replan_update_continue: label continue, jev_batch replan, llm continue. Step: Write the cleanup job that deletes debug logs older than 30 days. Update: Compliance now requires keeping debug logs for 30 days.
- `tb9x2` cf_replan_update_continue: label continue, jev_batch replan, llm continue. Step: Pin LibX to the latest 2.x release, which supports Runtime 18. Update: Platform team: this service must stay on Runtime 18 this quarter; use the latest LibX 2.x until then.
- `tqq77` cf_replan_update_continue: label continue, jev_batch continue, llm replan. Step: Write the Terraform for the staging worker pool in eu-north-1 with the requested worker count. Update: New policy: all staging workloads must run in EU regions.
- `tj75q` cf_replan_update_continue: label continue, jev_batch continue, llm replan. Step: Add a deprecation warning header to v1 /users responses. Update: The partner integration still calls v1 and has to keep working until next year.
- `tpq5z` cf_clarify_update_continue: label continue, jev_batch clarify, llm replan. Step: Add a dry-run mode that lists which logs the cleanup would delete. Update: Compliance is revising the retention period; the new number has not been shared.

**jev_percase vs llm** (run 1 each): agree 42/48, Cohen's kappa 0.802
- `tv9kq` cf_replan_update_continue: label continue, jev_percase replan, llm continue. Step: Write the cleanup job that deletes debug logs older than 30 days. Update: Compliance now requires keeping debug logs for 30 days.
- `tb9x2` cf_replan_update_continue: label continue, jev_percase replan, llm continue. Step: Pin LibX to the latest 2.x release, which supports Runtime 18. Update: Platform team: this service must stay on Runtime 18 this quarter; use the latest LibX 2.x until then.
- `tjm8d` cf_replan_update_continue: label continue, jev_percase continue, llm replan. Step: Add a per-region order count column to the export query. Update: The partner export must no longer contain any personal data.
- `tj75q` cf_replan_update_continue: label continue, jev_percase continue, llm replan. Step: Add a deprecation warning header to v1 /users responses. Update: The partner integration still calls v1 and has to keep working until next year.
- `tmfaa` base_continue: label continue, jev_percase replan, llm continue. Step: Bump the service base image to Runtime 20 and install LibX 3. Update: CI runners now ship Runtime 20, so drop the custom runtime install step from the pipeline.
- `tpq5z` cf_clarify_update_continue: label continue, jev_percase clarify, llm replan. Step: Add a dry-run mode that lists which logs the cleanup would delete. Update: Compliance is revising the retention period; the new number has not been shared.

**jev_batch vs jev_percase** (run 1 each): agree 45/48, Cohen's kappa 0.902
- `tqq77` cf_replan_update_continue: label continue, jev_batch continue, jev_percase replan. Step: Write the Terraform for the staging worker pool in eu-north-1 with the requested worker count. Update: New policy: all staging workloads must run in EU regions.
- `tjm8d` cf_replan_update_continue: label continue, jev_batch replan, jev_percase continue. Step: Add a per-region order count column to the export query. Update: The partner export must no longer contain any personal data.
- `tmfaa` base_continue: label continue, jev_batch continue, jev_percase replan. Step: Bump the service base image to Runtime 20 and install LibX 3. Update: CI runners now ship Runtime 20, so drop the custom runtime install step from the pipeline.

## Cost and time

- Jev batch (jev-1.13.0): reported evaluation_time_ms per 48-case request n/a (undocumented field, not end-to-end). List-price estimate $0.000589 per 48 cases.
- Jev per case (jev-1.13.0): client wall-clock per call p50 625 ms, p95 736 ms over 144 calls. List-price estimate $0.001064 per 48 cases.
- LLM judge (anthropic/claude-sonnet-4-5 (via LiteLLM proxy)): client wall-clock per call p50 3180 ms, p95 5125 ms over 144 calls. LiteLLM cost $0.0000 per 48 cases (144 calls without cost data).

Only 'Jev per case' vs 'LLM judge' latency is like for like (both isolated calls, client wall-clock, same machine). Jev prices are list-price estimates, not observed charges.

## Predeclared criteria (see PROTOCOL.md)

**jev_batch**
- C1 counterfactual >= 21/24 every run: FAIL
- C2 overall >= 43/48 every run: FAIL
- C3 at most 1 false continue per run: PASS

**jev_percase**
- C1 counterfactual >= 21/24 every run: FAIL
- C2 overall >= 43/48 every run: FAIL
- C3 at most 1 false continue per run: PASS


## Addendum: judge model and observed cost (added after scoring, 2026-09-24)

- Model: `anthropic/claude-sonnet-4-5` via a LiteLLM proxy, no reasoning effort (live model-info check the same day).
- Observed cost: the judge key's LiteLLM spend went from $0.00 to $0.30636 over this run, which is $0.1021 per 48 cases. This matches the tokens (38,115 in, 12,801 out at $3/$15 per M) to the cent, so no other traffic hit the key during the run. The "$0.0000" above is local LiteLLM failing to price the alias.
- Jev costs above are list-price estimates, not observed charges.
