"""Vortex-lattice neutral point of the lifting surfaces (wings and tails only), via AeroSandbox.

Everything is body frame, mm in and out (x aft, y right, z up, as the rest of the platform); AeroSandbox runs in metres.
A surface is a list of sections (LE point mm, chord mm, twist deg), ordered along its local span (left to right for a
wing). Sections are laid out with cosine spacing, so the VLM runs with one spanwise panel per section interval.

Method: `asb.VortexLatticeMethod` at two angles of attack (default 0 and 2 deg), CL_alpha and Cm_alpha by difference,
x_np = x_ref - Cm_alpha / CL_alpha * c_ref (the same result as AeroSandbox's own `x_np` from
`run_with_stability_derivatives`). Thin symmetric sections: a VLM uses only the camber line, and camber moves the
zero-lift angle, not the neutral point. NOT modelled: propellers, fuselage or pod, viscous effects, flexibility.
"""
from __future__ import annotations

import math
import time

import numpy as np

from .geometry import rotation_matrix

DEFAULT_SPEED_MPS = 15.0


def _import_asb():
    """The one import point of AeroSandbox; tests replace it to exercise the fallback."""
    import aerosandbox as asb  # noqa: WPS433 (optional dependency, imported lazily)
    return asb


def available() -> bool:
    try:
        _import_asb()
    except Exception:  # missing, or broken by an incompatible install
        return False
    return True


def _cosine_fractions(n: int) -> np.ndarray:
    """n + 1 stations in [0, 1], clustered at both ends."""
    return (1 - np.cos(np.linspace(0, math.pi, n + 1))) / 2


def _section_twist_chord(direction: np.ndarray, chord: float) -> tuple[float, float]:
    """AeroSandbox sections have the chord along x and a twist about y (positive nose up, TE moves down)."""
    return math.degrees(math.atan2(-direction[2], direction[0])), chord * math.hypot(direction[0], direction[2])


def lifting_surface_sections(component: dict, pose: np.ndarray | None = None, per_semispan: int = 8) -> list[tuple]:
    """Sections of a schema lifting_surface (both mirrored halves as one wing, left tip to right tip), after the
    component transform and, if given, the 4x4 articulation pose of its subtree."""
    ls = component["geometry"]["lifting_surface"]
    mirrored = ls.get("mirrored", True)
    semi = ls["span"] / 2 if mirrored else ls["span"]
    cr, ct = ls["root_chord"], ls["tip_chord"]
    sweep = math.tan(math.radians(ls.get("sweep_le_deg", 0)))
    dihedral = math.tan(math.radians(ls.get("dihedral_deg", 0)))
    r = rotation_matrix(component.get("rotation_deg"))
    pos = np.array(component["position"], dtype=float)
    if pose is not None:
        r_tot, t_tot = pose[:3, :3] @ r, pose[:3, :3] @ pos + pose[:3, 3]
    else:
        r_tot, t_tot = r, pos
    direction = r_tot @ np.array([1.0, 0.0, 0.0])
    fr = _cosine_fractions(per_semispan)
    ys = list(semi * fr)  # root -> tip, local y >= 0
    sides = [-1, 1] if mirrored else [1]
    out = []
    for sign in sides:
        seq = ys[::-1] if sign < 0 else ys  # left tip -> root, then root -> right tip
        for y in seq:
            if sign > 0 and mirrored and y == 0.0:
                continue  # root station already emitted by the left half
            chord = cr + (ct - cr) * y / semi
            local = np.array([y * sweep, sign * y, y * dihedral])
            tw, ch = _section_twist_chord(direction, chord)
            out.append(((r_tot @ local + t_tot).tolist(), ch, tw))
    return out


def strip_sections(strip_data: dict, pose: np.ndarray | None = None, n_intervals: int = 16) -> list[tuple]:
    """Sections of a mesh wing from `geometry.strip_planform`'s measured strips: LE x and chord interpolated linearly
    between the strip centres (strips with no material are skipped and bridged), end values held out to the measured
    span extent. Span axis y (wing) or z (fin), ordered by increasing coordinate."""
    centres = np.array(strip_data["centres"])
    chord = np.array(strip_data["chord"])
    le = np.array(strip_data["le"])
    ok = chord > 0
    if ok.sum() < 2:
        raise ValueError("fewer than two measured strips")
    lo, hi, axis = strip_data["lo"], strip_data["hi"], strip_data["axis"]
    s = lo + (hi - lo) * _cosine_fractions(n_intervals)
    c_s = np.interp(s, centres[ok], chord[ok])
    le_s = np.interp(s, centres[ok], le[ok])
    direction = (pose[:3, :3] @ np.array([1.0, 0.0, 0.0])) if pose is not None else np.array([1.0, 0.0, 0.0])
    out = []
    for si, ci, li in zip(s, c_s, le_s):
        p = np.zeros(3)
        p[0], p[axis] = li, si
        if pose is not None:
            p = pose[:3, :3] @ p + pose[:3, 3]
        tw, ch = _section_twist_chord(direction, float(ci))
        out.append((p.tolist(), ch, tw))
    return out


def vlm_neutral_point(surfaces: list[list[tuple]], x_ref_mm: float, c_ref_mm: float, s_ref_mm2: float,
                      speed_mps: float = DEFAULT_SPEED_MPS, z_ref_mm: float = 0.0, chordwise: int = 6,
                      alphas_deg: tuple[float, float] = (0.0, 2.0)) -> dict:
    """Neutral point of the given surfaces (body frame, mm). Raises ImportError when AeroSandbox is missing and
    ValueError when the model gives no positive lift slope. Returns x_np_mm, cl_alpha, cm_alpha (per rad, about
    x_ref, normalised by s_ref and c_ref), panels and seconds."""
    asb = _import_asb()
    t0 = time.perf_counter()
    af = asb.Airfoil("naca0012")
    wings = []
    for i, secs in enumerate(surfaces):
        wings.append(asb.Wing(name=f"surface{i}", xsecs=[
            asb.WingXSec(xyz_le=[v / 1000 for v in p], chord=c / 1000, twist=tw, airfoil=af) for p, c, tw in secs]))
    xyz_ref = [x_ref_mm / 1000, 0.0, z_ref_mm / 1000]
    airplane = asb.Airplane(name="vlm", wings=wings, xyz_ref=xyz_ref, c_ref=c_ref_mm / 1000,
                            s_ref=s_ref_mm2 / 1e6, b_ref=1.0)
    res, panels = [], 0
    for a in alphas_deg:
        vlm = asb.VortexLatticeMethod(airplane, asb.OperatingPoint(velocity=speed_mps, alpha=a), xyz_ref=xyz_ref,
                                      spanwise_resolution=1, chordwise_resolution=chordwise)
        res.append(vlm.run())
        panels = len(vlm.vortex_centers)
    da = math.radians(alphas_deg[1] - alphas_deg[0])
    cl_a = float(res[1]["CL"] - res[0]["CL"]) / da
    cm_a = float(res[1]["Cm"] - res[0]["Cm"]) / da
    if not (math.isfinite(cl_a) and math.isfinite(cm_a)) or cl_a <= 0:
        raise ValueError(f"VLM gave CL_alpha {cl_a:.3g} per rad")
    return {"x_np_mm": x_ref_mm - cm_a / cl_a * c_ref_mm, "cl_alpha": cl_a, "cm_alpha": cm_a, "panels": panels,
            "seconds": time.perf_counter() - t0}
