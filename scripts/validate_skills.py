#!/usr/bin/env python3
"""Repo-level Agent Skills contract validator (checks A1-A7).

Validates every skill under skills/ against the Agent Skills open-standard
format contract and repository conventions:

A1  expected rds-supabase skills present, no unexpected skills (pre-existing
    foreign skills are tolerated but exempt from the contract checks)
A2  frontmatter fields: allowed set, name rules, description length, semver version
A3  SKILL.md body under 500 lines
A4  no README.md / INSTALLATION_GUIDE.md / QUICK_REFERENCE.md inside skills
A5  reference file prefixes match references/_sections.md sections
A6  metadata.version appears in the root CHANGELOG.md (version-drift tripwire)
A7  description carries a trigger signal and is at least 80 characters

Complements the per-skill validator (skills/rds-supabase-mcp/scripts/validate-skill.py).
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "skills"
EXPECTED_SKILLS = {
    "rds-supabase-mcp",
    "rds-supabase",
    "rds-supabase-postgres-best-practices",
    "huawei-supabase-frontend",
}
# Skills present in this repository that are not authored against the A1-A7
# contract (tolerated; A2-A7 skipped).
FOREIGN_SKILLS = {"huaweicloud-mcp-dev", "rds-supabase-mgr"}

ALLOWED_FIELDS = {"name", "description", "license", "allowed-tools", "metadata", "compatibility"}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")
SECTION_RE = re.compile(r"^## \d+\. .+\((\w+)\)\s*$", re.MULTILINE)
TRIGGER_MARKERS = ("use when", "load this skill", "triggers:", "触发", "之前加载", "何时")
FORBIDDEN_FILES = {"README.md", "INSTALLATION_GUIDE.md", "QUICK_REFERENCE.md"}


def parse_frontmatter(text: str) -> dict:
    """Parse the YAML frontmatter; falls back to a two-level regex parser."""
    if not text.startswith("---\n"):
        return {}
    block = text.split("---\n", 2)[1]
    try:
        import yaml  # type: ignore[import-not-found]

        data = yaml.safe_load(block)
        return data if isinstance(data, dict) else {}
    except ImportError:
        fm: dict = {}
        parent = None
        for line in block.splitlines():
            if not line.strip() or line.strip().startswith("#"):
                continue
            if line.startswith("  ") and parent:
                m = re.match(r"^\s+([a-zA-Z-]+):\s*['\"]?([^'\"\n]*)['\"]?\s*$", line)
                if m and isinstance(fm.get(parent), dict):
                    fm[parent][m.group(1)] = m.group(2)
            elif ":" in line and not line.startswith((" ", "\t", "-")):
                key, value = line.split(":", 1)
                key, value = key.strip(), value.strip()
                if value == "":
                    fm[key] = {}
                    parent = key
                else:
                    fm[key] = value.strip("'\"")
                    parent = None
        return fm


def main() -> int:
    errors: list[str] = []
    if not SKILLS_DIR.is_dir():
        print(f"FAIL: {SKILLS_DIR} not found")
        return 1

    found = {p.name for p in SKILLS_DIR.iterdir() if (p / "SKILL.md").is_file()}
    missing = EXPECTED_SKILLS - found
    unknown = found - EXPECTED_SKILLS - FOREIGN_SKILLS
    if missing or unknown:
        errors.append(
            f"A1 skill set mismatch: missing {sorted(missing)}, unexpected {sorted(unknown)}"
        )

    changelog = REPO_ROOT / "CHANGELOG.md"
    changelog_text = changelog.read_text(encoding="utf-8") if changelog.exists() else ""

    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        skill = skill_dir.name
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file() or skill not in EXPECTED_SKILLS:
            continue
        text = skill_md.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        if not fm:
            errors.append(f"{skill}: A2 frontmatter missing or unparseable")
            continue

        extra = set(fm) - ALLOWED_FIELDS
        if extra:
            errors.append(f"{skill}: A2 unexpected frontmatter fields {sorted(extra)}")

        name = fm.get("name")
        if not isinstance(name, str) or not name:
            errors.append(f"{skill}: A2 name missing")
        else:
            normalized = unicodedata.normalize("NFKC", name)
            if not (1 <= len(normalized) <= 64) or not NAME_RE.match(normalized):
                errors.append(f"{skill}: A2 invalid name {name!r}")
            if name != skill_dir.name:
                errors.append(f"{skill}: A2 name {name!r} != directory {skill_dir.name!r}")

        desc = fm.get("description")
        if not isinstance(desc, str) or not (1 <= len(desc) <= 1024):
            errors.append(f"{skill}: A2 description must be 1-1024 characters")
        elif len(desc) < 80 or not any(m in desc.lower() for m in TRIGGER_MARKERS):
            errors.append(f"{skill}: A7 description lacks trigger signal or is too short")

        meta = fm.get("metadata")
        version = meta.get("version") if isinstance(meta, dict) else None
        if not isinstance(version, str) or not SEMVER_RE.match(version):
            errors.append(f"{skill}: A2 metadata.version must be a semver string")
        elif changelog_text and version not in changelog_text:
            errors.append(f"{skill}: A6 version {version} not found in root CHANGELOG.md")

        body = text.split("---\n", 2)[2] if text.startswith("---\n") else text
        if body.count("\n") >= 500:
            errors.append(f"{skill}: A3 body has {body.count(chr(10))} lines (limit: 500)")

        for f in skill_dir.rglob("*"):
            if f.is_file() and f.name in FORBIDDEN_FILES:
                errors.append(f"{skill}: A4 forbidden file {f.relative_to(skill_dir)}")

        refs_dir = skill_dir / "references"
        sections_file = refs_dir / "_sections.md"
        if sections_file.is_file() and refs_dir.is_dir():
            prefixes = set(SECTION_RE.findall(sections_file.read_text(encoding="utf-8")))
            for ref in refs_dir.glob("*.md"):
                if ref.name.startswith("_"):
                    continue
                if ref.name.split("-", 1)[0] not in prefixes:
                    errors.append(
                        f"{skill}: A5 reference {ref.name!r} prefix not in _sections.md"
                    )

    if errors:
        for e in errors:
            print(f"FAIL: {e}")
        return 1
    print(f"validate-skills: OK ({len(found)} skills)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
