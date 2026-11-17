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
    if not parts:  # point_mass (schema 0.4): no extent, so a token inertia keeps the body well posed
        return np.eye(3) * 1e-9
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
    from .design import load_standards
    std_h = float(load_standards()["sim"]["drop_height_m"]["value"])

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
        return [CheckResult("T2.sim", SKIP, "mujoco not installed; dynamic simulation skipped", STD + "drop_height_m")]

    cfg = std["sim"]
    dur = float(cfg["duration_s"]["value"])
    v_max = float(cfg["rest_speed_max_mps"]["value"])
    tip_max = float(cfg["tip_angle_max_deg"]["value"])

    try:
        xml, info = _build(design)
        model = mujoco.MjModel.from_xml_string(xml)
    except Exception as e:  # noqa: BLE001
        msg = f"could not build simulation model: {e}"
        return [CheckResult("T2.sim_stable", FAIL, msg, STD + "duration_s"),
                CheckResult("T2.sim_drop_loads", SKIP, "no model", STD + "drop_height_m", {"parts": []}),
                CheckResult("T2.sim_rest", SKIP, "no model", STD + "drop_height_m")]
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
        d = {"peak_n": round(peak, 2), "joint": label}
        if a.get("rating_basis") == "placeholder":
            res.append(CheckResult("T2.sim_drop_loads", SKIP, f"{label}: carries {peak:.1f} N; rating is a placeholder, not checked",
                                   STD + "landing_load_factor", d))
            continue
        if rated is None:
            res.append(CheckResult("T2.sim_drop_loads", FAIL, f"{label}: peak {peak:.1f} N in drop test, no rated_load_n given",
                                   STD + "landing_load_factor", d))
        elif peak > rated:
            res.append(CheckResult("T2.sim_drop_loads", FAIL, f"{label}: peak {peak:.1f} N in drop test exceeds rating {rated} N",
                                   STD + "landing_load_factor", d))
        else:
            res.append(CheckResult("T2.sim_drop_loads", PASS, f"{label}: peak {peak:.1f} N <= {rated} N in drop test",
                                   STD + "landing_load_factor", d))

    # b. rest
    root = info["root"] or design.components[0]["id"]
    if nan:
        res.append(CheckResult("T2.sim_rest", SKIP, "simulation went unstable", STD + "drop_height_m"))
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
        res.append(CheckResult("T2.sim_stable", FAIL, "simulation produced NaN/inf states", STD + "drop_height_m"))
    elif warn_count:
        res.append(CheckResult("T2.sim_stable", FAIL, f"MuJoCo raised {warn_count} instability warning(s) during the run", STD + "drop_height_m"))
    else:
        res.append(CheckResult("T2.sim_stable", PASS, f"{n_steps} steps, no NaN or solver warnings", STD + "drop_height_m"))
    return res


# ---------------------------------------------------------------- joint load cases for the structural check (fea.py)
def _weld_loads(model, data, mujoco, eq_index):
    """{weld k: (force on parent, torque on parent about the child's CG)} in world axes, from the active constraints.
    Verified on a two-body model: translational rows are the force on body1 (the parent) acting at body2's origin
    (the child CG here); rotational rows are twice the torque (MuJoCo's quaternion residual), world axes."""
    out = {}
    nc = data.nefc
    if not nc:
        return out
    rows = np.nonzero(data.efc_type[:nc] == mujoco.mjtConstraint.mjCNSTR_EQUALITY)[0]
    ids, f = data.efc_id[:nc][rows], data.efc_force[:nc][rows]
    for eid, k in eq_index.items():
        sel = f[ids == eid]
        if len(sel) >= 6:
            out[k] = (sel[:3].copy(), sel[3:6].copy() / 2.0)
        elif len(sel) >= 3:
            out[k] = (sel[:3].copy(), np.zeros(3))
    return out


def joint_load_cases(design: Design) -> dict:
    """Joint loads for two cases, per attachment id, in the design (body) frame:

    landing  the drop test: each joint at the instant of its largest force (an envelope over time);
    thrust   held at the root, gravity on, every motor at max_thrust_n along its axis (steady state).

    Each entry: {"force_n": force on the PARENT from the child, "torque_nm": torque on the parent about "at_mm",
    "at_mm": the child's CG}. The child feels the opposite force and torque.
    """
    import mujoco
    from .design import load_standards
    cfg = load_standards()["sim"]
    xml, info = _build(design)
    r, _, _ = _landing_rotation(design)
    welds = info["welds"]
    cg = {}
    for c in design.components:
        cg[c["id"]] = component_cg(c, component_parts(c, design.base_dir))

    def setup(model):
        eq_index = {mujoco.mj_name2id(model, mujoco.mjtObj.mjOBJ_EQUALITY, n): k for k, (n, _, _) in enumerate(welds)}
        return eq_index

    def record(k, F_w, T_w, R):
        a = welds[k][2]
        return {"force_n": (R.T @ F_w).round(4).tolist(), "torque_nm": (R.T @ T_w).round(5).tolist(),
                "at_mm": np.asarray(cg[a["child"]], float).round(3).tolist()}

    out = {"landing": {}, "thrust": {}}
    # landing: the drop test, peak force per joint
    model = mujoco.MjModel.from_xml_string(xml)
    data = mujoco.MjData(model)
    eq_index = setup(model)
    parent_bid = {k: int(model.eq_obj1id[eid]) for eid, k in eq_index.items()}
    peak = np.zeros(len(welds))
    n_steps = int(round(float(cfg["duration_s"]["value"]) / model.opt.timestep))
    for _ in range(n_steps):
        mujoco.mj_step(model, data)
        for k, (F_w, T_w) in _weld_loads(model, data, mujoco, eq_index).items():
            n = float(np.linalg.norm(F_w))
            if n > peak[k]:
                peak[k] = n
                R = data.xmat[parent_bid[k]].reshape(3, 3)
                out["landing"][welds[k][2].get("id") or welds[k][1]] = record(k, F_w, T_w, R)

    # thrust: a static solve (MuJoCo's soft welds do not settle under steady thrust on this model)
    out["thrust"] = _static_joint_loads(design, cg, welds)
    return out


def _static_joint_loads(design: Design, cg: dict, welds) -> dict:
    """Hover at full thrust, held at the root: every motor at max_thrust_n along its axis plus gravity (the hover
    attitude is the landing attitude, so 'down' is minus the landing up-axis). Each joint is a 6-DOF spring of the
    same stiffness between rigid parts (rotational stiffness = translational x (50 mm)^2), solved linearly; where
    joints form loops the load splits by that uniform stiffness. Returns joint loads like joint_load_cases."""
    _, _, up = _landing_rotation(design)
    ids = [c["id"] for c in design.components]
    idx = {cid: i for i, cid in enumerate(ids)}
    n = len(ids)
    X = np.array([np.asarray(cg[cid], float) / 1000 for cid in ids])  # m
    kt, L = 1.0, 0.05
    kr = kt * L * L
    K = np.zeros((6 * n, 6 * n))
    blocks = []
    for k, (_, _, a) in enumerate(welds):
        i, j = idx[a["parent"]], idx[a["child"]]
        p = X[j]                                         # spring at the child's CG (as MuJoCo's weld)
        # relative motion at p: u_j - (u_i + th_i x (p - x_i)); rotation th_j - th_i
        B = np.zeros((6, 6 * n))
        B[:3, 6 * j:6 * j + 3] = np.eye(3)
        B[:3, 6 * i:6 * i + 3] = -np.eye(3)
        r = p - X[i]
        B[:3, 6 * i + 3:6 * i + 6] = np.array([[0, r[2], -r[1]], [-r[2], 0, r[0]], [r[1], -r[0], 0]])  # -(th x r)
        B[3:, 6 * j + 3:6 * j + 6] = np.eye(3)
        B[3:, 6 * i + 3:6 * i + 6] = -np.eye(3)
        D = np.diag([kt] * 3 + [kr] * 3)
        K += B.T @ D @ B
        blocks.append((k, B, D))
    f = np.zeros(6 * n)
    for c in design.components:
        i = idx[c["id"]]
        f[6 * i:6 * i + 3] += -up * float(c["mass_g"]) / 1000 * G
        prop = c.get("propulsion") if c["type"] == "motor" else None
        if prop:
            ax = np.asarray(prop["axis"], float)
            f[6 * i:6 * i + 3] += ax / np.linalg.norm(ax) * float(prop["max_thrust_n"])
    root = idx[design.data.get("root") or ids[0]]
    free = np.ones(6 * n, bool)
    free[6 * root:6 * root + 6] = False
    u = np.zeros(6 * n)
    Kf = K[np.ix_(free, free)]
    u[free] = np.linalg.lstsq(Kf, f[free], rcond=None)[0]
    out = {}
    for k, B, D in blocks:
        a = welds[k][2]
        s_ = D @ (B @ u)                                 # = force/moment on the PARENT (the child is pulled back by -s_)
        out[a.get("id") or welds[k][1]] = {"force_n": s_[:3].round(4).tolist(), "torque_nm": s_[3:].round(5).tolist(),
                                           "at_mm": np.asarray(cg[a["child"]], float).round(3).tolist()}
    return out
