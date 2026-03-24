"""
Stage 1: Schema Detection — classify the physical structure of a khipu.

5 schema types:
  Form:       E-knot dominant, binary encoding, minimal subsidiaries
  Flat:       All L1, uniform clusters, Locke decimal
  Calculator: High median values (>500), mostly S-knots
  Relational: Exactly 2 levels (L1 + L2), no deeper
  Structured: Depth 3-6, color varies by level, arborescent

Priority: Structured > Relational > Flat > Form
Calculator identified by value magnitude, not depth.

Reference: Sivan (2026), "Khipu Reader Pipeline Architecture Brief"
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from khipu_translator.translator import TranslationResult


@dataclass
class SchemaResult:
    """Output of schema detection."""
    schema_type: str        # 'form', 'flat', 'calculator', 'relational', 'structured'
    max_depth: int          # deepest cord level
    n_clusters: int         # number of clusters
    modal_cluster_size: int # most common cluster size
    pct_string_cords: float # % of cords that are STRING
    pct_e_only: float       # % of knotted cords with E-knots only
    median_value: float     # median Locke value of INT cords
    notes: str


def detect_schema(result: TranslationResult) -> SchemaResult:
    """
    Detect the schema type of a khipu.

    Parameters
    ----------
    result : TranslationResult
        A translated khipu.

    Returns
    -------
    SchemaResult
    """
    all_cords = result.cords
    n_total = len(all_cords)

    if n_total == 0:
        return SchemaResult(
            schema_type="flat", max_depth=0, n_clusters=0,
            modal_cluster_size=0, pct_string_cords=0, pct_e_only=0,
            median_value=0, notes="Empty khipu",
        )

    # Max depth
    max_depth = max(c.level for c in all_cords)

    # Cluster sizes
    from collections import Counter
    cluster_sizes = Counter()
    for cl in result.clusters:
        cluster_sizes[len(cl.cords)] += 1
    modal_size = cluster_sizes.most_common(1)[0][0] if cluster_sizes else 0

    # STRING percentage
    n_string = sum(1 for c in all_cords if c.cord_type == "STRING")
    pct_string = 100 * n_string / n_total if n_total else 0

    # E-only cords (knotted cords with ONLY E-knots, no L, no S)
    n_e_only = 0
    n_knotted = 0
    for c in all_cords:
        if c.knot_sequence and c.knot_sequence.strip():
            n_knotted += 1
            parts = c.knot_sequence.split()
            has_l = any(p.startswith("L") for p in parts)
            has_s = any(p.startswith("S") for p in parts)
            has_e = any(p == "E" for p in parts)
            if has_e and not has_l and not has_s:
                n_e_only += 1
    pct_e_only = 100 * n_e_only / n_knotted if n_knotted else 0

    # Median value of INT cords
    int_values = sorted(
        int(c.locke_value) for c in all_cords
        if c.cord_type == "INT" and c.locke_value is not None and c.locke_value > 0
    )
    median_value = int_values[len(int_values) // 2] if int_values else 0

    # --- Classification ---

    # Form: >30% E-only, max depth 1
    if pct_e_only > 30 and max_depth <= 1:
        return SchemaResult(
            schema_type="form", max_depth=max_depth, n_clusters=len(result.clusters),
            modal_cluster_size=modal_size, pct_string_cords=pct_string,
            pct_e_only=pct_e_only, median_value=median_value,
            notes=f"E-only={pct_e_only:.0f}%, binary encoding. "
                  f"May be pre-Inca (Cajamarquilla type) — do NOT apply syllabary.",
        )

    # Calculator: high median values
    if median_value > 500:
        return SchemaResult(
            schema_type="calculator", max_depth=max_depth, n_clusters=len(result.clusters),
            modal_cluster_size=modal_size, pct_string_cords=pct_string,
            pct_e_only=pct_e_only, median_value=median_value,
            notes=f"Median value={median_value}. Large aggregate numbers (tribute/census).",
        )

    # Structured: depth 3+, color varies by level
    if max_depth >= 3:
        return SchemaResult(
            schema_type="structured", max_depth=max_depth, n_clusters=len(result.clusters),
            modal_cluster_size=modal_size, pct_string_cords=pct_string,
            pct_e_only=pct_e_only, median_value=median_value,
            notes=f"Depth {max_depth}. Arborescent: each pendant is a tree root.",
        )

    # Relational: exactly 2 levels
    if max_depth == 2:
        return SchemaResult(
            schema_type="relational", max_depth=max_depth, n_clusters=len(result.clusters),
            modal_cluster_size=modal_size, pct_string_cords=pct_string,
            pct_e_only=pct_e_only, median_value=median_value,
            notes="L1 = headers/labels, L2 = data/qualifiers.",
        )

    # Flat: all L1, uniform clusters
    return SchemaResult(
        schema_type="flat", max_depth=max_depth, n_clusters=len(result.clusters),
        modal_cluster_size=modal_size, pct_string_cords=pct_string,
        pct_e_only=pct_e_only, median_value=median_value,
        notes=f"All L1, modal cluster size={modal_size}.",
    )


def format_schema(s: SchemaResult) -> str:
    """Format a SchemaResult for display."""
    return (
        f"  Schema: {s.schema_type.upper()}\n"
        f"  Max depth: L{s.max_depth}\n"
        f"  Clusters: {s.n_clusters} (modal size: {s.modal_cluster_size})\n"
        f"  STRING: {s.pct_string_cords:.1f}%\n"
        f"  E-only: {s.pct_e_only:.1f}%\n"
        f"  Median INT value: {s.median_value}\n"
        f"  {s.notes}"
    )
