"""Joint ratings for a DBF-Combined concept import: where each `rated_load_n` comes from.

Convention (standards/design-standards.yaml#ultimate_factor: "joint ratings are ultimate ratings"): the platform's tier-2
load is mass x g x landing_load_factor 3 x ultimate_factor 1.5, so `rated_load_n` here is an ULTIMATE capacity, the load at
which the source's own (EST) allowable is reached. The source's margins are stress / allowable with K x limit load, so
capacity = limit load x K x (1 + MS) = allowable x area.

The concept's source facts (doc rows, allowables, citation texts, the structures folder) are the "ratings" block of its
CONCEPTS entry in importers/dbf.py and are passed in as `ratings`. Nothing concept-specific is written in this file.

Three kinds of rating, each returns (value_N, source_text):
  doc          a row of the concept's structures docs that analyses the joint (or its part pair): limit load, MS, K from the row
  derived      allowable x geometry: bond area measured on our meshes x bond or foam shear; fastener count x stress
               area x steel allowable; pin shear
  placeholder  no capacity is published or tested in the source (foam tape, gel pads, straps, ties, tape hinge): set to
               the platform's own tier-2 demand rounded up, so the check is VACUOUS for that joint. Marked in the YAML.
"""
from __future__ import annotations

import math
import re

PLACEHOLDER_VIA = {"CT-TAPE-FOAM", "CT-GEL-PAD", "CT-STRAP-VELCRO", "CT-TIE", "CT-TAPE-HINGE"}


def rating_basis(kind: str) -> str:
    """Schema attachment.rating_basis for a kind returned by rating(): doc -> sourced, placeholder -> placeholder,
    every other kind (derived) -> derived."""
    return {"doc": "sourced", "placeholder": "placeholder"}.get(kind, "derived")


def _fastener_d(text: str) -> float | None:
    m = re.search(r"\bM(\d(?:\.\d)?)", text or "")
    return float(m.group(1)) if m else None


def _default_ratings() -> dict:
    from .dbf import CONCEPTS  # lazy: dbf imports this module
    return CONCEPTS["A"]["ratings"]


def rating(edge: dict, parent: dict, child: dict, area_mm2: float | None, ratings: dict | None = None) -> tuple[float | None, str, str]:
    """(value_N or None for a placeholder, kind, source text). `parent`/`child` are PARTS entries. `ratings` is the
    concept's "ratings" block (default: concept A)."""
    R = ratings if ratings is not None else _default_ratings()
    eid, via = edge["id"], edge["via"]
    if eid in R["peel_not_sourced"]:
        return None, "placeholder", f"placeholder - not from source: {R['peel_text']}; set to the platform's own demand"
    if eid in R["doc"]:
        d = R["doc"][eid]
        if d[0] == "k":
            _, limit, ms, k, text = d
            return (round(limit * k * (1 + ms), 1), "doc",
                    f"{R['structures_dir']}{text}; rated = {limit:g} N x K {k:.5g} x (1 + MS {ms:g})")
        return round(d[1], 1), "doc", f"{R['structures_dir']}{d[2]}"
    if via in PLACEHOLDER_VIA:
        basis = R["strap_text"] if via == "CT-STRAP-VELCRO" else R["no_capacity_text"]
        return None, "placeholder", (f"placeholder - not from source: {via} has no published or tested capacity "
                                     f"({basis}); set to the platform's own demand")
    js = edge.get("joint_stack")
    if js:
        d = _fastener_d(js.get("fastener", ""))
        n = int(js.get("count", 1))
        text = js.get("fastener", "")
        if "clevis pin" in text.lower():
            dia = float(re.search(r"([\d.]+)\s*mm", text).group(1))
            val = n * math.pi / 4 * dia ** 2 * R["steel_shear_mpa"]
            return round(val, 1), "derived", (f"{n} x pin shear pi/4 x {dia:g}^2 mm2 x {R['steel_shear_mpa']:g} MPa "
                                              f"({R['steel_shear_src']})")
        if d in R["stress_area_mm2"]:
            a_s, a_src = R["stress_area_mm2"][d]
            val = n * a_s * R["steel_tension_mpa"]
            tag = "" if "placeholder" not in a_src else " (placeholder stress area)"
            return round(val, 1), "derived", (f"{n} x M{d:g} tension {a_s} mm2 ({a_src}) x {R['steel_tension_mpa']:g} MPa "
                                              f"({R['steel_tension_src']}){tag}")
    if via in ("CT-EPOXY", "CT-CA", "CT-A-PROP-ADAPTER", "CT-HW-SEATED", "CT-SERVO-SPLINE") and area_mm2 is not None:
        foam = any("XPS" in (p.get("material") or "") for p in (parent, child))
        if foam:
            tau, src = R["xps_shear_kpa"] * 1e-3, R["xps_src"]
        else:
            tau, src = R["bond_tau_mpa"], R["bond_tau_src"]
        ca = " (CA assumed as strong as epoxy: no CA allowable in the source)" if via == "CT-CA" and not foam else ""
        return round(tau * area_mm2, 1), "derived", f"contact area {area_mm2:.0f} mm2 (measured on the meshes) x {src}{ca}"
    return None, "placeholder", f"placeholder - not from source: no rule for {via}; set to the platform's own demand"
