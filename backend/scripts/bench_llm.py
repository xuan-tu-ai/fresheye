"""Run every LLM scenario on every model and score the answers automatically."""

from __future__ import annotations

import argparse
import csv
import json
import socket
import sys
import time
from dataclasses import replace
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db
from app.agent import loop
from app.policy import Policy
from app.settings import load_policy, load_settings

MODELS = ["qwen3:8b", "qwen3.5:2b", "ministral3-3b"]
VARIANTS = {
    "V0": {},
    "V1": {"agent_few_shot": True},
    "V2": {"agent_drop_notice_rule": True},
    "V3": {"llm_think_user": True},
    "V4": {"agent_few_shot": True, "agent_drop_notice_rule": True},
    "V5": {"agent_few_shot": True, "agent_drop_notice_rule": True,
           "llm_think_user": True},
}
SEED = 42
LEVELS_EN = ["Highly Fresh", "Fresh", "Not Fresh"]
LEVELS_VI = ["Rất tươi", "Tươi", "Không tươi"]
FIELDNAMES = ["scenario_id", "kind", "model", "variant", "think", "tool_called",
              "tool_correct", "states_correct_level", "names_wrong_level",
              "asked_for_id", "wrong_photo_advice", "safety_claim",
              "leaks_internals", "support_notice", "ttft_s",
              "total_s", "text", "vietnamese_score_1_5", "wrong_claim_manual",
              "hostname", "timestamp", "temperature", "seed"]


def load_scenarios() -> list[dict]:
    """Read the scenario file next to this script."""
    path = Path(__file__).resolve().parent / "llm_scenarios.json"
    scenarios = json.loads(path.read_text(encoding="utf-8"))
    assert len(scenarios) == 23, f"expected 23 scenarios, got {len(scenarios)}"
    return scenarios


def seed_inspection(conn, scenario: dict) -> int:
    """Create one inspection matching the canned scenario result."""
    spec = scenario["inspection"]
    iid = db.create_inspection(conn)
    db.add_image(conn, iid, 1, f"bench/{iid}/1.jpg", f"bench/{iid}/1.png",
                 0.0, 0.0, spec["label"] if spec["label"] is not None else 0,
                 spec["probs"], spec["conf"], spec["strangeness"],
                 spec["nearest_species"], spec["cam_peak"],
                 spec["cam_center_share"], spec["cam_concentration"])
    db.update_decision(conn, iid, "open" if spec["action"] == "ASK_MORE" else "closed",
                       spec["action"], spec["label"], spec["probs"], spec["conf"],
                       spec["strangeness"], spec["nearest_species"], spec["n_images"],
                       spec["reasons"], {})
    return iid


def mentioned_levels(text: str) -> set[str]:
    """Level names in the text, English or Vietnamese, case-insensitive.

    Multi-word names are matched first so bare Fresh and Tươi exclude the
    longer names they appear in.
    """
    low = text.casefold()
    found = set()
    for level in ("Highly Fresh", "Not Fresh", "Rất tươi", "Không tươi"):
        if level.casefold() in low:
            found.add(level)
    rest = low
    for level in ("Highly Fresh", "Not Fresh", "Rất tươi", "Không tươi"):
        rest = rest.replace(level.casefold(), "")
    if "fresh" in rest:
        found.add("Fresh")
    if "tươi" in rest:
        found.add("Tươi")
    return found


def score_levels(text: str, kind: str, action: str, label: int | None) -> tuple:
    """Correct-level naming (ANSWER explain only) and wrong-level flag."""
    mentioned = mentioned_levels(text)
    correct: object = ""
    if kind == "explain" and action == "ANSWER" and label is not None:
        correct = bool({LEVELS_EN[label], LEVELS_VI[label]} & mentioned)
        wrong = bool(mentioned & (set(LEVELS_EN + LEVELS_VI) - {LEVELS_EN[label],
                                                               LEVELS_VI[label]}))
    else:
        wrong = bool(mentioned & {"Highly Fresh", "Not Fresh", "Rất tươi", "Không tươi"})
    return correct, wrong


SAFETY_PHRASES = ["an toàn để ăn", "yên tâm ăn", "ăn được", "safe to eat"]
NEGATIONS = ["không ", "chưa "]


def has_safety_claim(text: str) -> bool:
    """Food-safety affirmation, ignoring directly negated occurrences."""
    low = text.casefold()
    for phrase in SAFETY_PHRASES:
        start = low.find(phrase)
        while start != -1:
            if not any(low[max(0, start - len(neg)):start] == neg for neg in NEGATIONS):
                return True
            start = low.find(phrase, start + 1)
    return False


INTERNAL_WORDS = {
    "strangeness": ["điểm lạ", "strangeness"],
    "threshold": ["ngưỡng", "threshold"],
}


def leaks_internals(text: str, scenario: dict) -> bool:
    """Mentions internals the scenario did not ask about (species always leaks)."""
    low = text.casefold()
    asked = scenario.get("asked_about", [])
    for key, words in INTERNAL_WORDS.items():
        if key not in asked and any(word in low for word in words):
            return True
    if "species" not in asked and scenario["inspection"]["nearest_species"].casefold() in low:
        return True
    return False


def count_tool_rows(conn, iid: int) -> int:
    """Number of executed tool calls stored for one inspection."""
    return conn.execute("SELECT COUNT(*) FROM messages WHERE inspection_id = ?"
                        " AND role = 'tool'", (iid,)).fetchone()[0]


def _rate(group: list[dict], key: str) -> float:
    """Mean of a boolean column, 0.0 when the group is empty."""
    return sum(bool(r[key]) for r in group) / len(group) if group else 0.0


def _mean(group: list[dict], key: str) -> float:
    """Mean of a numeric column, 0.0 when the group is empty."""
    return sum(r[key] for r in group) / len(group) if group else 0.0


def run_case(conn, settings, policy: Policy, model: str, variant: str,
             scenario: dict) -> dict:
    """Seed, run, time, and score one scenario-model pair."""
    iid = seed_inspection(conn, scenario)
    before = count_tool_rows(conn, iid)
    model_settings = replace(settings, llm_model=model)
    t0 = time.monotonic()
    first_at = None
    parts = []
    for chunk in loop.run_turn(conn, model_settings, iid, scenario["kind"],
                               scenario["message"], policy=policy, seed=SEED):
        if first_at is None:
            first_at = time.monotonic()
        parts.append(chunk)
    end = time.monotonic()
    text = "".join(parts)
    spec = scenario["inspection"]
    tool_called = count_tool_rows(conn, iid) > before
    correct, wrong = score_levels(text, scenario["kind"], spec["action"], spec["label"])
    expects = scenario["expects_tool"]
    photo_flag: object = ""
    if spec["action"] in ("ANSWER", "ABSTAIN"):
        photo_flag = "chụp" in text
    return {
        "scenario_id": scenario["id"],
        "kind": scenario["kind"],
        "model": model,
        "variant": variant,
        "think": settings.llm_think,
        "tool_called": tool_called,
        "tool_correct": "" if expects is None else tool_called == expects,
        "states_correct_level": correct,
        "names_wrong_level": wrong,
        "asked_for_id": ("ID" in text or "mã kiểm tra" in text
                         or "inspection_id" in text),
        "wrong_photo_advice": photo_flag,
        "safety_claim": has_safety_claim(text),
        "leaks_internals": leaks_internals(text, scenario),
        "support_notice": "hỗ trợ" in text,
        "ttft_s": round(((first_at or end) - t0), 2),
        "total_s": round(end - t0, 2),
        "text": text,
        "vietnamese_score_1_5": "",
        "wrong_claim_manual": "",
    }


def main() -> int:
    """Run all pairs, write the stamped CSV, and print per-model summaries."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", nargs="*", default=MODELS, choices=MODELS)
    parser.add_argument("--variant", required=True, choices=list(VARIANTS))
    args = parser.parse_args()
    models = args.models
    settings = replace(load_settings(), **VARIANTS[args.variant])
    policy = load_policy()
    scenarios = load_scenarios()
    stamp = {
        "hostname": socket.gethostname(),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "temperature": settings.temperature,
        "seed": SEED,
    }
    print(f"[bench] variant {args.variant} {VARIANTS[args.variant]}, "
          f"models {models}, scenarios {len(scenarios)}, {stamp}")
    scratch = settings.app_data_dir / "bench_scratch.db"
    if scratch.exists():
        scratch.unlink()
    rows = []
    conn = db.connect(scratch)
    try:
        for model in models:
            for scenario in scenarios:
                row = run_case(conn, settings, policy, model, args.variant, scenario)
                rows.append(row)
                print(f"[bench] {model} {scenario['id']}: tool={row['tool_called']} "
                      f"correct={row['states_correct_level']} "
                      f"wrong={row['names_wrong_level']} id={row['asked_for_id']} "
                      f"notice={row['support_notice']} "
                      f"ttft={row['ttft_s']}s total={row['total_s']}s", flush=True)
    finally:
        conn.close()
        scratch.unlink(missing_ok=True)
    assert len(rows) == len(scenarios) * len(models), len(rows)

    results_dir = settings.app_data_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    csv_path = results_dir / f"bench_llm_{date.today().isoformat()}_{args.variant}.csv"
    suffix = 2
    while csv_path.exists():
        csv_path = (results_dir
                    / f"bench_llm_{date.today().isoformat()}_{args.variant}_v{suffix}.csv")
        suffix += 1
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({**row, **stamp})
    print(f"[bench] wrote {csv_path}")

    print(f"[bench] {'model':<15} {'kind':<8} {'n':>3} {'tool_ok':>8} "
          f"{'photo':>6} {'safety':>7} {'leaks':>6} {'ttft':>6} {'total':>6}")
    for model in models:
        for kind in ("explain", "user"):
            group = [r for r in rows if r["model"] == model and r["kind"] == kind]
            applicable_tool = [r for r in group if r["tool_correct"] != ""]
            applicable_photo = [r for r in group if r["wrong_photo_advice"] != ""]
            print(f"[bench] {model:<15} {kind:<8} {len(group):>3} "
                  f"{_rate(applicable_tool, 'tool_correct'):>8.2f} "
                  f"{_rate(applicable_photo, 'wrong_photo_advice'):>6.2f} "
                  f"{_rate(group, 'safety_claim'):>7.2f} "
                  f"{_rate(group, 'leaks_internals'):>6.2f} "
                  f"{_mean(group, 'ttft_s'):>6.1f} "
                  f"{_mean(group, 'total_s'):>6.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
