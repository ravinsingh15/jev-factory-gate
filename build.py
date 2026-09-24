"""Build the factory-gate test set.

Edit SCENARIOS (labels included) during your label review, then run:
    python3 build.py
It writes: answer_key.json, jev_request.json, judge_cases.json, FREEZE.txt (hashes).
All tickets are invented. No real company code, tickets or data.
"""
import hashlib, json, random
from pathlib import Path

SEED = 20260924
HERE = Path(__file__).parent

# Each scenario: one ticket, three updates (u_c, u_r, u_q) and four pending steps.
#   A + u_c -> continue    A + u_r -> replan    A + u_q -> clarify      (base triple)
#   B + u_r -> continue    C + u_q -> continue  D + u_c -> replan       (counterfactuals)
# Counterfactuals reuse an update verbatim with a different pending step, so the
# update text alone can never decide the label.
SCENARIOS = [
    {
        "sid": "webhook",
        "ticket": "Make the payment webhook handler resilient: retry failed deliveries with exponential backoff, max 5 attempts.",
        "u_c": "Also emit a metric with the number of retry attempts per delivery.",
        "u_r": "Product decided there will be no retries in the handler; failed deliveries go to a dead-letter queue instead.",
        "u_q": "Security is checking whether handler retries can cause duplicate charges; waiting on their answer.",
        "A": ("Coding", "Implement exponential-backoff retry, max 5 attempts, inside the webhook handler."),
        "B": ("Coding", "Add structured logging of failed webhook deliveries with their event IDs."),
        "C": ("Coding", "Write a test fixture that simulates the webhook endpoint returning HTTP 503."),
        "D": ("Coding", "Remove the metrics client dependency from the webhook module."),
    },
    {
        "sid": "schema",
        "ticket": "Migrate the orders table from integer order_id to UUID. Dropping the integer column is approved once all reads use the UUID.",
        "u_c": "All read paths now use the UUID column; the reporting job was switched over yesterday.",
        "u_r": "Keep the integer order_id column indefinitely; the finance export still reads it.",
        "u_q": "The data team flagged a possible dependency on order_id and will confirm which jobs use it.",
        "A": ("Coding", "Write the migration that drops the integer order_id column."),
        "B": ("Coding", "Add a non-null UUID column to orders and backfill it."),
        "C": ("Coding", "Add an index on the new UUID column."),
        "D": ("Coding", "Change the reporting job to read the integer order_id column."),
    },
    {
        "sid": "region",
        "ticket": "Provision a staging worker pool of two workers for the ingestion service in us-east-1.",
        "u_c": "Make it four workers instead of two; the region stays the same.",
        "u_r": "New policy: all staging workloads must run in EU regions.",
        "u_q": "Infra may consolidate all staging into one region; the decision is expected Friday.",
        "A": ("Coding", "Write the Terraform for the staging worker pool in us-east-1 with the requested worker count."),
        "B": ("Coding", "Write the Terraform for the staging worker pool in eu-north-1 with the requested worker count."),
        "C": ("Coding", "Write the container image build for the ingestion worker."),
        "D": ("Coding", "Write the Terraform for a two-worker staging pool in us-east-1."),
    },
    {
        "sid": "rollout",
        "ticket": "Roll out the new search ranking to all tenants now that the pilot has passed.",
        "u_c": "Pilot metrics are final; attach them to the release notes.",
        "u_r": "Only internal tenants get the new ranking this sprint.",
        "u_q": "Legal is checking whether EU tenants need to opt in first; no answer yet.",
        "A": ("Deploy", "Set the search-ranking feature flag to 100% of tenants."),
        "B": ("Deploy", "Turn the search-ranking feature flag on for internal tenants."),
        "C": ("Docs", "Draft the release notes describing the ranking change."),
        "D": ("Docs", "Publish the release notes without any pilot metrics."),
    },
    {
        "sid": "api",
        "ticket": "Replace the v1 /users endpoint with v2. Removing v1 is approved.",
        "u_c": "The last v1 consumer, the mobile app, shipped its v2 migration today.",
        "u_r": "The partner integration still calls v1 and has to keep working until next year.",
        "u_q": "Some traffic to v1 still shows up in the logs; we are identifying the caller.",
        "A": ("Coding", "Delete the v1 /users route and its handler."),
        "B": ("Coding", "Add a deprecation warning header to v1 /users responses."),
        "C": ("Docs", "Write the OpenAPI documentation for v2 /users."),
        "D": ("Coding", "Add a new field to the v1 /users response for the mobile app."),
    },
    {
        "sid": "retention",
        "ticket": "Implement the approved 7-day retention for debug logs.",
        "u_c": "Run the cleanup nightly at 02:00 instead of hourly.",
        "u_r": "Compliance now requires keeping debug logs for 30 days.",
        "u_q": "Compliance is revising the retention period; the new number has not been shared.",
        "A": ("Coding", "Write the cleanup job that deletes debug logs older than 7 days."),
        "B": ("Coding", "Write the cleanup job that deletes debug logs older than 30 days."),
        "C": ("Coding", "Add a dry-run mode that lists which logs the cleanup would delete."),
        "D": ("Coding", "Set the cleanup job's schedule to run every hour."),
    },
    {
        "sid": "dependency",
        "ticket": "Upgrade the service to LibX 3, which needs Runtime 20. The runtime upgrade is approved.",
        "u_c": "CI runners now ship Runtime 20, so drop the custom runtime install step from the pipeline.",
        "u_r": "Platform team: this service must stay on Runtime 18 this quarter; use the latest LibX 2.x until then.",
        "u_q": "Platform may freeze runtime versions this quarter; they decide next week.",
        "A": ("Coding", "Bump the service base image to Runtime 20 and install LibX 3."),
        "B": ("Coding", "Pin LibX to the latest 2.x release, which supports Runtime 18."),
        "C": ("Research", "Run the existing test suite against LibX 3 in a local Runtime 20 container and record failures."),
        "D": ("Coding", "Add a CI step that downloads and installs Runtime 20 manually."),
    },
    {
        "sid": "export",
        "ticket": "Build the monthly partner export with customer name and email.",
        "u_c": "Name the output file partner_export_<yyyy-mm>.csv.",
        "u_r": "The partner export must no longer contain any personal data.",
        "u_q": "Privacy is reviewing which fields partners may receive; the list is not ready.",
        "A": ("Coding", "Add customer name and email columns to the export query."),
        "B": ("Coding", "Add a per-region order count column to the export query."),
        "C": ("Coding", "Schedule the export to run on the first day of each month."),
        "D": ("Coding", "Write the export output to a file named export.csv."),
    },
]

COMBOS = [  # (kind, step, update, label)
    ("base_continue", "A", "u_c", "continue"),
    ("base_replan", "A", "u_r", "replan"),
    ("base_clarify", "A", "u_q", "clarify"),
    ("cf_replan_update_continue", "B", "u_r", "continue"),
    ("cf_clarify_update_continue", "C", "u_q", "continue"),
    ("cf_continue_update_replan", "D", "u_c", "replan"),
]

INSTRUCTIONS = (
    "Evaluate only `cases.{cid}`. An automated software-delivery pipeline is about to run "
    "this case's pending_step for its ticket. Given the ticket and the ticket_update, is the "
    "pending_step still right to run exactly as written? Treat each case independently. "
    "Judge fit with the current requirements only, not permissions or code quality."
)
CRITERIA = {
    "continue": "The pending step is still consistent with the ticket as updated. The pipeline should run it.",
    "replan": "The update makes this pending step wrong as written, whatever any still-missing details turn out to be. The ticket should go back to planning.",
    "clarify": "Whether this pending step is still right depends on a decision or information that is not available yet. The pipeline should pause for a human.",
}


def build():
    rng = random.Random(SEED)
    rows = []
    for s in SCENARIOS:
        for kind, step, upd, label in COMBOS:
            stage, action = s[step]
            rows.append({
                "sid": s["sid"], "kind": kind, "step": step, "update_key": upd, "label": label,
                "case": {"ticket": s["ticket"],
                         "pending_step": {"stage": stage, "action": action},
                         "ticket_update": s[upd]},
            })
    rng.shuffle(rows)
    used = set()
    for r in rows:
        while True:
            cid = "t" + "".join(rng.choice("abcdefghjkmnpqrstuvwxyz23456789") for _ in range(4))
            if cid not in used:
                used.add(cid); r["cid"] = cid; break

    key = {r["cid"]: {k: r[k] for k in ("sid", "kind", "step", "update_key", "label")} for r in rows}
    state = {"cases": {r["cid"]: r["case"] for r in rows}}
    request = {
        "model": "jev-latest",
        "state": state,
        "questions": {r["cid"]: {"type": "choice",
                                 "instructions": INSTRUCTIONS.format(cid=r["cid"]),
                                 "criteria": dict(CRITERIA)} for r in rows},
    }
    judge = {"instructions": INSTRUCTIONS.replace("Evaluate only `cases.{cid}`. ", ""),
             "criteria": CRITERIA,
             "cases": {r["cid"]: r["case"] for r in rows}}

    out = {"answer_key.json": key, "jev_request.json": request, "judge_cases.json": judge}
    lines = []
    for name, obj in out.items():
        data = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
        (HERE / name).write_text(data)
        lines.append(f"{hashlib.sha256(data.encode()).hexdigest()}  {name}")
    (HERE / "FREEZE.txt").write_text(
        "SHA-256 of the frozen test set. Commit these files to a public repo or gist\n"
        "BEFORE the first run so the timestamp shows the labels came first.\n\n"
        + "\n".join(lines) + "\n")
    from collections import Counter
    print("cases:", len(rows), dict(Counter(r["label"] for r in rows)))
    print("kinds:", dict(Counter(r["kind"] for r in rows)))
    print("\n".join(lines))


if __name__ == "__main__":
    build()
