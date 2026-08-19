#!/usr/bin/env python3
"""Automated runner for the skill trigger-eval set (evals/trigger-cases.json).

Two modes:

* Offline structural mode (default): validates the eval set itself (JSON
  syntax, unique ids, required fields, bool flags, referenced skill dirs,
  notes on negative cases) and reports the length distribution of every
  SKILL.md description. No network or credentials required; CI-friendly.
* LLM routing mode (--llm): collects every user-invocable skill in the
  repo as routing candidates, asks an OpenAI-compatible chat endpoint
  which skill each utterance should trigger, and scores the predictions
  against the expectations (positive top-1 hit rate, negative false
  trigger rate). Threshold failures exit 1.

Exit codes: 0 = pass, 1 = fail, 2 = LLM mode selected but the endpoint
environment variables (EVAL_LLM_BASE_URL / EVAL_LLM_API_KEY /
EVAL_LLM_MODEL) are not configured. Pure standard library; UTF-8.
"""

import argparse
import json
import os
import re
import statistics
import sys
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_THRESHOLD = 0.90
DEFAULT_TIMEOUT = 60
MIN_DESC_LEN = 50  # descriptions shorter than this trigger a warning
REQUIRED_FIELDS = ("id", "utterance", "expected_plugin", "expected_skill", "should_trigger")

SYSTEM_PROMPT = (
    "You are a skill router. Given a user utterance and a list of candidate "
    "skills, decide which single skill should be triggered. Reply with a JSON "
    'object only: {"skill": "<name>"} using one of the candidate skill names, '
    'or {"skill": null} when no candidate fits. Do not output any other text.'
)

USER_TEMPLATE = (
    "Candidate skills:\n{candidates}\n\n"
    "User utterance:\n{utterance}\n\n"
    "Which skill should be triggered? Answer with the JSON object only."
)


# -- SKILL.md scanning (frontmatter parsing stays dependency-free on purpose)

def parse_frontmatter(text):
    """Extract top-level keys from the YAML frontmatter of a SKILL.md file.

    Only plain scalars and block scalars (>- / > / |- / |) are supported,
    which covers the keys this runner needs (name, description,
    user-invocable). Nested blocks such as ``metadata:`` are ignored.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    meta, i, n = {}, 1, len(lines)
    key_re = re.compile(r"^([A-Za-z0-9_-]+):\s*(.*)$")
    while i < n and lines[i].strip() != "---":
        match = key_re.match(lines[i])
        if match:
            key, value = match.group(1), match.group(2).strip()
            if value in (">-", ">", "|-", "|"):
                # Block scalar: consume the following indented lines.
                block = []
                i += 1
                while i < n and (lines[i].startswith("  ") or lines[i].startswith("\t")):
                    block.append(lines[i].strip())
                    i += 1
                meta[key] = (" " if value.startswith(">") else "\n").join(block).strip()
                continue
            meta[key] = value.strip("'\"")
        i += 1
    return meta


def load_skills(repo_root):
    """Return one record per plugins/<plugin>/skills/<skill>/SKILL.md."""
    skills = []
    for path in sorted(repo_root.glob("plugins/*/skills/*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        meta = parse_frontmatter(text)
        description = meta.get("description", "")
        skills.append({
            "plugin": path.parents[2].name,
            "dir_name": path.parent.name,
            "name": meta.get("name") or path.parent.name,
            "description": description,
            "desc_len": len(description),
            # Library skills opt out of direct user invocation.
            "user_invocable": str(meta.get("user-invocable", "true")).lower() != "false",
            "path": str(path.relative_to(repo_root)),
        })
    return skills


# -- Offline structural validation of the eval set

def load_cases(repo_root):
    """Load trigger-cases.json; return (cases, structural_errors)."""
    cases_file = repo_root / "evals" / "trigger-cases.json"
    errors = []
    try:
        data = json.loads(cases_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [], [f"trigger-cases.json is not valid JSON: {exc}"]
    if not isinstance(data, dict) or "version" not in data:
        errors.append("top level must be an object with a 'version' field")
    cases = data.get("cases") if isinstance(data, dict) else None
    if not isinstance(cases, list):
        return [], errors + ["'cases' must be a list"]
    return cases, errors


def validate_cases(cases, repo_root):
    """Validate every case; return a list of structural error strings."""
    errors, seen_ids = [], set()
    for idx, case in enumerate(cases):
        if not isinstance(case, dict):
            errors.append(f"case #{idx}: must be a JSON object")
            continue
        where = case.get("id") if isinstance(case.get("id"), str) else f"#{idx}"
        for field in REQUIRED_FIELDS:
            if field not in case:
                errors.append(f"{where}: missing required field '{field}'")
        cid = case.get("id")
        if not isinstance(cid, str) or not cid:
            errors.append(f"case #{idx}: 'id' must be a non-empty string")
        elif cid in seen_ids:
            errors.append(f"{cid}: duplicate case id")
        else:
            seen_ids.add(cid)
        if not isinstance(case.get("utterance"), str) or not case.get("utterance", "").strip():
            errors.append(f"{where}: 'utterance' must be a non-empty string")
        should_trigger = case.get("should_trigger")
        if not isinstance(should_trigger, bool):
            errors.append(f"{where}: 'should_trigger' must be a boolean")
        plugin, skill = case.get("expected_plugin"), case.get("expected_skill")
        if plugin is not None and not isinstance(plugin, str):
            errors.append(f"{where}: 'expected_plugin' must be a string or null")
        if skill is not None and not isinstance(skill, str):
            errors.append(f"{where}: 'expected_skill' must be a string or null")
        if (plugin is None) != (skill is None):
            errors.append(f"{where}: expected_plugin and expected_skill must both be null or both be set")
        if should_trigger is False:
            if not isinstance(case.get("note"), str) or not case.get("note", "").strip():
                errors.append(f"{where}: negative case must carry a non-empty 'note'")
        if should_trigger is True and isinstance(plugin, str) and isinstance(skill, str):
            if not (repo_root / "plugins" / plugin / "skills" / skill).is_dir():
                errors.append(f"{where}: positive case references missing dir plugins/{plugin}/skills/{skill}")
    return errors


def description_report(skills):
    """Length distribution of all SKILL.md descriptions plus warnings."""
    lengths = [s["desc_len"] for s in skills]
    stats = {"count": len(lengths), "min": 0, "max": 0, "mean": 0.0, "median": 0.0}
    if lengths:
        stats.update(min=min(lengths), max=max(lengths),
                     mean=round(statistics.mean(lengths), 1),
                     median=statistics.median(lengths))
    warnings = []
    for s in skills:
        if not s["description"]:
            warnings.append({"skill": s["name"], "path": s["path"], "reason": "missing description"})
        elif s["desc_len"] < MIN_DESC_LEN:
            warnings.append({"skill": s["name"], "path": s["path"],
                             "reason": f"description too short ({s['desc_len']} chars < {MIN_DESC_LEN})"})
    return {"length_stats": stats, "warnings": warnings}


# -- LLM routing mode

def chat_completion(base_url, api_key, model, messages, timeout):
    """POST {base}/chat/completions with urllib; return the reply content."""
    url = base_url.rstrip("/") + "/chat/completions"
    payload = json.dumps({"model": model, "messages": messages, "temperature": 0}).encode("utf-8")
    request = urllib.request.Request(url, data=payload, method="POST", headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    })
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


def parse_router_response(content):
    """Extract the predicted skill name (or None) from the model reply."""
    match = re.search(r"\{[^{}]*\}", content or "", flags=re.DOTALL)
    if not match:
        raise ValueError("reply contains no JSON object")
    skill = json.loads(match.group(0)).get("skill")
    return None if skill in (None, "", "null") else str(skill)


def extract_traps(note, all_skill_names, expected_skill):
    """Trap skills of a negative case = skill names mentioned in its note,
    excluding the expected (correct) skill itself."""
    return sorted(n for n in all_skill_names if n != expected_skill and n in (note or ""))


def judge(case, predicted, all_skill_names):
    """Return True/False for a scored case (see evals/README.md criteria)."""
    if case["should_trigger"]:
        return predicted == case["expected_skill"]
    # Negative: no skill at all when expected is null, otherwise the trap
    # skills named in the note must not be triggered.
    if case.get("expected_skill") is None:
        return predicted is None
    traps = extract_traps(case.get("note"), all_skill_names, case["expected_skill"])
    return predicted is None or predicted not in traps


def run_llm_mode(cases, skills, args):
    """Route every case through the configured LLM and score the outcome."""
    base_url = os.environ.get("EVAL_LLM_BASE_URL", "").strip()
    api_key = os.environ.get("EVAL_LLM_API_KEY", "").strip()
    model = os.environ.get("EVAL_LLM_MODEL", "").strip()
    if not (base_url and api_key and model):
        return None, 2  # caller prints the configuration guidance

    candidates = [s for s in skills if s["user_invocable"]]
    all_names = [s["name"] for s in skills]  # includes library skills (trap detection)
    known_dirs = {(s["plugin"], s["dir_name"]) for s in skills}
    candidate_block = "\n".join(f"- {s['name']}: {s['description']}" for s in candidates)

    results = []
    for case in cases:
        entry = {"id": case["id"], "should_trigger": case["should_trigger"],
                 "expected_skill": case.get("expected_skill"), "predicted": None,
                 "passed": None, "error": None}
        # Skip cases whose expected skill is still under construction.
        if case.get("expected_skill") is not None and \
                (case["expected_plugin"], case["expected_skill"]) not in known_dirs:
            entry["error"] = "skipped: expected skill dir missing"
            results.append(entry)
            continue
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": USER_TEMPLATE.format(
                candidates=candidate_block, utterance=case["utterance"])},
        ]
        error = None
        for attempt in (1, 2):  # one retry, then degrade to a per-case error
            try:
                entry["predicted"] = parse_router_response(
                    chat_completion(base_url, api_key, model, messages, args.timeout))
                error = None
                break
            except Exception as exc:  # network, timeout, HTTP, or parse failure
                error = f"attempt {attempt}: {type(exc).__name__}: {exc}"
        if error:
            entry["error"] = error
        else:
            entry["passed"] = judge(case, entry["predicted"], all_names)
        results.append(entry)

    scored_pos = [r for r in results if r["should_trigger"] and not r["error"]]
    scored_neg = [r for r in results if not r["should_trigger"] and not r["error"]]
    hit_rate = (sum(r["passed"] for r in scored_pos) / len(scored_pos)) if scored_pos else None
    false_trigger_rate = (sum(not r["passed"] for r in scored_neg) / len(scored_neg)) if scored_neg else None
    passed = bool(results)
    if hit_rate is not None:
        passed = passed and hit_rate >= args.threshold
    if false_trigger_rate is not None:
        passed = passed and false_trigger_rate <= 1 - args.threshold
    report = {
        "mode": "llm", "model": model, "base_url": base_url, "threshold": args.threshold,
        "summary": {
            "total": len(results), "positive": len(scored_pos), "negative": len(scored_neg),
            "errors": sum(1 for r in results if r["error"]),
            "hit_rate": hit_rate, "false_trigger_rate": false_trigger_rate,
        },
        "results": results, "passed": passed,
    }
    return report, 0 if passed else 1


# -- Offline mode + reporting

def run_offline_mode(cases, case_errors, skills, repo_root):
    """Validate the eval set structure and the SKILL.md descriptions."""
    errors = list(case_errors)
    if cases:
        errors.extend(validate_cases(cases, repo_root))
    desc = description_report(skills)
    report = {
        "mode": "offline", "repo": repo_root.name,
        "cases": {"total": len(cases),
                  "positive": sum(1 for c in cases if isinstance(c, dict) and c.get("should_trigger") is True),
                  "negative": sum(1 for c in cases if isinstance(c, dict) and c.get("should_trigger") is False)},
        "structural_errors": errors,
        "skills": {"total": len(skills),
                   "user_invocable": sum(1 for s in skills if s["user_invocable"]),
                   "library": sum(1 for s in skills if not s["user_invocable"]),
                   "description_length": desc["length_stats"],
                   "warnings": desc["warnings"]},
        "passed": not errors,
    }
    return report, 0 if not errors else 1


def print_text_report(report):
    """Human-readable rendering of either report kind."""
    if report["mode"] == "offline":
        c, s = report["cases"], report["skills"]
        print(f"== Trigger-eval structural report (offline) == repo: {report['repo']}")
        print(f"Cases: {c['total']} total ({c['positive']} positive, {c['negative']} negative)")
        if report["structural_errors"]:
            for err in report["structural_errors"]:
                print(f"[FAIL] {err}")
        else:
            print("[OK] JSON syntax, unique ids, required fields, bool flags, "
                  "skill dirs, negative notes: all checks passed")
        stats = s["description_length"]
        print(f"Skills scanned: {s['total']} ({s['user_invocable']} user-invocable, {s['library']} library)")
        print(f"Description length (chars): min={stats['min']} median={stats['median']} "
              f"mean={stats['mean']} max={stats['max']}")
        for warn in s["warnings"]:
            print(f"[WARN] {warn['skill']} ({warn['path']}): {warn['reason']}")
        if not s["warnings"]:
            print(f"[OK] all descriptions >= {MIN_DESC_LEN} chars")
        print(f"RESULT: {'PASS' if report['passed'] else 'FAIL'}")
        return
    summary = report["summary"]
    print(f"== Trigger-eval routing report (LLM) == model: {report['model']}")
    for r in report["results"]:
        tag = "ERR " if r["error"] else ("HIT " if r["passed"] else "MISS")
        print(f"[{tag}] {r['id']}: expected={r['expected_skill']} predicted={r['predicted']}"
              + (f" ({r['error']})" if r["error"] else ""))
    fmt = lambda v: "n/a" if v is None else f"{v:.3f}"
    print(f"Summary: total={summary['total']} positive={summary['positive']} "
          f"negative={summary['negative']} errors={summary['errors']}")
    print(f"hit_rate={fmt(summary['hit_rate'])} (threshold {report['threshold']}), "
          f"false_trigger_rate={fmt(summary['false_trigger_rate'])}")
    print(f"RESULT: {'PASS' if report['passed'] else 'FAIL'}")


def print_llm_env_guidance():
    print("LLM mode requires these environment variables (none found):", file=sys.stderr)
    print("  EVAL_LLM_BASE_URL  OpenAI-compatible endpoint, e.g. https://api.openai.com/v1", file=sys.stderr)
    print("  EVAL_LLM_API_KEY   API key for that endpoint", file=sys.stderr)
    print("  EVAL_LLM_MODEL     model name, e.g. gpt-4o-mini", file=sys.stderr)
    print("Example (bash):", file=sys.stderr)
    print('  export EVAL_LLM_BASE_URL="https://api.openai.com/v1"', file=sys.stderr)
    print('  export EVAL_LLM_API_KEY="sk-..."', file=sys.stderr)
    print('  export EVAL_LLM_MODEL="gpt-4o-mini"', file=sys.stderr)
    print("  python evals/run_trigger_evals.py --llm", file=sys.stderr)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Runner for evals/trigger-cases.json "
                                     "(offline structural validation by default, LLM routing with --llm).")
    parser.add_argument("--llm", action="store_true", help="run the LLM routing evaluation")
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD,
                        help=f"pass threshold for hit_rate / 1 - false_trigger_rate (default {DEFAULT_THRESHOLD})")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="report format")
    parser.add_argument("--cases", default=None, metavar="PREFIX[,PREFIX...]",
                        help="only run cases whose id starts with one of these prefixes")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help=f"per-request timeout in seconds for --llm (default {DEFAULT_TIMEOUT})")
    args = parser.parse_args(argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # Windows consoles
    except (AttributeError, ValueError):
        pass

    repo_root = Path(__file__).resolve().parent.parent
    cases, case_errors = load_cases(repo_root)
    if args.cases:
        prefixes = [p.strip() for p in args.cases.split(",") if p.strip()]
        cases = [c for c in cases if isinstance(c, dict) and
                 any(str(c.get("id", "")).startswith(p) for p in prefixes)]
    skills = load_skills(repo_root)

    if args.llm:
        report, code = run_llm_mode(cases, skills, args)
        if code == 2:
            print_llm_env_guidance()
            return 2
    else:
        report, code = run_offline_mode(cases, case_errors, skills, repo_root)

    if args.format == "json":
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_text_report(report)
    return code


if __name__ == "__main__":
    sys.exit(main())
