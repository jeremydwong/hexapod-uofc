# /// script
# requires-python = ">=3.12"
# dependencies = ["numpy==2.5.3", "matplotlib==3.10.8", "meshcat"]
# ///
"""Build <output>/report.html from <output>/trajectory.csv: xyz plots, per-phase table, meshcat animation.

The animation is schematic: the Stewart geometry below is illustrative, not the PS-6TL-350's
real joint layout. Top-plate motion is the SDK-reported pose; the green rim is the command.
"""
from __future__ import annotations

import argparse
import base64
import csv
import html
import io
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
FPS = 30
# Illustrative geometry (m). Neutral top-joint height chosen so heave -165.8 mm stays above the base.
BASE_R, TOP_R, NEUTRAL_H, SPREAD = 0.62, 0.42, 0.46, np.deg2rad(12)
# Base plate rests on the floor grid (z = 0); lower ball joints sit on top of it, so no rod reaches the floor.
PLATE_T, JOINT_R = 0.04, 0.035
# Top plate is a disc wide enough to cover every upper joint; rods stop at ball joints under its underside.
TOP_T, TOP_PLATE_R = 0.03, TOP_R + 0.08
BASE_Z = PLATE_T + JOINT_R  # height of lower joint centres


def load(path):
    with path.open() as f:
        rows = list(csv.reader(f))
    header, data = rows[0], rows[1:]
    col = {name: i for i, name in enumerate(header)}
    num = lambda name: np.array([float(r[col[name]]) for r in data])
    return {name: (num(name) if name != "phase" else np.array([r[col[name]] for r in data])) for name in header}


def joints():
    """Lower joints in world frame; upper joints in the top-plate frame (hanging just under the plate)."""
    base, top = [], []
    for k in range(3):
        for sign in (-1, 1):
            a = np.deg2rad(120 * k) + sign * SPREAD
            base.append([BASE_R * np.cos(a), BASE_R * np.sin(a), BASE_Z])
            b = np.deg2rad(120 * k) + sign * (np.deg2rad(60) - SPREAD)
            top.append([TOP_R * np.cos(b), TOP_R * np.sin(b), -JOINT_R])
    return np.array(base), np.array(top)


def to_scene(sway, surge, heave):
    """SDK mm -> meshcat metres: x forward = surge, y left = -sway (sway is +right), z up = heave."""
    return np.array([surge, -sway, heave]) / 1000.


def leg_transform(p, q):
    """Unit cylinder (along y, centred) -> segment p..q, as (rigid transform, length along y).

    meshcat animation keyframes store only position + quaternion, so the length must go in a
    separate scale track; folding it into the matrix corrupts the quaternion.
    """
    d = q - p
    length = np.linalg.norm(d)
    y = d / length
    x = np.cross(y, [0, 0, 1.]) if abs(y[2]) < 0.99 else np.array([1., 0, 0])
    x /= np.linalg.norm(x)
    z = np.cross(x, y)
    T = np.eye(4)
    T[:3, :3] = np.c_[x, y, z]
    T[:3, 3] = (p + q) / 2
    return T, length


def spans(phase):
    """[(name, first index, last index)] for consecutive runs of the phase column, in order."""
    out, start = [], 0
    for i in range(1, len(phase) + 1):
        if i == len(phase) or phase[i] != phase[start]:
            out.append((str(phase[start]), start, i - 1))
            start = i
    return out


def png(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=110)
    return base64.b64encode(buf.getvalue()).decode()


def plots(d, out, test):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    t, sp = d["time_s"], spans(d["phase"])
    fig, ax = plt.subplots(4, 1, sharex=True, figsize=(11, 10))
    for i, axis in enumerate(["sway", "surge", "heave"]):
        ax[i].plot(t, d[f"command_{axis}_mm"], ":", lw=2, label="command")
        ax[i].plot(t, d[f"actual_{axis}_mm"], lw=1.2, label="actual (SDK)")
        ax[i].set_ylabel(f"{axis} (mm)")
    ax[0].legend(loc="upper right")
    for axis in ["roll", "pitch", "yaw"]:
        ax[3].plot(t, np.rad2deg(d[f"actual_{axis}_rad"]), label=axis)
    ax[3].set_ylabel("rotation (deg)"); ax[3].set_xlabel("time (s)"); ax[3].legend(loc="upper right")
    for a in ax:
        a.grid(alpha=.3)
        for _, i0, _ in sp:
            a.axvline(t[i0], color="grey", lw=.6)
    fig.tight_layout()
    fig.savefig(out / "report_xyz.png", dpi=110)
    whole = png(fig)

    fig2, ax2 = plt.subplots(2, 1, sharex=True, figsize=(11, 6))
    for k, axis in enumerate(["surge", "sway"]):
        ax2[k].plot(t[test], d[f"reference_{axis}_mm"][test], "--", label="reference")
        ax2[k].plot(t[test], d[f"command_{axis}_mm"][test], ":", lw=2, label="command")
        ax2[k].plot(t[test], d[f"actual_{axis}_mm"][test], label="actual (SDK)")
        ax2[k].set_ylabel(f"{axis} (mm)"); ax2[k].grid(alpha=.3)
        for name, i0, _ in sp:
            if test[i0]:
                ax2[k].axvline(t[i0], color="grey", lw=.6)
                if k == 0:
                    ax2[k].text(t[i0], ax2[k].get_ylim()[1], f" {name}", fontsize=8, color="grey", va="top")
    ax2[0].legend(loc="lower right"); ax2[1].set_xlabel("time (s)")
    ax2[0].set_title("Test sequence (surge + front, sway + right)", pad=14)
    fig2.tight_layout()
    return whole, png(fig2)


def animation(d):
    import meshcat
    import meshcat.geometry as g
    import meshcat.transformations as tf
    from meshcat.animation import Animation
    vis = meshcat.Visualizer()
    vis.delete()
    base, top = joints()
    slate, steel = g.MeshLambertMaterial(color=0x40444c), g.MeshLambertMaterial(color=0x6f737a)
    upright = tf.rotation_matrix(np.pi / 2, [1, 0, 0])  # meshcat cylinders run along y; stand them on z
    vis["base"].set_object(g.Cylinder(PLATE_T, BASE_R + 0.08), slate)
    vis["base"].set_transform(tf.translation_matrix([0, 0, PLATE_T / 2]) @ upright)
    for j in range(6):
        vis[f"joints/{j}"].set_object(g.Sphere(JOINT_R), steel)
        vis[f"joints/{j}"].set_transform(tf.translation_matrix(base[j]))
        vis[f"top/joints/{j}"].set_object(g.Sphere(JOINT_R), steel)
        vis[f"top/joints/{j}"].set_transform(tf.translation_matrix(top[j]))
        vis[f"legs/{j}"].set_object(g.Cylinder(1.0, 0.018), g.MeshLambertMaterial(color=0xc9ccd1))
    vis["top/plate"].set_object(g.Cylinder(TOP_T, TOP_PLATE_R), g.MeshLambertMaterial(color=0xd9a441))
    vis["top/plate"].set_transform(tf.translation_matrix([0, 0, TOP_T / 2]) @ upright)
    vis["top/forward"].set_object(g.Box([0.2, 0.04, 0.02]), g.MeshLambertMaterial(color=0xc0392b))
    vis["top/forward"].set_transform(tf.translation_matrix([TOP_PLATE_R - 0.12, 0, TOP_T + 0.01]))
    # Command ghost: a wider, thinner disc centred in the plate's thickness, so only a rim shows and
    # no face is coplanar with the plate (coplanar faces z-fight, which is what made the plate flicker).
    vis["ghost"].set_object(g.Cylinder(TOP_T * 0.6, TOP_PLATE_R + 0.03),
                            g.MeshLambertMaterial(color=0x2ecc71, opacity=0.6, transparent=True))

    t = d["time_s"]
    anim = Animation(default_framerate=FPS)
    z0 = BASE_Z + NEUTRAL_H
    for f, tk in enumerate(np.arange(0, t[-1], 1 / FPS)):
        i = min(np.searchsorted(t, tk), len(t) - 1)
        a = to_scene(d["actual_sway_mm"][i], d["actual_surge_mm"][i], d["actual_heave_mm"][i])
        c = to_scene(d["command_sway_mm"][i], d["command_surge_mm"][i], d["command_heave_mm"][i])
        R = tf.euler_matrix(d["actual_roll_rad"][i], -d["actual_pitch_rad"][i], -d["actual_yaw_rad"][i])
        T_top = tf.translation_matrix(a + [0, 0, z0]) @ R
        T_ghost = tf.translation_matrix(c + [0, 0, z0 + TOP_T / 2]) @ upright
        legs = [leg_transform(base[j], (T_top @ np.r_[top[j], 1.])[:3]) for j in range(6)]
        if f == 0:  # static pose shown before play is pressed
            vis["top"].set_transform(T_top)
            vis["ghost"].set_transform(T_ghost)
            for j, (T, length) in enumerate(legs):
                vis[f"legs/{j}"].set_transform(T @ np.diag([1., length, 1., 1.]))
        with anim.at_frame(vis, f) as frame:
            frame["top"].set_transform(T_top)
            frame["ghost"].set_transform(T_ghost)
            for j, (T, length) in enumerate(legs):
                frame[f"legs/{j}"].set_transform(T)
                frame[f"legs/{j}"].set_property("scale", "vector3", [1., float(length), 1.])
    vis.set_animation(anim, play=False)
    return vis.static_html()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "output")
    args = parser.parse_args()
    d = load(args.output / "trajectory.csv")
    t, ph = d["time_s"], d["phase"]
    test = ~np.isin(ph, ["lift", "lower", "park"])
    whole_png, test_png = plots(d, args.output, test)
    dt = np.diff(t) * 1000
    xyz = lambda kind: np.c_[d[f"{kind}_sway_mm"], d[f"{kind}_surge_mm"], d[f"{kind}_heave_mm"]]
    actual, reference = xyz("actual"), xyz("reference")
    rpy = np.rad2deg(np.c_[d["actual_roll_rad"], d["actual_pitch_rad"], d["actual_yaw_rad"]])
    fmt = lambda v: " / ".join(f"{x:+.2f}" for x in v)
    phase_rows = []
    for name, i0, i1 in spans(ph):
        target = reference[i1]
        phase_rows.append(
            f"<tr><td>{html.escape(name)}</td><td>{t[i0]:.1f}–{t[i1]:.1f} s</td><td>{fmt(target)}</td>"
            f"<td>{fmt(actual[i1])}</td><td>{np.max(np.abs(actual[i1] - target)):.2f}</td>"
            f"<td>{np.max(np.abs(reference[i0:i1 + 1] - actual[i0:i1 + 1])):.2f}</td></tr>")
    stats = [
        ("Max |reference − actual|, test phases", f"{np.max(np.abs(reference[test] - actual[test])):.2f} mm"),
        ("Max |heave| during test phases", f"{np.max(np.abs(actual[test, 2])):.2f} mm"),
        ("Max |roll, pitch, yaw|, whole run", f"{np.max(np.abs(rpy)):.3f}°"),
        ("Heave range, whole run", f"{actual[:, 2].min():.2f} to {actual[:, 2].max():.2f} mm"),
        ("Loop period", f"mean {dt.mean():.1f} ms, max {dt.max():.1f} ms (nominal 10)"),
        ("Samples", f"{len(t)} over {t[-1]:.1f} s"),
    ]
    sequence = " → ".join(html.escape(n) for n, _, _ in spans(ph))
    scene = animation(d)
    page = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Motion Test Report</title>
<style>
:root{{--bg:#fff;--fg:#1d1d1f;--muted:#666;--line:#ddd}}
@media (prefers-color-scheme:dark){{:root{{--bg:#16181c;--fg:#e8e8ea;--muted:#9a9aa0;--line:#333}}}}
body{{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;max-width:1100px;margin:0 auto;padding:16px}}
h1{{margin-bottom:0}} .muted{{color:var(--muted)}} table{{border-collapse:collapse;margin:8px 0 20px}}
td,th{{border-bottom:1px solid var(--line);padding:4px 14px 4px 0;text-align:left}}
img{{max-width:100%;background:#fff;border-radius:6px}} .scroll{{overflow-x:auto}}
iframe{{width:100%;height:620px;border:1px solid var(--line);border-radius:6px}} code{{font-size:13px}}
</style></head><body>
<h1>M10 motion test</h1>
<p class="muted">ForceSeatDI over USB, controller S/N 5F0051-000150-344335-353720 · run by
<code>examples/LevelMove_Python/test_from_park.py</code> · data <code>{html.escape(args.output.name)}/trajectory.csv</code></p>
<p>Sequence: {sequence}. All rotations commanded zero. Positions are what the SDK reports;
there is no external measurement. Sway + is right, surge + is front.</p>
<h2>Summary</h2><table>{''.join(f'<tr><td>{k}</td><td><b>{v}</b></td></tr>' for k, v in stats)}</table>
<h2>Phases</h2><div class="scroll"><table><tr><th>phase</th><th>time</th><th>target sway / surge / heave (mm)</th>
<th>actual at end (mm)</th><th>end error (mm)</th><th>max tracking error (mm)</th></tr>{''.join(phase_rows)}</table></div>
<h2>Test sequence</h2><img src="data:image/png;base64,{test_png}" alt="surge and sway: reference, command and actual">
<h2>X / Y / Z over the whole run</h2><img src="data:image/png;base64,{whole_png}" alt="sway, surge, heave, rotations vs time">
<h2>Animation</h2>
<p class="muted">Open the <i>Animations</i> folder in the meshcat panel (top right) and press play. Gold plate + red nose =
SDK-reported pose (red points forward/surge); green rim = command (it only separates from the plate when tracking lags). Real timing ({t[-1]:.0f} s).
Leg geometry is schematic, not the PS-6TL-350's real joint layout.</p>
<iframe srcdoc="{html.escape(scene)}"></iframe>
</body></html>"""
    path = args.output / "report.html"
    path.write_text(page, encoding="utf-8")
    print(f"Wrote {path} ({path.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
