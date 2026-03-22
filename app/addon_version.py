"""Read Home Assistant add-on version from bundled `addon_config.yaml` (Docker) or repo `ekstrehub/config.yaml` (dev)."""
from __future__ import annotations

import pathlib
import re


def read_addon_version() -> str | None:
    root = pathlib.Path(__file__).resolve().parent.parent
    for candidate in (root / "addon_config.yaml", root / "ekstrehub" / "config.yaml"):
        if not candidate.is_file():
            continue
        try:
            text = candidate.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        m = re.search(r"^version:\s*[\"']?([^\"'\s]+)[\"']?", text, re.MULTILINE)
        if m:
            return m.group(1).strip()
    return None
