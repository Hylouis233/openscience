"""Validate the openscience marketplace structure and skill contracts.

Checks performed:
  1. Every plugins/*/skills/*/SKILL.md has a --- delimited frontmatter with:
     - `name`: present, kebab-case, and identical to the skill directory name
     - `description`: present and at least 50 characters long
     - `metadata.last_reviewed` (optional): must match YYYY-MM-DD
  2. Every JSON manifest (.claude-plugin/*.json, marketplace.json, .mcp.json,
     hooks.json) parses as valid JSON.
  3. Every plugin source in .claude-plugin/marketplace.json exists and
     contains .claude-plugin/plugin.json.

Each check prints one PASS/FAIL line; a summary is printed at the end and the
script exits with code 1 if any check failed.

Usage: python scripts/validate-skills.py
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

KEBAB_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

results = []  # list of (ok, message)


def report(ok, message):
    """Record one check result and print it immediately."""
    results.append((ok, message))
    print(f"{'PASS' if ok else 'FAIL'}  {message}")


BLOCK_INDICATORS = {">", ">-", ">+", "|", "|-", "|+"}
KEY_RE = re.compile(r"^([A-Za-z0-9_-]+)\s*:\s*(.*)$")


def parse_frontmatter(text):
    """Parse a minimal YAML-subset frontmatter block.

    Returns (mapping, error). Keys nested under mappings are exposed with
    dotted paths (e.g. "metadata.last_reviewed"); error is None on success.
    Supported subset: flat 'key: value' pairs, nested mappings, block scalars
    ('>-', '|' ...) and indented continuation lines (folded into one string),
    and sequence items ('- ...', skipped -- nothing in them needs validating).
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, "missing opening '---' frontmatter delimiter"
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, "missing closing '---' frontmatter delimiter"

    mapping = {}
    paths = {}       # indent -> dotted key path of the mapping opened there
    last_key = None  # mapping key still accepting continuation lines
    last_indent = 0  # indent of the line that opened last_key
    for raw in lines[1:end]:
        if not raw.strip() or raw.strip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        stripped = raw.strip()
        # A more-indented line continues the previous scalar (block or plain).
        if last_key is not None and indent > last_indent:
            mapping[last_key] = (mapping[last_key] + " " + stripped).strip()
            continue
        if stripped.startswith("- "):  # sequence item: valid YAML, skip
            last_key = None
            continue
        m = KEY_RE.match(stripped)
        if not m:
            return None, f"unparseable frontmatter line: {stripped!r}"
        key, value = m.group(1), m.group(2).strip()
        paths = {i: p for i, p in paths.items() if i < indent}
        parent = next((p for _, p in sorted(paths.items(), reverse=True) if p), None)
        full = f"{parent}.{key}" if parent else key
        if value in BLOCK_INDICATORS:
            mapping[full] = ""
            last_key, last_indent = full, indent
        elif value == "":
            paths[indent] = full  # opening a nested mapping
            last_key = None
        else:
            mapping[full] = value.strip("'\"")
            last_key, last_indent = full, indent
    return mapping, None


def check_skill(skill_md):
    """Validate one SKILL.md file against the frontmatter contract."""
    rel = skill_md.relative_to(ROOT)
    label = f"skill {rel}"
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        report(False, f"{label}: cannot read as UTF-8 ({exc})")
        return

    fm, err = parse_frontmatter(text)
    if err:
        report(False, f"{label}: {err}")
        return

    dir_name = skill_md.parent.name
    name = fm.get("name", "")
    if not name:
        report(False, f"{label}: 'name' field missing")
    elif not KEBAB_RE.match(name):
        report(False, f"{label}: 'name' {name!r} is not kebab-case")
    elif name != dir_name:
        report(False, f"{label}: 'name' {name!r} != directory {dir_name!r}")
    else:
        report(True, f"{label}: name '{name}' is kebab-case and matches directory")

    desc = fm.get("description", "")
    if not desc:
        report(False, f"{label}: 'description' field missing")
    elif len(desc) < 50:
        report(False, f"{label}: 'description' too short ({len(desc)} < 50 chars)")
    else:
        report(True, f"{label}: description present ({len(desc)} chars)")

    reviewed = fm.get("metadata.last_reviewed")
    if reviewed is not None:
        ok = bool(DATE_RE.match(reviewed))
        report(ok, f"{label}: metadata.last_reviewed {reviewed!r} "
                   f"{'is' if ok else 'is NOT'} YYYY-MM-DD")


def check_json(path):
    """Validate that one manifest file parses as JSON."""
    rel = path.relative_to(ROOT)
    try:
        json.loads(path.read_text(encoding="utf-8"))
        report(True, f"json {rel}: valid JSON")
        return True
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        report(False, f"json {rel}: invalid ({exc})")
        return False


def check_marketplace():
    """Validate the marketplace manifest and its plugin source directories."""
    mp = ROOT / ".claude-plugin" / "marketplace.json"
    try:
        data = json.loads(mp.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        report(False, f"marketplace: cannot load {mp.relative_to(ROOT)} ({exc})")
        return

    plugins = data.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        report(False, "marketplace: 'plugins' must be a non-empty list")
        return

    for entry in plugins:
        name = entry.get("name", "<unnamed>")
        source = entry.get("source", "")
        src_dir = (ROOT / source).resolve() if source else None
        if not src_dir or not src_dir.is_dir():
            report(False, f"marketplace plugin {name}: source dir {source!r} missing")
            continue
        pj = src_dir / ".claude-plugin" / "plugin.json"
        if pj.is_file():
            report(True, f"marketplace plugin {name}: source ok, plugin.json present")
            check_json(pj)
        else:
            report(False, f"marketplace plugin {name}: missing {pj.relative_to(ROOT)}")


def main():
    # Keep output readable on Windows GBK consoles.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass

    # 1. Skill frontmatter contracts (empty skill sets are fine).
    skill_files = sorted(ROOT.glob("plugins/*/skills/*/SKILL.md"))
    if not skill_files:
        print("INFO  no skills found under plugins/*/skills/*/, skipping skill checks")
    for skill_md in skill_files:
        check_skill(skill_md)

    # 2. JSON manifests: marketplace.json plus every .mcp.json / hooks.json
    #    and every .claude-plugin/*.json in the repo.
    json_files = {ROOT / ".claude-plugin" / "marketplace.json"}
    json_files.update(ROOT.glob("**/.claude-plugin/*.json"))
    json_files.update(ROOT.glob("**/.mcp.json"))
    json_files.update(ROOT.glob("**/hooks.json"))
    for path in sorted(json_files):
        if path.is_file():
            check_json(path)
        else:
            report(False, f"json {path.relative_to(ROOT)}: file missing")

    # 3. Marketplace plugin source directories.
    check_marketplace()

    # Summary.
    failed = [msg for ok, msg in results if not ok]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed, "
          f"{len(results)} total")
    if failed:
        print("validation FAILED", file=sys.stderr)
        sys.exit(1)
    print("validation OK")


if __name__ == "__main__":
    main()
