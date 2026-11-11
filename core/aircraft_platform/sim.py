"""MuJoCo drop-test simulation: dynamic evidence that the design holds together, stands and stays stable.

Units in the MJCF are metres/kg. Every component is a free body welded to its attachment parent so the
constraint force in each weld is the joint load. Components of one aircraft do not collide with each
other (tier 1 owns self-clipping); they collide only with the ground. Propellers (swept discs) never collide.
"""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np

from .design import Design, CheckResult, PASS, FAIL, WARN, SKIP
from .geometry import component_parts
from .mass import component_cg

G = 9.81
STD = "design-standards.yaml#"
TIMESTEP = 0.001


def _is_tailsitter(design: Design) -> bool:
    return design.data.get("morphology", {}).get("vtol_method") == "tailsitter"


def _landing_rotation(design: Design) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(R body->world, quaternion wxyz, landing 'up' axis in the body frame)."""
    if _is_tailsitter(design):
        # +90 deg about y maps body -x onto world +z
        c = math.cos(math.radians(45))
        r = np.array([[0, 0, 1], [0, 1, 0], [-1, 0, 0]], dtype=float)
        return r, np.array([c, 0, c, 0]), np.array([-1.0, 0, 0])
    return np.eye(3), np.array([1.0, 0, 0, 0]), np.array([0.0, 0, 1.0])


def _vec(v) -> str:
    return " ".join(f"{x:.9g}" for x in v)


def _component_inertia(mass_kg: float, parts, cg_mm: np.ndarray) -> np.ndarray:
    """Inertia (kg m^2) about the component CG, body-aligned axes, from the convex parts."""
    vols = np.array([max(p.convex_hull.volume, 1e-9) for p in parts])
    inertia = np.zeros((3, 3))
    for p, v in zip(parts, vols):
        pm = mass_kg * v / vols.sum()
        q = p.convex_hull.copy()
        q.density = pm / max(q.volume, 1e-9)           # kg/mm^3 -> moment_inertia in kg mm^2
        d = q.center_mass - cg_mm
        inertia += q.moment_inertia + pm * (np.dot(d, d) * np.eye(3) - np.outer(d, d))
    inertia *= 1e-6                                     # kg mm^2 -> kg m^2
    # keep it strictly positive definite and physically valid
    w, v = np.linalg.eigh(inertia)
    w = np.maximum(w, 1e-9)
    return v @ np.diag(w) @ v.T


def _build(design: Design):
    """Returns (xml, info) where info maps attachment ids to equality names."""
    r, quat, up_body = _landing_rotation(design)
    std_h = 0.3
    try:
        from .design import load_standards
        std_h = float(load_standards()["sim"]["drop_height_m"]["value"])
    except Exception:
        pass

    comps = []
    for c in design.components:
        parts = component_parts(c, design.base_dir)
        cg = component_cg(c, parts)
        comps.append((c, parts, cg))

    # lowest colliding point in landing orientation -> release height
    low = math.inf
    for c, parts, _ in comps:
        if c["type"] == "propeller":
            continue
        for p in parts:
            low = min(low, float((p.vertices @ r.T)[:, 2].min()) / 1000)
    if not math.isfinite(low):
        low = 0.0
    shift = std_h - low

    mesh_xml, body_xml = [], []
    for c, parts, cg in comps:
        cid = c["id"]
        mass = float(c["mass_g"]) / 1000
        pos = r @ (cg / 1000) + np.array([0, 0, shift])
        coll = c["type"] != "propeller"
        geoms = []
        for i, p in enumerate(parts):
            hull = p.convex_hull
            verts = (hull.vertices - cg) / 1000
            name = f"{cid}_m{i}"
            mesh_xml.append(f'    <mesh name="{name}" vertex="{_vec(verts.ravel())}"/>')
            if coll:
                geoms.append(f'      <geom type="mesh" mesh="{name}" contype="2" conaffinity="0" friction="1 0.005 0.0001"/>')
            else:
                geoms.append(f'      <geom type="mesh" mesh="{name}" contype="0" conaffinity="0" rgba="0.9 0.6 0.2 0.3"/>')
        i3 = _component_inertia(mass, parts, cg)
        fi = [i3[0, 0], i3[1, 1], i3[2, 2], i3[0, 1], i3[0, 2], i3[1, 2]]
        body_xml.append(
            f'    <body name="{cid}" pos="{_vec(pos)}" quat="{_vec(quat)}">\n'
            f'      <freejoint name="{cid}_free"/>\n'
            f'      <inertial pos="0 0 0" mass="{mass:.9g}" fullinertia="{_vec(fi)}"/>\n'
            + "\n".join(geoms) + "\n    </body>")

    ids = {c["id"] for c in design.components}
    eq_xml, eq_names = [], []
    for k, a in enumerate(design.data.get("attachments", [])):
        if a["parent"] not in ids or a["child"] not in ids:
            continue
        name = f"weld_{k}"
        label = a.get("id") or f"{a['parent']}->{a['child']}"
        eq_names.append((name, label, a))
        eq_xml.append(f'    <weld name="{name}" body1="{a["parent"]}" body2="{a["child"]}" solref="0.004 1"/>')

    xml = f"""<mujoco model="{design.id}">
  <compiler angle="degree"/>
  <option timestep="{TIMESTEP}" gravity="0 0 -{G}"/>
  <asset>
{chr(10).join(mesh_xml)}
  </asset>
  <worldbody>
    <geom name="ground" type="plane" size="5 5 0.1" contype="1" conaffinity="2" friction="1 0.005 0.0001"/>
{chr(10).join(body_xml)}
  </worldbody>
  <equality>
{chr(10).join(eq_xml)}
  </equality>
</mujoco>
"""
    return xml, {"welds": eq_names, "up_body": up_body, "root": design.data.get("root")}


def build_mjcf(design: Design) -> str:
    return _build(design)[0]


def export_mjcf(design: Design, out_path) -> Path:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_mjcf(design))
    return out


def tier2_sim(design: Design, std: dict, mp: dict) -> list[CheckResult]:
    try:
        import mujoco
    except ImportError:
        return [CheckResult("T2.sim", SKIP, "mujoco not installed; dynamic simulation skipped")]

    cfg = std.get("sim", {})
    dur = float(cfg.get("duration_s", {}).get("value", 2.0))
    v_max = float(cfg.get("rest_speed_max_mps", {}).get("value", 0.05))
    tip_max = float(cfg.get("tip_angle_max_deg", {}).get("value", 30.0))

    try:
        xml, info = _build(design)
        model = mujoco.MjModel.from_xml_string(xml)
    except Exception as e:  # noqa: BLE001
        msg = f"could not build simulation model: {e}"
        return [CheckResult("T2.sim_stable", FAIL, msg, STD + "sim"),
                CheckResult("T2.sim_drop_loads", SKIP, "no model"),
                CheckResult("T2.sim_rest", SKIP, "no model")]
    data = mujoco.MjData(model)
    mujoco.mj_forward(model, data)

    welds = info["welds"]
    peaks = np.zeros(len(welds))
    eq_index = {mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_EQUALITY, n): k for k, (n, _, _) in enumerate(welds)}
    warn_count = 0
    nan = False
    n_steps = int(round(dur / model.opt.timestep))
    for _ in range(n_steps):
        mujoco.mj_step(model, data)
        if not np.all(np.isfinite(data.qpos)) or not np.all(np.isfinite(data.qvel)):
            nan = True
            break
        nc = data.nefc
        if nc:
            eqrows = np.nonzero(data.efc_type[:nc] == mujoco.mjtConstraint.mjCNSTR_EQUALITY)[0]
            ids = data.efc_id[:nc][eqrows]
            f = data.efc_force[:nc][eqrows]
            for eid, k in eq_index.items():
                sel = ids == eid
                if sel.any():
                    fv = f[sel][:3]  # translational rows come first
                    peaks[k] = max(peaks[k], float(np.linalg.norm(fv)))
    warn_count = int(sum(data.warning[i].number for i in range(len(data.warning))))

    res: list[CheckResult] = []
    # a. drop loads
    for k, (name, label, a) in enumerate(welds):
        peak = float(peaks[k])
        rated = a.get("rated_load_n")
        d = {"peak_n": round(peak, 2)}
        if rated is None:
            res.append(CheckResult("T2.sim_drop_loads", WARN, f"{label}: peak {peak:.1f} N in drop test, no rated_load_n given",
                                   STD + "sim", d))
        elif peak > rated:
            res.append(CheckResult("T2.sim_drop_loads", FAIL, f"{label}: peak {peak:.1f} N in drop test exceeds rating {rated} N",
                                   STD + "sim", d))
        else:
            res.append(CheckResult("T2.sim_drop_loads", PASS, f"{label}: peak {peak:.1f} N <= {rated} N in drop test",
                                   STD + "sim", d))

    # b. rest
    root = info["root"] or design.components[0]["id"]
    if nan:
        res.append(CheckResult("T2.sim_rest", SKIP, "simulation went unstable", STD + "sim"))
    else:
        bid = mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_BODY, root)
        vel = np.zeros(6)
        mujoco.mj_objectVelocity(model, data, mujoco.mjtObj.mjOBJ_BODY, bid, vel, 0)
        speed = float(np.linalg.norm(vel[3:]))
        rmat = data.xmat[bid].reshape(3, 3)
        up = rmat @ info["up_body"]
        angle = math.degrees(math.acos(max(-1.0, min(1.0, float(up[2])))))
        resting = speed < v_max
        d = {"speed_mps": round(speed, 4), "tilt_deg": round(angle, 1)}
        if angle >= tip_max:
            res.append(CheckResult("T2.sim_rest", FAIL,
                                   f"tipped over after drop: landing axis {angle:.0f} deg from vertical (limit {tip_max:.0f}), "
                                   f"speed {speed:.3f} m/s" + ("; tailsitter cannot stand on its landing gear"
                                                                if _is_tailsitter(design) else ""),
                                   STD + "tip_angle_max_deg", d))
        elif not resting:
            res.append(CheckResult("T2.sim_rest", FAIL,
                                   f"not at rest after {dur:.1f} s: speed {speed:.3f} m/s >= {v_max} m/s (tilt {angle:.0f} deg)",
                                   STD + "rest_speed_max_mps", d))
        else:
            res.append(CheckResult("T2.sim_rest", PASS,
                                   f"at rest after {dur:.1f} s: speed {speed:.3f} m/s, tilt {angle:.1f} deg from vertical",
                                   STD + "rest_speed_max_mps", d))

    # c. stability
    if nan:
        res.append(CheckResult("T2.sim_stable", FAIL, "simulation produced NaN/inf states", STD + "sim"))
    elif warn_count:
        res.append(CheckResult("T2.sim_stable", FAIL, f"MuJoCo raised {warn_count} instability warning(s) during the run", STD + "sim"))
    else:
        res.append(CheckResult("T2.sim_stable", PASS, f"{n_steps} steps, no NaN or solver warnings", STD + "sim"))
    return res
