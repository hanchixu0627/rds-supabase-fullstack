#!/usr/bin/env python3
"""Static validation for the RDS Supabase skill package.

Checks SKILL.md frontmatter, required sections, link targets and secret-like
strings. Exits non-zero on the first failure.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
SKILL_MD = SKILL_DIR / "SKILL.md"

REQUIRED_SECTIONS = [
    "## 概述",
    "## 适用范围",
    "## 前置条件",
    "## 工作流",
    "## 可用工具",
    "## 参数确认",
    "## 输出格式",
    "## 验证方法",
    "## 注意事项",
    "## 参考文档",
]

SECRET_PATTERN = re.compile(
    r"(ey[A-Za-z0-9_-]{20,}|[A-Fa-f0-9]{32,}|SUPABASE_SERVICE_ROLE_KEY\s*=\s*\S+)"
)


def fail(message: str) -> int:
    print(f"validate-skill: {message}")
    return 1


def main() -> int:
    if not SKILL_MD.exists():
        return fail("SKILL.md missing")
    text = SKILL_MD.read_text(encoding="utf-8")

    if not text.startswith("---"):
        return fail("frontmatter missing")
    frontmatter = text.split("---", 2)[1]

    # Parse the frontmatter as real YAML so quoting errors (for example an
    # unquoted value containing ": ") are caught here instead of at load time.
    try:
        import yaml
    except ImportError:
        yaml = None  # type: ignore[assignment]
    if yaml is not None:
        try:
            data = yaml.safe_load(frontmatter)
        except yaml.YAMLError as exc:
            return fail(f"frontmatter YAML is invalid: {exc}")
        if not isinstance(data, dict):
            return fail("frontmatter must be a YAML mapping")
        for key in ("name", "description"):
            if not isinstance(data.get(key), str) or not data[key].strip():
                return fail(f"frontmatter key missing or empty: {key}")
    else:
        # PyYAML unavailable: fall back to a naive presence check.
        for key in ("name:", "description:"):
            if key not in frontmatter:
                return fail(f"frontmatter key missing: {key}")

    for section in REQUIRED_SECTIONS:
        if section not in text:
            return fail(f"section missing: {section}")

    if len(text.encode()) > 60_000:
        return fail("SKILL.md exceeds 60 KB")

    match = SECRET_PATTERN.search(text)
    if match:
        return fail("secret-like string found in SKILL.md")

    for reference in re.findall(r"references/([a-z0-9-]+\.md)", text):
        if not (SKILL_DIR / "references" / reference).exists():
            return fail(f"broken reference link: {reference}")

    print("validate-skill: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
