"""Joint ratings for the DBF-Combined concept A import: where each `rated_load_n` comes from.

Convention (standards/design-standards.yaml#ultimate_factor: "joint ratings are ultimate ratings"): the platform's tier-2
load is mass x g x landing_load_factor 3 x ultimate_factor 1.5, so `rated_load_n` here is an ULTIMATE capacity, the load at
which the source's own (EST) allowable is reached. The source's margins are stress / allowable with K x limit load, so
capacity = limit load x K x (1 + MS) = allowable x area; K = KF 1.725 (CF / metal) or KP 2.15625 (printed / bonded),
redesign/qp/A/structures/structures_a.py L10-12. Nothing in this file is a new number except the three flagged below.

Three kinds of rating, each returns (value_N, source_text):
  doc          a row of qp/A/structures/*.md that analyses the joint (or its part pair): limit load, MS, K from the row
  derived      allowable x geometry: bond area measured on our meshes x BOND_TAU / XPS shear; fastener count x stress
               area x steel allowable; pin shear
  placeholder  no capacity is published or tested in the source (foam tape, gel pads, straps, ties, tape hinge): set to
               the platform's own tier-2 demand rounded up, so the check is VACUOUS for that joint. Marked in the YAML.
"""
from __future__ import annotations

import math
import re

FS_ULT, FS_FIT, FS_PRINT = 1.5, 1.15, 1.25       # structures_a.py L10
KF = FS_ULT * FS_FIT                              # 1.725   (structures_a.py L12)
KP = FS_ULT * FS_FIT * FS_PRINT                   # 2.15625 (structures_a.py L12)

BOND_TAU_MPA = 2.0        # structures_a.py L17: "neat epoxy on CF/PETG, C6 `E-FIN-13` allowable" (EST there, coupons not run)
BOND_TAU_SRC = "structures_a.py L17 BOND_TAU 2.0 MPa (EST)"  # the one place this citation is written
XPS_SHEAR_KPA = 86.0      # foam_103.md last line: "shear 86 (EST, 100 x 103/120)" (EST there)
STEEL_TENSION_MPA = 450.0  # arm_cup_checks.md: M2.5 screw tension allowable 450.0 MPa (steel allowable EST)
STEEL_SHEAR_MPA = 270.0    # arm_cup_checks.md: "M2.5 screw shear (shank) ... 270.0 MPa" (EST)
# tensile stress areas (mm2): M2.5 and M3 are the source's own values (arm_cup_checks.py L82, structures_a.py L228).
# M2 and M5 are NOT in the source: the ISO 898-1 standard values, which we did not open -> placeholder, marked.
STRESS_AREA_MM2 = {2.5: (3.39, "arm_cup_checks.py L82"), 3.0: (5.03, "structures_a.py L228"),
                   2.0: (2.07, "placeholder: ISO 898-1 standard value, not opened"),
                   5.0: (14.2, "placeholder: ISO 898-1 standard value, not opened")}

STRUCT = "redesign/qp/A/structures/"

# edge id -> ("k", limit_N, MS, K, text) | ("abs", value_N, text)
DOC: dict[str, tuple] = {}


def _doc_k(ids, limit, ms, k, text):
    for i in ids:
        DOC[i] = ("k", limit, ms, k, text)


# The lens-cap peel rows (foam_103.md L10, 'Stop reaction at stall (30 N) peeling the lens cap off the skin') are NOT
# here: the same row says "peel of the tape skin is not covered by a foam value: pull coupon required". See PEEL_NOT_SOURCED.
_doc_k(("E-FIN-01", "E-FIN-09"), 130.0, 6.17, KP,
       "iter2_margins.md 'Fin root block on fin tube (40 mm long, 16 mm OD)', 130 N, MS +6.17")
_doc_k(("E-FIN-02", "E-FIN-10"), 84.0, 28.14, KP,
       "iter2_margins.md 'Rib tube 14x12 in fin root block, 60 mm embed', 84 N, MS +28.14")
_doc_k(("E-FIN-03", "E-FIN-04", "E-FIN-11", "E-FIN-12"), 783.0, 0.34, KP,
       "iter2_margins.md 'Rib saddle on 12 mm spar, wrap 60 mm wide', 783 N, MS +0.34 (same saddle wrap used for the "
       "saddle-on-rib joint)")
_doc_k(("E-GER-01", "E-GER-03", "E-GER-05", "E-GER-07"), 52.0, 21.41, KP,
       "iter2_margins.md 'Foot shoe on the fin tube end (25 mm wrap, 16 mm OD)', 52 N, MS +21.41")
_doc_k(("E-CGE-01", "E-CGE-03", "E-CGE-05", "E-CGE-07"), 296.0, 0.48, KP,
       "iter2_margins.md 'Arm 12x10 in socket, 25 mm, strike couple', 296 N, MS +0.48")
_doc_k(("E-CGE-09",), 188.0, 1.32, KP,
       "iter2_margins.md 'Bridge 12x10 in hub, strike couple', 188 N, MS +1.32")
_doc_k(("E-CGE-13", "E-CGE-14", "E-CGE-16", "E-CGE-17"), 19.0, 8.20, KP,
       "iter2_margins.md 'V strut saddles (6x4.5, 20 mm)', 19 N, MS +8.20")
DOC["E-CGE-18"] = ("abs", BOND_TAU_MPA * 600.0,
                   "structures_run.md L225 'Pack tray to hub (PETG, 600 mm2 bond)': BOND_TAU 2.0 MPa x 600 mm2")
for _e in ("E-PRP-01", "E-PRP-03", "E-PRP-05", "E-PRP-07"):
    DOC[_e] = ("abs", 4 * 20.0 * 9.3,
               "arm_cup_checks.md 'Head pull-through': 4 screws x PETG bearing 20.0 MPa x annulus 9.3 mm2 (governs over "
               "screw tension and thread strip)")
for _e in ("E-MEC-03", "E-MEC-08"):
    DOC[_e] = ("abs", 73.0, "qp5_checks.md s1 pushrod buckling, Pcr 73 N at the CAD rod length 52.5 mm (D-194)")
for _e in ("E-WNG-01",):
    DOC[_e] = ("abs", round(XPS_SHEAR_KPA * 1e-3 * math.pi * 12.0 * 400.0, 1),
               "foam_103.md XPS shear 86 kPa x bore wrap pi x 12 mm x 0.40 m (bond rule |y| <= 0.20 m, E-WNG-01 notes, "
               "FIXES2)")

def rating_basis(kind: str) -> str:
    """Schema attachment.rating_basis for a kind returned by rating(): doc -> sourced, placeholder -> placeholder,
    every other kind (derived) -> derived."""
    return {"doc": "sourced", "placeholder": "placeholder"}.get(kind, "derived")


PLACEHOLDER_VIA = {"CT-TAPE-FOAM", "CT-GEL-PAD", "CT-STRAP-VELCRO", "CT-TIE", "CT-TAPE-HINGE"}

# Lens-cap flanges bonded (CT-EPOXY) on the tape skin. The 30 N stop reaction is a PEEL load, and foam_103.md L10 says
# the peel is not covered by any value (pull coupon required). The only adhesive allowable in the source is the epoxy
# SHEAR value BOND_TAU, which does not apply to peel, so no derived rating is used: placeholder, set to our own demand.
PEEL_NOT_SOURCED = ("E-WNG-30R", "E-WNG-31R", "E-WNG-30L", "E-WNG-31L")
PEEL_NOT_SOURCED_TEXT = ("foam_103.md L10 'Stop reaction at stall (30 N) peeling the lens cap off the skin' states 'peel of "
                         "the tape skin is not covered by a foam value: pull coupon required'; the only adhesive allowable is "
                         f"epoxy shear ({BOND_TAU_SRC}), which does not apply to peel")


def _fastener_d(text: str) -> float | None:
    m = re.search(r"\bM(\d(?:\.\d)?)", text or "")
    return float(m.group(1)) if m else None


def rating(edge: dict, parent: dict, child: dict, area_mm2: float | None) -> tuple[float | None, str, str]:
    """(value_N or None for a placeholder, kind, source text). `parent`/`child` are PARTS entries."""
    eid, via = edge["id"], edge["via"]
    if eid in PEEL_NOT_SOURCED:
        return None, "placeholder", f"placeholder - not from source: {PEEL_NOT_SOURCED_TEXT}; set to the platform's own demand"
    if eid in DOC:
        d = DOC[eid]
        if d[0] == "k":
            _, limit, ms, k, text = d
            return round(limit * k * (1 + ms), 1), "doc", f"{STRUCT}{text}; rated = {limit:g} N x K {k:.5g} x (1 + MS {ms:g})"
        return round(d[1], 1), "doc", f"{STRUCT}{d[2]}"
    if via in PLACEHOLDER_VIA:
        basis = ("structures_run.md L225 'strap: 2 x 20 mm Velcro ... not tested'" if via == "CT-STRAP-VELCRO" else
                 "no capacity found in qp/A/structures or the EDGES notes, see "
                 "knowledge/sources/dbf-concept-a-joint-capacities.md")
        return None, "placeholder", (f"placeholder - not from source: {via} has no published or tested capacity "
                                     f"({basis}); set to the platform's own demand")
    js = edge.get("joint_stack")
    if js:
        d = _fastener_d(js.get("fastener", ""))
        n = int(js.get("count", 1))
        text = js.get("fastener", "")
        if "clevis pin" in text.lower():
            dia = float(re.search(r"([\d.]+)\s*mm", text).group(1))
            val = n * math.pi / 4 * dia ** 2 * STEEL_SHEAR_MPA
            return round(val, 1), "derived", (f"{n} x pin shear pi/4 x {dia:g}^2 mm2 x {STEEL_SHEAR_MPA:g} MPa "
                                              "(arm_cup_checks.md steel shear allowable, EST)")
        if d in STRESS_AREA_MM2:
            a_s, a_src = STRESS_AREA_MM2[d]
            val = n * a_s * STEEL_TENSION_MPA
            tag = "" if "placeholder" not in a_src else " (placeholder stress area)"
            return round(val, 1), "derived", (f"{n} x M{d:g} tension {a_s} mm2 ({a_src}) x {STEEL_TENSION_MPA:g} MPa "
                                              f"(arm_cup_checks.md steel tension allowable, EST){tag}")
    if via in ("CT-EPOXY", "CT-CA", "CT-A-PROP-ADAPTER", "CT-HW-SEATED", "CT-SERVO-SPLINE") and area_mm2 is not None:
        foam = any("XPS" in (p.get("material") or "") for p in (parent, child))
        if foam:
            tau, src = XPS_SHEAR_KPA * 1e-3, "foam_103.md XPS shear 86 kPa (EST)"
        else:
            tau, src = BOND_TAU_MPA, BOND_TAU_SRC
        ca = " (CA assumed as strong as epoxy: no CA allowable in the source)" if via == "CT-CA" and not foam else ""
        return round(tau * area_mm2, 1), "derived", f"contact area {area_mm2:.0f} mm2 (measured on the meshes) x {src}{ca}"
    return None, "placeholder", f"placeholder - not from source: no rule for {via}; set to the platform's own demand"
