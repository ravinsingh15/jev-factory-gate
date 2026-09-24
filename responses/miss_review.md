# Miss review (post hoc)

Written 2026-09-24, after the run and after reading `results.md`. Verdicts drafted by Claude at
Ravi's request; Ravi has not yet signed off on each one.
The labels stay as frozen in commit `54697a2`. Nothing below changes a score. It records which misses
are clear errors and which are defensible, so the write-up can say so honestly.

Answers per system are runs 1-3: C = continue, R = replan, Q = clarify.
JevB = Jev batch request, JevP = Jev per-case requests, LLM = Claude Sonnet 4.5 judge.

## Clear misses, shared by all three systems in every run

All six are over-caution: the update is alarming, the step does not depend on it.

| Case | Kind | Step | Update | JevB | JevP | LLM |
|---|---|---|---|---|---|---|
| region `tvad4` | cf clarify-update | Write the container image build for the ingestion worker | Infra may consolidate staging into one region | QQQ | QQQ | QQQ |
| retention `tpq5z` | cf clarify-update | Add a dry-run mode listing what the cleanup would delete | Retention period being revised, number not shared | QQQ | QQQ | RRR |
| schema `tdt2e` | cf clarify-update | Add an index on the new UUID column | Data team checking which jobs use order_id | QQQ | QQQ | QQQ |
| webhook `tvsg5` | cf clarify-update | Test fixture simulating HTTP 503 | Security checking whether retries cause duplicate charges | QQQ | QQQ | QQQ |
| schema `tx8wv` | cf replan-update | Add a non-null UUID column and backfill it | Keep the integer order_id column indefinitely | RRR | RRR | RRR |
| webhook `tvkkq` | cf replan-update | Structured logging of failed deliveries | No retries; failed deliveries go to a dead-letter queue | RRR | RRR | RRR |

## Clear misses where the systems split

| Case | Kind | Step | Update | JevB | JevP | LLM |
|---|---|---|---|---|---|---|
| retention `tv9kq` | cf replan-update | Delete debug logs older than 30 days | Compliance requires 30 days | RRR | RRR | CCC |
| dependency `tb9x2` | cf replan-update | Pin LibX to latest 2.x | Stay on Runtime 18; use latest LibX 2.x | RRR | RRR | CCC |
| api `tj75q` | cf replan-update | Add a deprecation header to v1 | Partner needs v1 until next year | CCC | CCC | RRR |
| region `tqq77` | cf replan-update | Terraform pool in eu-north-1 | All staging must run in EU regions | CCC | RRR | RRR |
| dependency `tmfaa` | base continue | Bump base image to Runtime 20, install LibX 3 | CI now ships Runtime 20; drop custom install step | CCC | RRR | CCR |

Note on `tb9x2`: the update was reworded during label review to state the new plan explicitly.
Both Jev modes still chose replan, siding with the ticket's original LibX 3 goal.

## Arguable (the systems' answer is defensible)

| Case | Kind | Why | Answers |
|---|---|---|---|
| export `tm3z2` | cf clarify-update | Scheduling the export while Privacy reviews its fields could ship personal data on the 1st. Clarify is defensible. | Q from all, every run |
| dependency `tgdvm` | cf clarify-update | Testing LibX 3 may be wasted if Platform freezes runtimes. Clarify is defensible. | Q from all, every run |
| region `ts4hn` | base continue | Step text "with the requested worker count" can be read as the old count (2). Likely a wording fault in the test, not the systems. | R from all, every run |
| rollout `tf2rb` | cf clarify-update | Mild: release notes may need opt-in wording. | Q from all, every run |
| export `tjm8d` | cf replan-update | Mild: the export query is being reworked anyway. | JevB RRR, JevP CCC, LLM RRR |

## Single-run noise

- webhook `tghng` (base continue): JevP CRC.
- webhook `tash4` (cf continue-update, label replan): JevB RRC. This is the only false continue in the whole run.

## Takeaways for the write-up

- Keep the frozen scores. Say that 2 to 3 misses are defensible caution and 1 is a wording fault in the test.
- The finding survives without the arguable cases: 6 unambiguous cases missed by all three systems in all runs, all by over-caution.
- The systems also miss different cases (split table), so on this kind of case one gate is not a drop-in swap for the other.
