"""RQ3 Sankey diagram (5 columns, fix channel encoded as ribbon color).

Reproduces and pins down the construction methodology of the paper's Sankey
figure (`RQ3_sankey_5col_nochannel`). The figure was originally produced
manually with an external tool and only committed as a static image; this
script rewrites it from the methodology reverse-engineered by audit so it is
fully reproducible.

Data source
-----------
../../labeled_dataset/symptom_fix_joined/cr_discussion_annotated_chunk_*.json
(330 CRs; the figure uses only the 128 CRs with `with_observed_fix`)

Construction rules (reverse-engineered by vector-geometry audit,
confirmed by independent recomputation)
----------------------------------------------------------------
* Unit of analysis = the 128 fixed CRs; all five columns are normalized to 128.
* Counting = **fractional multi-label counting**: each CR contributes a total
  weight of 1.0 per dimension, split evenly across that dimension's labels.
  E.g. fix_submodule=[wine, dxvk] => wine +0.5, dxvk +0.5.
* Inter-column flow = **within-CR joint**: left share x right share x channel
  share, accumulated per CR. This definition strictly guarantees:
  (1) each node's marginal = its fractional node value; (2) flow through every
  gap is conserved (=128); (3) each channel's color share = the data's channel
  distribution.
* The channel is NOT a separate column ("nochannel"); it is encoded as the
  ribbon color: blue=proton_update, green=community_fix, orange=third_party_fix.

Outputs (written to ./output/ next to this script)
--------------------------------------------------
* matplotlib: `RQ3_sankey_5col_nochannel.pdf` + `.png` (high-res, no Chrome needed, default)
* plotly    : `RQ3_sankey_5col_nochannel.html` (interactive; PDF/PNG export needs Chrome+kaleido)

dxvk grouping switch
--------------------
The codebook lists `dxvk-nvapi` as a subcomponent separate from `dxvk`. The
original figure merged the two into a single "dxvk" node without indicating so
in the label (whereas the adjacent vkd3d node is labeled "vkd3d(-proton)").
SUBMODULE_DXVK_MODE:
* "merge_label" (default): merge, rename node to "dxvk(-nvapi)", consistent
  with the vkd3d(-proton) convention.
* "split"      : dxvk-nvapi goes to "other Proton comp.", strictly following
  the codebook.
* "faithful"   : merge and keep the node named "dxvk", replicating the original
  figure exactly (including its known overestimate).

Usage
-----
    pip install matplotlib          # static high-res figures (recommended, no Chrome)
    pip install plotly kaleido      # only for the interactive HTML / plotly export
    python rq3_sankey.py
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

# ----------------------------------------------------------------------------- config
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR.parent.parent / "labeled_dataset" / "symptom_fix_joined"
OUT_DIR = SCRIPT_DIR / "output"
OUT_STEM = "RQ3_sankey_5col_nochannel"

RENDER_MATPLOTLIB = True          # high-res static PDF+PNG (no Chrome needed)
RENDER_PLOTLY = True              # interactive HTML (+ PDF/PNG export if Chrome available)

SUBMODULE_DXVK_MODE = "merge_label"   # "merge_label" | "split" | "faithful"

# colors (sampled from the original figure's PDF fill RGB)
NODE_COLOR = "#3F4F60"                 # node bars: dark slate
CHANNEL_COLORS = {
    "proton_update":  "#5E91C4",       # blue
    "community_fix":  "#73B36C",       # green
    "third_party_fix": "#E59A57",      # orange
}
CHANNEL_LEGEND = [("proton_update", "Proton update"),
                  ("community_fix", "Community fix"),
                  ("third_party_fix", "Third-party fix")]
LINK_ALPHA = 0.55

COLUMN_TITLES = ["Symptom", "Root cause", "Fix pattern", "Fix management", "Fix submodule"]

# layout (matplotlib): large canvas + large fonts for readability
FIG_W_IN, FIG_H_IN, FIG_DPI = 20.0, 10.5, 200
FS_LABEL, FS_TITLE, FS_LEGEND = 13, 18, 14
COL_X = [0.115, 0.265, 0.45, 0.665, 0.875]   # horizontal node-bar positions (spread to avoid label collisions)
BAR_W = 0.007
NODE_GAP_FRAC = 0.016                          # vertical gap between nodes in the same column


# ----------------------------------------------------------------------------- grouping maps
def g_symptom(v: str) -> str:
    keep = {
        "Launch Failure": "Launch Failure", "Freeze": "Freeze", "Black Screen": "Black Screen",
        "Cutscene Issue": "Cutscene", "Graphic  / Rendering Issue": "Graphic / Rendering",
        "In-game Crash": "In-game Crash", "Startup Crash": "Startup Crash",
        "Network / Sync Issue": "Network / Sync",
    }
    return keep.get(v, "Other symptoms")


def g_root(v: str) -> str:
    return {"proton_side": "Proton side", "game_side": "Game side",
            "system_side": "System side", "cant_identify": "Unidentified"}[v]


def g_pattern(v: str) -> str:
    if v == "unknown":
        return "Unknown"
    for pre in ("(proton side) ", "(game side) ", "(system side) "):
        if v.startswith(pre):
            verb = v[len(pre):]
            return verb[0].upper() + verb[1:]
    raise ValueError(f"unrecognized fix_pattern value: {v!r}")


def g_mgmt(v: str) -> str:
    return {
        "generic upstream code change": "Upstream code change",
        "inline per-game hardcode": "Per-game hardcode",
        "centralized per-game profile": "Per-game profile",
        "server-side asset/config": "Server-side asset/config",
        "Community toolkit pre-game fix": "Community toolkit (per-game)",
        "discussion-only (no systematic manage)": "Discussion-only",
        "unknown": "Unknown",
    }[v]


def _dxvk_label() -> str:
    return "dxvk(-nvapi)" if SUBMODULE_DXVK_MODE == "merge_label" else "dxvk"


def g_sub(v: str) -> str:
    base = {
        "wine": "wine",
        "vkd3d-proton": "vkd3d(-proton)", "vkd3d": "vkd3d(-proton)",
        "gstreamer": "gstreamer", "wine-mono": "wine-mono",
        "proton (launcher script)": "proton script",
        "fonts (proton)": "other Proton comp.", "faudio": "other Proton comp.",
        "vrclient": "other Proton comp.", "lsteamclient": "other Proton comp.",
        "(game side) unknown": "game (closed-source)",
        "(system side) steam-client": "steam-client",
        "(system side) Mesa driver": "GPU driver", "(system side) Nvidia Driver": "GPU driver",
        "(system side) AMD GPU driver": "GPU driver",
        "(system side) host OS / environment": "host OS / hardware",
        "(system side) hardware / firmware": "host OS / hardware",
        "(system side) SteamVR runtime": "host OS / hardware",
        "unknown": "unknown",
    }
    if v == "dxvk":
        return _dxvk_label()
    if v == "dxvk-nvapi":
        return "other Proton comp." if SUBMODULE_DXVK_MODE == "split" else _dxvk_label()
    return base[v]


def column_specs():
    return [
        ("symptom_tags", g_symptom,
         ["Launch Failure", "Freeze", "Black Screen", "Cutscene", "Graphic / Rendering",
          "In-game Crash", "Startup Crash", "Network / Sync", "Other symptoms"]),
        ("root_cause_origin", g_root,
         ["Proton side", "Game side", "System side", "Unidentified"]),
        ("fix_patterns", g_pattern,
         ["Fix internal defect", "Supply missing capability", "Substitute component",
          "Disable / skip component", "Spoof identity", "Override / force parameter",
          "Change component version", "Change game settings", "Remap input bindings", "Unknown"]),
        ("fix_management", g_mgmt,
         ["Upstream code change", "Per-game hardcode", "Per-game profile", "Server-side asset/config",
          "Community toolkit (per-game)", "Discussion-only", "Unknown"]),
        ("fix_submodule", g_sub,
         ["wine", _dxvk_label(), "vkd3d(-proton)", "gstreamer", "wine-mono", "proton script",
          "other Proton comp.", "game (closed-source)", "steam-client", "GPU driver",
          "host OS / hardware", "unknown"]),
    ]


# ----------------------------------------------------------------------------- data & computation
def load_fixed_crs():
    # os-level listing (not glob) so the artifact also works when placed under
    # a path containing glob metacharacters such as [brackets].
    files = sorted(p for p in DATA_DIR.iterdir()
                   if p.name.startswith("cr_discussion_annotated_chunk_") and p.suffix == ".json")
    if not files:
        raise FileNotFoundError(f"data not found: {DATA_DIR}")
    recs = []
    for fn in files:
        with open(fn, encoding="utf-8") as f:
            recs += json.load(f)
    return recs, [r for r in recs if r.get("resolution_status") == "with_observed_fix"]


def _frac(record, field, gfn):
    vals = record.get(field) or []
    if not vals:
        return {}
    w = defaultdict(float)
    for v in vals:
        w[gfn(v)] += 1.0 / len(vals)
    return w


def _chan(record):
    vals = record.get("fix_channel") or []
    if not vals:
        return {}
    w = defaultdict(float)
    for v in vals:
        w[v] += 1.0 / len(vals)
    return w


def compute_sankey(fixed):
    """Return (columns, flows):
    columns[ci] = [(label, value), ...] top-to-bottom, only nodes that occur;
                  each column sums to len(fixed).
    flows = [(gap_i, src_label, dst_label, channel, value), ...].
    """
    specs = column_specs()
    columns = []
    for (field, gfn, order) in specs:
        acc = Counter()
        for r in fixed:
            for lab, wt in _frac(r, field, gfn).items():
                acc[lab] += wt
        columns.append([(lab, acc[lab]) for lab in order if acc.get(lab, 0) > 0])

    flows = []
    for gi in range(len(specs) - 1):
        lf, lg, _ = specs[gi]
        rf, rg, _ = specs[gi + 1]
        agg = defaultdict(float)
        for r in fixed:
            wl, wr, wc = _frac(r, lf, lg), _frac(r, rf, rg), _chan(r)
            if not wl or not wr or not wc:
                continue
            for ll, vl in wl.items():
                for rr, vr in wr.items():
                    for ch, vc in wc.items():
                        agg[(ll, rr, ch)] += vl * vr * vc
        for (ll, rr, ch), v in agg.items():
            flows.append((gi, ll, rr, ch, v))
    return columns, flows


# ----------------------------------------------------------------------------- matplotlib rendering
def render_matplotlib(columns, flows, total):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.path import Path as MPath
    from matplotlib.patches import PathPatch, Rectangle

    # node geometry (y: 0 top -> 1 bottom)
    top, bot, hgt = {}, {}, {}
    for ci, col in enumerate(columns):
        n = len(col)
        span = 1.0 - NODE_GAP_FRAC * (n - 1)
        cur = 0.0
        for lab, v in col:
            h = span * v / total
            top[(ci, lab)] = cur
            bot[(ci, lab)] = cur + h
            hgt[(ci, lab)] = h
            cur += h + NODE_GAP_FRAC

    # ribbon stacking at endpoints (outgoing sorted by target position,
    # incoming sorted by source position)
    out_links = defaultdict(list)
    in_links = defaultdict(list)
    for k, (gi, s, d, ch, v) in enumerate(flows):
        out_links[(gi, s)].append(k)
        in_links[(gi + 1, d)].append(k)
    for key, ks in out_links.items():
        ks.sort(key=lambda k: top[(flows[k][0] + 1, flows[k][2])])
    for key, ks in in_links.items():
        ks.sort(key=lambda k: top[(flows[k][0], flows[k][1])])

    seg_out, seg_in = {}, {}
    for (ci, lab), ks in out_links.items():
        cur = top[(ci, lab)]
        for k in ks:
            h = hgt[(ci, lab)] * flows[k][4] / sum(flows[j][4] for j in ks)
            seg_out[k] = (cur, cur + h); cur += h
    for (ci, lab), ks in in_links.items():
        cur = top[(ci, lab)]
        for k in ks:
            h = hgt[(ci, lab)] * flows[k][4] / sum(flows[j][4] for j in ks)
            seg_in[k] = (cur, cur + h); cur += h

    fig, ax = plt.subplots(figsize=(FIG_W_IN, FIG_H_IN), dpi=FIG_DPI)
    ax.set_xlim(0, 1); ax.set_ylim(1, 0); ax.axis("off")   # y inverted: 0 = top

    def hex2rgb(h):
        h = h.lstrip("#"); return tuple(int(h[i:i+2], 16) / 255 for i in (0, 2, 4))

    # draw ribbons first (large flows later so small flows stay visible)
    for k in sorted(range(len(flows)), key=lambda k: -flows[k][4]):
        gi, s, d, ch, v = flows[k]
        x0 = COL_X[gi] + BAR_W / 2
        x1 = COL_X[gi + 1] - BAR_W / 2
        oa, ob = seg_out[k]; ia, ib = seg_in[k]
        mx = (x0 + x1) / 2
        verts = [(x0, oa), (mx, oa), (mx, ia), (x1, ia),
                 (x1, ib), (mx, ib), (mx, ob), (x0, ob), (x0, oa)]
        codes = [MPath.MOVETO, MPath.CURVE4, MPath.CURVE4, MPath.CURVE4,
                 MPath.LINETO, MPath.CURVE4, MPath.CURVE4, MPath.CURVE4, MPath.CLOSEPOLY]
        ax.add_patch(PathPatch(MPath(verts, codes),
                               facecolor=hex2rgb(CHANNEL_COLORS[ch]) + (LINK_ALPHA,),
                               edgecolor="none"))

    # node bars + labels
    for ci, col in enumerate(columns):
        for lab, v in col:
            t, b = top[(ci, lab)], bot[(ci, lab)]
            ax.add_patch(Rectangle((COL_X[ci] - BAR_W / 2, t), BAR_W, b - t,
                                   facecolor=NODE_COLOR, edgecolor="none", zorder=3))
            # labels of the three middle columns sit on top of ribbons; add a
            # translucent white halo for readability
            halo = dict(facecolor="white", alpha=0.7, edgecolor="none",
                        boxstyle="round,pad=0.15") if ci in (1, 2, 3) else None
            if ci == 0:   # Symptom column: label on the left
                ax.text(COL_X[ci] - BAR_W / 2 - 0.008, (t + b) / 2, lab,
                        va="center", ha="right", fontsize=FS_LABEL, color="#1a1a1a", zorder=4)
            else:         # other columns: label on the right
                ax.text(COL_X[ci] + BAR_W / 2 + 0.008, (t + b) / 2, lab,
                        va="center", ha="left", fontsize=FS_LABEL, color="#1a1a1a",
                        zorder=4, bbox=halo)

    # column titles
    for title, x in zip(COLUMN_TITLES, COL_X):
        ax.text(x, -0.055, title, ha="center", va="bottom",
                fontsize=FS_TITLE, fontweight="bold", color="#000")

    # bottom channel legend
    lx = 0.34
    for ch, name in CHANNEL_LEGEND:
        ax.add_patch(Rectangle((lx, 1.045), 0.016, 0.028,
                               facecolor=CHANNEL_COLORS[ch], edgecolor="none", clip_on=False))
        ax.text(lx + 0.024, 1.059, name, va="center", ha="left",
                fontsize=FS_LEGEND, color="#222")
        lx += 0.135

    ax.set_ylim(1.10, -0.09)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for fmt in ("pdf", "png"):
        p = OUT_DIR / f"{OUT_STEM}.{fmt}"
        fig.savefig(str(p), bbox_inches="tight", facecolor="white",
                    dpi=FIG_DPI if fmt == "png" else None)
        written.append(p)
    plt.close(fig)
    return written


# ----------------------------------------------------------------------------- plotly rendering (interactive)
def render_plotly(columns, flows, total):
    import plotly.graph_objects as go

    index, labels, nx, ny = {}, [], [], []
    px = [0.06, 0.205, 0.40, 0.635, 0.93]
    for ci, col in enumerate(columns):
        n = len(col); span = 1.0 - 0.012 * (n - 1); cur = 0.0
        for lab, v in col:
            h = span * v / total
            index[(ci, lab)] = len(labels)
            labels.append(lab); nx.append(px[ci])
            ny.append(min(0.999, max(0.001, cur + h / 2)))
            cur += h + 0.012

    def rgba(hx, a):
        hx = hx.lstrip("#"); r, g, b = (int(hx[i:i+2], 16) for i in (0, 2, 4))
        return f"rgba({r},{g},{b},{a})"

    order_ch = ["third_party_fix", "community_fix", "proton_update"]
    flows_sorted = sorted(flows, key=lambda f: order_ch.index(f[3]) if f[3] in order_ch else 9)
    src = [index[(gi, s)] for (gi, s, d, ch, v) in flows_sorted]
    dst = [index[(gi + 1, d)] for (gi, s, d, ch, v) in flows_sorted]
    val = [v for (gi, s, d, ch, v) in flows_sorted]
    lcol = [rgba(CHANNEL_COLORS[ch], LINK_ALPHA) for (gi, s, d, ch, v) in flows_sorted]

    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node=dict(label=labels, x=nx, y=ny, color=NODE_COLOR, pad=8, thickness=12,
                  line=dict(width=0)),
        link=dict(source=src, target=dst, value=val, color=lcol),
    ))
    ann = [dict(x=x, y=1.07, xref="paper", yref="paper", text=f"<b>{t}</b>",
                showarrow=False, font=dict(size=16), xanchor="center")
           for t, x in zip(COLUMN_TITLES, px)]
    shapes, lx = [], 0.30
    for ch, name in CHANNEL_LEGEND:
        shapes.append(dict(type="rect", xref="paper", yref="paper",
                           x0=lx, x1=lx + 0.02, y0=-0.10, y1=-0.06,
                           fillcolor=CHANNEL_COLORS[ch], line=dict(width=0)))
        ann.append(dict(x=lx + 0.026, y=-0.08, xref="paper", yref="paper", text=name,
                        showarrow=False, xanchor="left", font=dict(size=13)))
        lx += 0.14
    fig.update_layout(annotations=ann, shapes=shapes, paper_bgcolor="white",
                      font=dict(family="Helvetica, Arial, sans-serif", size=14, color="#222"),
                      margin=dict(l=10, r=10, t=46, b=54), width=1300, height=620)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    html = OUT_DIR / f"{OUT_STEM}.html"
    fig.write_html(str(html), include_plotlyjs="cdn"); written.append(html)
    for fmt in ("pdf", "png"):
        try:
            fig.write_image(str(OUT_DIR / f"{OUT_STEM}_plotly.{fmt}"), scale=3)
            written.append(OUT_DIR / f"{OUT_STEM}_plotly.{fmt}")
        except Exception as e:
            hint = ""
            if "chrome" in str(e).lower() or "kaleido" in str(e).lower():
                hint = "  (needs Chrome: `pip install kaleido`, then run `plotly_get_chrome`)"
            print(f"  [plotly skipped {fmt}] {type(e).__name__}{hint}")
    return written


def main():
    recs, fixed = load_fixed_crs()
    total = len(fixed)
    print(f"total CRs={len(recs)}  fixed (in figure)={total}  dxvk mode={SUBMODULE_DXVK_MODE}")
    columns, flows = compute_sankey(fixed)
    # conservation self-check: every column sum and every gap flow must equal `total`
    for ci, col in enumerate(columns):
        assert abs(sum(v for _, v in col) - total) < 1e-6, f"column {ci} not normalized"
    for gi in range(4):
        gsum = sum(f[4] for f in flows if f[0] == gi)
        assert abs(gsum - total) < 1e-6, f"gap {gi} flow not conserved: {gsum}"
    written = []
    if RENDER_MATPLOTLIB:
        written += render_matplotlib(columns, flows, total)
    if RENDER_PLOTLY:
        try:
            written += render_plotly(columns, flows, total)
        except ModuleNotFoundError:
            print("  [plotly skipped] plotly not installed")
    print("written:")
    for p in written:
        print("  -", p)


if __name__ == "__main__":
    main()
