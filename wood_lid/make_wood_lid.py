#!/usr/bin/env python3
"""Laser cut files for the stacked wooden busylight lid.

The lid is glued up from thin wood sheets:
  layer 1        floor with the LED holes
  layers 2..13   rings round the cavity the base slides into
                 (the rings at the snap-bump height have small notches)
Every ring has a hole in each corner: push toothpicks through them while
gluing so the layers line up, then trim them flush.

It matches busylight_wood_lid.sc. Run it again with your measured numbers:

    python3 make_wood_lid.py --sheet 0.95 --kerf 0.12

The parts are split into jobs that fit the laser's bed (default 80 x 80 mm,
the Daja DJ6); each job is written as jobs/job_NN.svg, .dxf and .png.
SVG/DXF: inner contours red (layer CUT), outlines blue (layer OUTLINE), cut red first.
PNG: black parts on white at true scale, for picture-only apps (Daja Engraver):
set the picture to the size the script prints and use the contour/cut mode.
"""
import argparse
import math
import shutil
from pathlib import Path

# ---- design (mm), same names as the SolidCraft parameters ----
P = dict(
    L=62.0,          # base outer length (fits inside the lid)
    W=29.0,          # base outer width
    clr=0.1,         # fit clearance per side
    wall_end=4.0,    # end wall thickness (X)
    wall_side=4.0,   # side wall thickness (Y)
    cavity=12.0,     # cavity depth the base needs
    led_d=10.0,
    led_x=11.5,      # first LED centre from the base's -X end
    led_pitch=11.5,
    n_led=3,
    bump_in=3.0,     # snap bumps: distance from the base's long edges
    notch_w=1.2,
    notch_d=0.6,
    notch_z0=8.0,    # notches between these heights in the lid
    notch_z1=11.0,
    pin_d=2.1,       # toothpick alignment holes, centred in the wall corners
)


def build_parts(p, sheet, kerf, floor_pins):
    k2 = kerf / 2
    we, ws, clr = p["wall_end"], p["wall_side"], p["clr"]
    L, W = p["L"], p["W"]
    ow, oh = L + 2 * clr + 2 * we, W + 2 * clr + 2 * ws  # nominal outer size

    outer = [(-k2, -k2), (ow + k2, -k2), (ow + k2, oh + k2), (-k2, oh + k2)]

    ix0, ix1 = we + k2, we + L + 2 * clr - k2
    iy0, iy1 = ws + k2, ws + W + 2 * clr - k2
    plain_inner = [(ix0, iy0), (ix1, iy0), (ix1, iy1), (ix0, iy1)]

    hw = (p["notch_w"] - kerf) / 2
    n1 = ws + clr + p["bump_in"]
    n2 = ws + clr + W - p["bump_in"]
    lx = we - p["notch_d"] + k2
    rx = we + L + 2 * clr + p["notch_d"] - k2
    notched_inner = [
        (ix0, iy0), (ix1, iy0),
        (ix1, n1 - hw), (rx, n1 - hw), (rx, n1 + hw), (ix1, n1 + hw),
        (ix1, n2 - hw), (rx, n2 - hw), (rx, n2 + hw), (ix1, n2 + hw),
        (ix1, iy1), (ix0, iy1),
        (ix0, n2 + hw), (lx, n2 + hw), (lx, n2 - hw), (ix0, n2 - hw),
        (ix0, n1 + hw), (lx, n1 + hw), (lx, n1 - hw), (ix0, n1 - hw),
    ]

    pr = p["pin_d"] / 2 - k2
    pins = [(x, y, pr) for x in (we / 2, ow - we / 2) for y in (ws / 2, oh - ws / 2)]
    leds = [
        (we + clr + p["led_x"] + i * p["led_pitch"], ws + clr + W / 2, p["led_d"] / 2 - k2)
        for i in range(int(p["n_led"]))
    ]

    n_ring = math.ceil(p["cavity"] / sheet - 1e-9)
    parts = [("L01 floor", outer, [], leds + (pins if floor_pins else []))]
    for i in range(1, n_ring + 1):
        z0, z1 = i * sheet, (i + 1) * sheet
        notched = z0 < p["notch_z1"] and z1 > p["notch_z0"]
        inner = notched_inner if notched else plain_inner
        parts.append((f"L{i + 1:02d} {'notched ring' if notched else 'ring'}", outer, [inner], pins))
    return parts, (ow + kerf, oh + kerf), n_ring


def plan_jobs(parts, size, bed, margin, gap):
    """Stack parts in one column per job, as many as fit the bed."""
    pw, ph = size
    bw, bh = bed
    if pw + 2 * margin > bw or ph + 2 * margin > bh:
        raise SystemExit(f"a part ({pw:.1f} x {ph:.1f} mm) does not fit the {bw:g} x {bh:g} mm bed")
    cols = max(1, int((bw - 2 * margin + gap) // (pw + gap)))
    rows = max(1, int((bh - 2 * margin + gap) // (ph + gap)))
    per = cols * rows
    jobs = []
    for start in range(0, len(parts), per):
        chunk = parts[start:start + per]
        placed = []
        for n, part in enumerate(chunk):
            c, r = n % cols, n // cols
            # outlines start at -kerf/2 in part coordinates: shift by it
            k2 = -part[1][0][0]
            placed.append((part, margin + k2 + c * (pw + gap), margin + k2 + r * (ph + gap)))
        jobs.append(placed)
    return jobs, per


def write_svg(path, placed, bed):
    sw, sh = bed
    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{sw:.3f}mm" height="{sh:.3f}mm" '
        f'viewBox="0 0 {sw:.3f} {sh:.3f}">',
        '<g id="CUT" fill="none" stroke="#ff0000" stroke-width="0.1">',
    ]

    def pts(poly, dx, dy):  # flip Y so the SVG reads like the model from above
        return " ".join(f"{x + dx:.3f},{sh - (y + dy):.3f}" for x, y in poly)

    for (name, outer, inners, holes), dx, dy in placed:
        for poly in inners:
            out.append(f'<polygon points="{pts(poly, dx, dy)}"/>')
        for cx, cy, r in holes:
            out.append(f'<circle cx="{cx + dx:.3f}" cy="{sh - (cy + dy):.3f}" r="{r:.3f}"/>')
    out.append("</g>")
    out.append('<g id="OUTLINE" fill="none" stroke="#0000ff" stroke-width="0.1">')
    for (name, outer, inners, holes), dx, dy in placed:
        out.append(f'<polygon points="{pts(outer, dx, dy)}"/>')
    out.append("</g></svg>")
    Path(path).write_text("\n".join(out) + "\n")


def write_dxf(path, placed):
    e = []

    def line(layer, a, b):
        e.extend(["0", "LINE", "8", layer, "10", f"{a[0]:.4f}", "20", f"{a[1]:.4f}", "30", "0",
                  "11", f"{b[0]:.4f}", "21", f"{b[1]:.4f}", "31", "0"])

    def poly(layer, pts_, dx, dy):
        q = [(x + dx, y + dy) for x, y in pts_]
        for a, b in zip(q, q[1:] + q[:1]):
            line(layer, a, b)

    for (name, outer, inners, holes), dx, dy in placed:  # inner contours first
        for p_ in inners:
            poly("CUT", p_, dx, dy)
        for cx, cy, r in holes:
            e.extend(["0", "CIRCLE", "8", "CUT", "10", f"{cx + dx:.4f}", "20", f"{cy + dy:.4f}",
                      "30", "0", "40", f"{r:.4f}"])
    for (name, outer, inners, holes), dx, dy in placed:
        poly("OUTLINE", outer, dx, dy)

    head = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4", "0", "ENDSEC",
            "0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LAYER", "70", "2",
            "0", "LAYER", "2", "CUT", "70", "0", "62", "1", "6", "CONTINUOUS",
            "0", "LAYER", "2", "OUTLINE", "70", "0", "62", "5", "6", "CONTINUOUS",
            "0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    tail = ["0", "ENDSEC", "0", "EOF"]
    Path(path).write_text("\n".join(head + e + tail) + "\n")


def write_png(path, placed, px_per_mm=20.0, border=1.0):
    """Black parts on white, holes white, at true scale (DPI stored in the file).

    For apps that only take pictures and trace their outlines (the Daja Engraver
    app's contour/cut mode). Returns the picture size in mm.
    """
    import struct
    import zlib

    polys, circles = [], []
    for (name, outer, inners, holes), dx, dy in placed:
        for poly in [outer] + inners:
            polys.append([(x + dx, y + dy) for x, y in poly])
        circles += [(cx + dx, cy + dy, r) for cx, cy, r in holes]
    xs = [x for p_ in polys for x, _ in p_]
    ys = [y for p_ in polys for _, y in p_]
    x0, y0 = min(xs) - border, min(ys) - border
    w_mm, h_mm = max(xs) + border - x0, max(ys) + border - y0
    w, h = round(w_mm * px_per_mm), round(h_mm * px_per_mm)
    edges = [(a, b) for p_ in polys for a, b in zip(p_, p_[1:] + p_[:1]) if a[1] != b[1]]

    rows = []
    for row in range(h):
        y = y0 + h_mm - (row + 0.5) / px_per_mm  # row 0 is the top
        xs_ = []
        for (ax, ay), (bx, by) in edges:
            if (ay <= y < by) or (by <= y < ay):
                xs_.append(ax + (y - ay) * (bx - ax) / (by - ay))
        for cx, cy, r in circles:
            d = r * r - (y - cy) ** 2
            if d > 0:
                s = d ** 0.5
                xs_ += [cx - s, cx + s]
        xs_.sort()
        line = bytearray(b"\xff" * w)
        for a, b in zip(xs_[0::2], xs_[1::2]):  # even-odd fill
            i0 = max(0, round((a - x0) * px_per_mm))
            i1 = min(w, round((b - x0) * px_per_mm))
            line[i0:i1] = b"\x00" * max(0, i1 - i0)
        rows.append(b"\x00" + bytes(line))

    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    ppm = round(px_per_mm * 1000)  # pixels per metre
    png = (b"\x89PNG\r\n\x1a\n"
           + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
           + chunk(b"pHYs", struct.pack(">IIB", ppm, ppm, 1))
           + chunk(b"IDAT", zlib.compress(b"".join(rows), 9))
           + chunk(b"IEND", b""))
    Path(path).write_bytes(png)
    return w_mm, h_mm


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sheet", type=float, default=1.0, help="measured wood thickness, mm (default 1.0)")
    ap.add_argument("--kerf", type=float, default=0.1, help="laser kerf width, mm (default 0.1)")
    ap.add_argument("--clr", type=float, default=P["clr"], help="fit clearance per side, mm")
    ap.add_argument("--wall", type=float, default=None, help="wall thickness, mm (default 4)")
    ap.add_argument("--pin", type=float, default=P["pin_d"], help="alignment hole diameter, mm (default 2.1)")
    ap.add_argument("--floor-pins", action="store_true", help="also put the alignment holes in the floor")
    ap.add_argument("--bed", type=float, nargs=2, default=(80.0, 80.0), metavar=("W", "H"),
                    help="laser bed, mm (default 80 80, Daja DJ6)")
    ap.add_argument("--margin", type=float, default=1.5, help="space from the bed edge, mm")
    ap.add_argument("--gap", type=float, default=2.0, help="space between parts, mm")
    ap.add_argument("--ppmm", type=float, default=20.0, help="PNG pixels per mm (default 20 = 508 dpi)")
    a = ap.parse_args()
    p = dict(P, clr=a.clr, pin_d=a.pin)
    if a.wall is not None:
        p.update(wall_end=a.wall, wall_side=a.wall)

    parts, size, n_ring = build_parts(p, a.sheet, a.kerf, a.floor_pins)
    jobs, per = plan_jobs(parts, size, a.bed, a.margin, a.gap)

    out = Path(__file__).resolve().parent / "jobs"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir()
    png_sizes = []
    for n, placed in enumerate(jobs, 1):
        write_svg(out / f"job_{n:02d}.svg", placed, a.bed)
        write_dxf(out / f"job_{n:02d}.dxf", placed)
        png_sizes.append(write_png(out / f"job_{n:02d}.png", placed, a.ppmm))

    # one file per kind of part, to cut as many times as needed
    singles = Path(__file__).resolve().parent / "singles"
    shutil.rmtree(singles, ignore_errors=True)
    singles.mkdir()
    kinds = {}
    for part in parts:
        kinds.setdefault(part[0].split(" ", 1)[1].replace(" ", "_"), part)
    for kind, part in kinds.items():
        (placed,), _ = plan_jobs([part], size, a.bed, a.margin, a.gap)
        write_svg(singles / f"{kind}.svg", placed, a.bed)
        write_dxf(singles / f"{kind}.dxf", placed)
        sw, sh = write_png(singles / f"{kind}.png", placed, a.ppmm)
        count = sum(1 for p_ in parts if p_[0].split(" ", 1)[1] == part[0].split(" ", 1)[1])
        print(f"  singles/{kind}: picture {sw:.1f} x {sh:.1f} mm, cut {count}x")

    print(f"part {size[0]:.1f} x {size[1]:.1f} mm, {per} per job on a {a.bed[0]:g} x {a.bed[1]:g} mm bed")
    print(f"stack: 1 floor + {n_ring} rings = {a.sheet * (1 + n_ring):.2f} mm tall, "
          f"cavity {n_ring * a.sheet:.2f} mm deep")
    for n, placed in enumerate(jobs, 1):
        pw, ph = png_sizes[n - 1]
        print(f"  job_{n:02d}: picture {pw:.1f} x {ph:.1f} mm: "
              + ", ".join(part[0] for part, _, _ in placed))


if __name__ == "__main__":
    main()
