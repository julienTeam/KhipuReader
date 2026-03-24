"""
Khipu dating system — extract dates from the first pendant cords.

Two modes:
  Mode A (Explicit): C1 = year offset from epoch (~1438 CE), C2 = month (1-12),
                     C3 = day (1-30). For standalone official documents.
  Mode B (Checkbox): First 12 positions contain mostly zeros + one "10" tick mark.
                     The position of the "10" (1-indexed) = month.
                     For periodic registers where the year is archive context.

Reference: Sivan (2026), "Dating the Inca Archive."
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from khipu_translator.translator import TranslationResult


# Reference epoch: Pachacutec's accession, start of Inca imperial expansion
DEFAULT_EPOCH = 1438

# Inca month names (Guaman Poma 1615), Month 1 = June (Pleiades rising)
INCA_MONTHS = {
    1:  ("Inti Raymi",      "June",      "Dry (harvest festival)"),
    2:  ("Chahua Huarquiz", "July",      "Dry"),
    3:  ("Yapaquis",        "August",    "Dry (planting prep)"),
    4:  ("Coya Raymi",      "September", "Transition"),
    5:  ("Uma Raymi",       "October",   "Wet (planting)"),
    6:  ("Ayamarca",        "November",  "Wet"),
    7:  ("Qhapaq Raymi",    "December",  "Wet (solstice)"),
    8:  ("Camay",           "January",   "Wet"),
    9:  ("Jatun Pucuy",     "February",  "Wet (rains peak)"),
    10: ("Pacha Pucuy",     "March",     "Transition"),
    11: ("Inca Raymi",      "April",     "Dry (harvest begins)"),
    12: ("Aymuray",         "May",       "Dry"),
}


@dataclass
class KhipuDate:
    """Extracted date from a khipu."""
    khipu_id: str
    mode: str                    # 'A' (explicit) or 'B' (checkbox) or 'AB' (both)
    year_offset: Optional[int]   # C1 value (offset from epoch)
    year_ce: Optional[int]       # absolute year (epoch + offset)
    month: Optional[int]         # 1-12 (Inca calendar, 1=June)
    day: Optional[int]           # 1-30 or None
    month_name: Optional[str]    # Inca month name
    gregorian_month: Optional[str]  # Gregorian equivalent
    season: Optional[str]        # Dry/Wet/Transition
    confidence: str              # 'high', 'medium', 'low'
    epoch: int                   # reference epoch used
    notes: str                   # explanation

    # Checkbox details
    checkbox_ticks: list[int]    # positions of "10" values (1-indexed)
    checkbox_double: bool        # True if 2 ticks (date range)


def extract_date(
    result: TranslationResult,
    epoch: int = DEFAULT_EPOCH,
) -> Optional[KhipuDate]:
    """
    Extract a date from a khipu's first pendant cords.

    Parameters
    ----------
    result : TranslationResult
        A translated khipu.
    epoch : int
        Reference epoch (default: 1438 CE).

    Returns
    -------
    KhipuDate or None
        The extracted date, or None if no date pattern detected.
    """
    # Get first 20 L1 cord values in order
    first_values = []
    first_types = []
    for cl in result.clusters:
        for c in cl.cords:
            if c.level == 1:
                if c.cord_type == "INT" and c.locke_value is not None:
                    first_values.append(int(c.locke_value))
                    first_types.append("INT")
                elif c.cord_type == "STRING":
                    first_values.append(None)
                    first_types.append("STRING")
                elif c.cord_type == "EMPTY":
                    first_values.append(0)
                    first_types.append("EMPTY")
                else:
                    first_values.append(0)
                    first_types.append("OTHER")
            if len(first_values) >= 20:
                break
        if len(first_values) >= 20:
            break

    if len(first_values) < 3:
        return None

    # Try Mode A (Explicit)
    mode_a = _try_mode_a(first_values, first_types, epoch)

    # Try Mode B (Checkbox)
    mode_b = _try_mode_b(first_values, first_types, epoch)

    # Return best result
    if mode_a and mode_b:
        # Both modes detected — combine
        mode_a.mode = "AB"
        if mode_a.month is None and mode_b.month is not None:
            mode_a.month = mode_b.month
            _fill_month_info(mode_a)
        mode_a.checkbox_ticks = mode_b.checkbox_ticks
        mode_a.checkbox_double = mode_b.checkbox_double
        mode_a.notes += f" Checkbox confirms month {mode_b.month}."
        return mode_a
    elif mode_a:
        return mode_a
    elif mode_b:
        return mode_b

    return None


def _try_mode_a(
    values: list,
    types: list,
    epoch: int,
) -> Optional[KhipuDate]:
    """Try Mode A: C1=year offset, C2=month, C3=day."""
    c1 = values[0] if len(values) > 0 else None
    c2 = values[1] if len(values) > 1 else None
    c3 = values[2] if len(values) > 2 else None

    # C1 must be non-round integer 13-100
    if c1 is None or c1 < 13 or c1 > 100:
        return None
    if c1 % 10 == 0:  # round numbers are likely tribute
        return None

    # C2 must be 1-12 (month)
    if c2 is None or c2 < 1 or c2 > 12:
        return None

    # C3 is optional (day, 1-30)
    day = None
    if c3 is not None and 1 <= c3 <= 30:
        day = c3

    year_ce = epoch + c1
    confidence = "medium"
    notes = f"Mode A: C1={c1} (year offset), C2={c2} (month)"
    if day:
        notes += f", C3={day} (day)"
        confidence = "medium"
    else:
        notes += ", no day detected"

    date = KhipuDate(
        khipu_id="",
        mode="A",
        year_offset=c1,
        year_ce=year_ce,
        month=c2,
        day=day,
        month_name=None,
        gregorian_month=None,
        season=None,
        confidence=confidence,
        epoch=epoch,
        notes=notes,
        checkbox_ticks=[],
        checkbox_double=False,
    )
    _fill_month_info(date)
    return date


def _try_mode_b(
    values: list,
    types: list,
    epoch: int,
) -> Optional[KhipuDate]:
    """Try Mode B: checkbox pattern with "10" as tick mark."""
    # Need at least 12 positions
    if len(values) < 12:
        return None

    # First cord should be 0, STRING, or EMPTY
    if values[0] is not None and values[0] > 0 and types[0] == "INT":
        # C1 has a positive value — might be Mode A, not B
        # Unless C1 is round (tribute) or > 12
        if values[0] % 10 != 0 and 13 <= values[0] <= 100:
            return None  # looks like Mode A

    # Scan first 12 positions for "10" ticks
    ticks = []
    for i in range(min(12, len(values))):
        v = values[i]
        if v == 10:
            ticks.append(i + 1)  # 1-indexed

    if len(ticks) == 0:
        return None

    # Check that non-tick positions are mostly 0 or STRING
    non_tick_nonzero = 0
    for i in range(min(12, len(values))):
        if (i + 1) not in ticks:
            v = values[i]
            if v is not None and v > 0 and types[i] == "INT":
                non_tick_nonzero += 1

    # Allow up to 3 non-tick non-zero values (some khipus have sparse data)
    if non_tick_nonzero > 3:
        return None

    month = ticks[0]
    is_double = len(ticks) >= 2

    confidence = "medium" if not is_double else "low"
    if non_tick_nonzero == 0:
        confidence = "high" if not is_double else "medium"

    if is_double:
        notes = f"Mode B: checkbox ticks at positions {ticks} (date range months {ticks[0]}-{ticks[-1]})"
    else:
        notes = f"Mode B: checkbox tick at position {month}"

    date = KhipuDate(
        khipu_id="",
        mode="B",
        year_offset=None,
        year_ce=None,
        month=month,
        day=None,
        month_name=None,
        gregorian_month=None,
        season=None,
        confidence=confidence,
        epoch=epoch,
        notes=notes,
        checkbox_ticks=ticks,
        checkbox_double=is_double,
    )
    _fill_month_info(date)
    return date


def _fill_month_info(date: KhipuDate) -> None:
    """Fill in month name, Gregorian equivalent, and season."""
    if date.month and date.month in INCA_MONTHS:
        name, greg, season = INCA_MONTHS[date.month]
        date.month_name = name
        date.gregorian_month = greg
        date.season = season


def format_date(date: KhipuDate) -> str:
    """Format a KhipuDate for display."""
    lines = []

    if date.year_ce and date.month:
        day_str = f"/{date.day:02d}" if date.day else ""
        lines.append(f"  Date: {date.year_ce}/{date.month:02d}{day_str} CE")
    elif date.month:
        lines.append(f"  Month: {date.month}")

    if date.month_name:
        lines.append(f"  Inca month: {date.month_name} ({date.gregorian_month}, {date.season})")

    if date.year_offset:
        lines.append(f"  Year offset: {date.year_offset} from epoch {date.epoch}")

    lines.append(f"  Mode: {date.mode} ({_mode_desc(date.mode)})")
    lines.append(f"  Confidence: {date.confidence}")
    lines.append(f"  {date.notes}")

    if date.checkbox_ticks:
        lines.append(f"  Checkbox ticks: positions {date.checkbox_ticks}")

    return "\n".join(lines)


def _mode_desc(mode: str) -> str:
    if mode == "A":
        return "explicit year/month/day"
    elif mode == "B":
        return "checkbox month indicator"
    elif mode == "AB":
        return "explicit + checkbox"
    return mode
