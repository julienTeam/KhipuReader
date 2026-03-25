"""
Knowledge database — loads research notes from contributions/ JSON files.

Each khipu's knowledge is stored as a separate JSON file in contributions/.
This module loads them on demand and provides a unified interface.

JSON format:
  {
    "khipu": "UR006",
    "contributor": "Name <email>",
    "date": "2026-03-25",
    "status": "proposed|reviewed|confirmed",
    "confidence": "low|medium|medium-high|high",
    "summary": "One paragraph description...",
    "interpretation": "Multi-line research notes...",
    "references": ["Source 1", "Source 2"],
    "reconstructed_xlsx": "filename.xlsx" or null
  }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


CONTRIBUTIONS_DIR = Path(__file__).parent.parent.parent / "contributions"


def get_knowledge(khipu_id: str) -> Optional[dict]:
    """
    Load knowledge entry for a khipu from its JSON file.

    Parameters
    ----------
    khipu_id : str
        Khipu identifier (e.g. 'UR006').

    Returns
    -------
    dict or None
        The knowledge entry, or None if no file exists.
    """
    path = CONTRIBUTIONS_DIR / f"{khipu_id}.json"
    if not path.exists():
        return None

    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    # Only return entries that have meaningful content
    if not data.get("summary") or "TODO" in data.get("summary", ""):
        return None

    return data


def list_known_khipus() -> list[str]:
    """Return list of khipu IDs that have knowledge entries."""
    if not CONTRIBUTIONS_DIR.exists():
        return []

    known = []
    for path in sorted(CONTRIBUTIONS_DIR.glob("*.json")):
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if data.get("summary") and "TODO" not in data.get("summary", ""):
                known.append(data.get("khipu", path.stem))
        except (json.JSONDecodeError, OSError):
            continue

    return known
