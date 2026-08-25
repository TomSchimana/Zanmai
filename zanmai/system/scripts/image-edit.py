#!/usr/bin/env python3
"""Local image editing for Loki, deterministic pixel work that needs no model.

A standalone tool, separate from zanmai.py: the CLI here is a pixel workbench,
not vault mechanics. Two tiers of operation:

  Core (Pillow only)   convert, resize, rotate, crop, grayscale, composite,
                       optimize, palette (dominant colours plus WCAG contrast
                       against a reference), plus batch over a folder. Always
                       available once Pillow is provisioned.

  Detected (heavier)   grade (apply a .cube LUT or match a reference image's
                       colour), raw (develop a camera RAW). Each checks its own
                       dependency at call time and, when it is missing, prints
                       what to provision and exits non-zero instead of guessing.

Nothing is assumed present. `image-edit.py detect` reports what this host can do.
Formats follow the output extension; WebP is supported through Pillow.
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

RASTER_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp", ".gif"}


def _fail(msg: str) -> "NoReturn":  # type: ignore[valid-type]
    print(f"error: {msg}", file=sys.stderr)
    raise SystemExit(1)


def _need_pillow():
    try:
        from PIL import Image  # noqa: F401
    except ImportError:
        _fail(
            "Pillow is not available. Provision it before core image editing "
            "(the shared provisioning step installs it into the media environment)."
        )
    from PIL import Image

    return Image


def _open(path: str):
    Image = _need_pillow()
    p = Path(path)
    if not p.is_file():
        _fail(f"input not found: {path}")
    try:
        return Image.open(p)
    except Exception as e:  # Pillow raises a family of decode errors
        _fail(f"could not read {path} as an image: {e}")


def _save(img, out: str, quality: int | None = None, optimize: bool = False):
    outp = Path(out)
    outp.parent.mkdir(parents=True, exist_ok=True)
    fmt = outp.suffix.lower()
    params: dict = {}
    if optimize:
        params["optimize"] = True
    if quality is not None and fmt in {".jpg", ".jpeg", ".webp"}:
        params["quality"] = quality
    save_img = img
    # JPEG has no alpha channel; flatten onto white so a PNG→JPG convert never crashes.
    if fmt in {".jpg", ".jpeg"} and img.mode in {"RGBA", "LA", "P"}:
        Image = _need_pillow()
        bg = Image.new("RGB", img.size, (255, 255, 255))
        rgba = img.convert("RGBA")
        bg.paste(rgba, mask=rgba.split()[-1])
        save_img = bg
    try:
        save_img.save(outp, **params)
    except Exception as e:
        _fail(f"could not write {out}: {e}")
    print(f"wrote {out} ({save_img.width}x{save_img.height})")


# ---------------------------------------------------------------------------
# Core transforms (Pillow). Each takes a PIL image and returns a PIL image, so
# single-file and batch share one implementation.
# ---------------------------------------------------------------------------

def op_resize(img, width=None, height=None, scale=None, fit=False):
    Image = _need_pillow()
    w0, h0 = img.size
    if scale is not None:
        w, h = max(1, round(w0 * scale)), max(1, round(h0 * scale))
    elif width and height and not fit:
        w, h = width, height
    elif width or height:
        # preserve aspect: scale so the image fits within the given bound(s)
        rw = width / w0 if width else None
        rh = height / h0 if height else None
        r = min([x for x in (rw, rh) if x is not None])
        w, h = max(1, round(w0 * r)), max(1, round(h0 * r))
    else:
        _fail("resize needs --scale, or --width/--height")
    return img.resize((w, h), Image.LANCZOS)


def op_rotate(img, degrees, expand=True):
    return img.rotate(-degrees, expand=expand)  # negative = clockwise for positive input


def op_crop(img, x, y, w, h):
    iw, ih = img.size
    if x < 0 or y < 0 or x + w > iw or y + h > ih:
        _fail(f"crop box {x},{y},{w}x{h} falls outside the {iw}x{ih} image")
    return img.crop((x, y, x + w, y + h))


def op_grayscale(img):
    return img.convert("L")


def op_palette(img, n=6):
    """The `n` dominant colours by pixel count, most common first. Pillow's own
    median-cut quantiser does the clustering, no extra dependency; MAXCOVERAGE is
    used over the faster FASTOCTREE because it keeps a small-but-large solid block
    (a logo mark, a brand accent) rather than losing it to background noise, which
    is exactly the case reading a reference mockup or screenshot needs."""
    Image = _need_pillow()
    rgb = img.convert("RGB")
    n = max(1, min(n, 256))
    quant = rgb.quantize(colors=n, method=Image.Quantize.MAXCOVERAGE)
    counts = quant.getcolors(maxcolors=256) or []
    counts.sort(key=lambda c: -c[0])
    palette = quant.getpalette()
    total = rgb.width * rgb.height
    result = []
    for count, index in counts[:n]:
        r, g, b = palette[index * 3], palette[index * 3 + 1], palette[index * 3 + 2]
        result.append({"hex": "#%02x%02x%02x" % (r, g, b), "rgb": (r, g, b),
                        "count": count, "share": round(count / total, 4)})
    return result


def _hex_to_rgb(hex_str: str) -> tuple[int, int, int]:
    h = hex_str.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    if len(h) != 6:
        _fail(f"not a hex colour: {hex_str}")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _srgb_channel_to_linear(c: int) -> float:
    v = c / 255.0
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    r, g, b = rgb
    return (0.2126 * _srgb_channel_to_linear(r) + 0.7152 * _srgb_channel_to_linear(g)
            + 0.0722 * _srgb_channel_to_linear(b))


def contrast_ratio(rgb_a: tuple[int, int, int], rgb_b: tuple[int, int, int]) -> float:
    """WCAG 2 contrast ratio, 1:1 (identical) to 21:1 (black on white)."""
    la, lb = relative_luminance(rgb_a), relative_luminance(rgb_b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def _wcag_verdict(ratio: float) -> str:
    if ratio >= 7.0:
        return "AAA"
    if ratio >= 4.5:
        return "AA"
    if ratio >= 3.0:
        return "AA-large-only"
    return "fail"


def op_composite(base, overlay_path, x, y, scale=None, opacity=1.0):
    Image = _need_pillow()
    ov = _open(overlay_path).convert("RGBA")
    if scale is not None:
        ov = ov.resize((max(1, round(ov.width * scale)), max(1, round(ov.height * scale))), Image.LANCZOS)
    if opacity < 1.0:
        alpha = ov.split()[-1].point(lambda a: round(a * opacity))
        ov.putalpha(alpha)
    canvas = base.convert("RGBA")
    canvas.alpha_composite(ov, (x, y))
    return canvas


def _apply_core(img, op, a):
    if op == "resize":
        return op_resize(img, a.get("width"), a.get("height"), a.get("scale"), a.get("fit", False))
    if op == "rotate":
        return op_rotate(img, a["degrees"], a.get("expand", True))
    if op == "grayscale":
        return op_grayscale(img)
    if op == "convert":
        return img  # format change happens at save
    if op == "optimize":
        return img
    _fail(f"'{op}' is not a batchable core op")


# ---------------------------------------------------------------------------
# Detected tiers, real implementations, guarded by their dependency.
# ---------------------------------------------------------------------------

def _detect() -> dict:
    def has(mod):
        try:
            __import__(mod)
            return True
        except ImportError:
            return False

    return {
        "pillow": has("PIL"),
        "numpy": has("numpy"),           # LUT application
        "color_matcher": has("color_matcher"),  # reference colour match
        "skimage": has("skimage"),       # reference colour match (fallback)
        "rawpy": has("rawpy"),           # RAW develop
        "imagemagick": bool(shutil.which("magick") or shutil.which("convert")),
    }


def grade_lut(inp, out, cube_path, quality=None):
    caps = _detect()
    if not caps["numpy"]:
        _fail("grade lut needs numpy, not present. Provision numpy, then retry.")
    import numpy as np

    lut, size = _read_cube(cube_path)  # (N^3, 3) float, and N
    img = _open(inp).convert("RGB")
    arr = np.asarray(img, dtype=np.float32) / 255.0
    idx = np.clip(arr * (size - 1), 0, size - 1)
    lo = np.floor(idx).astype(int)
    # nearest-neighbour sample of the LUT (a trilinear blend would be smoother;
    # nearest is honest and dependency-free, refine when a real look demands it)
    r, g, b = lo[..., 0], lo[..., 1], lo[..., 2]
    flat = (r + g * size + b * size * size)
    out_arr = lut[flat]
    result = (np.clip(out_arr, 0, 1) * 255.0).round().astype("uint8")
    Image = _need_pillow()
    _save(Image.fromarray(result, "RGB"), out, quality=quality)


def _read_cube(path):
    import numpy as np

    p = Path(path)
    if not p.is_file():
        _fail(f"LUT not found: {path}")
    size = None
    rows = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("TITLE"):
            continue
        if line.startswith("LUT_3D_SIZE"):
            size = int(line.split()[-1])
            continue
        if line.startswith(("LUT_1D_SIZE", "DOMAIN_")):
            continue
        parts = line.split()
        if len(parts) == 3:
            try:
                rows.append([float(x) for x in parts])
            except ValueError:
                continue
    if size is None or len(rows) != size ** 3:
        _fail(f"unsupported .cube: expected a 3D LUT with {size}^3 rows, got {len(rows)}")
    return np.asarray(rows, dtype=np.float32), size


def grade_match(inp, out, ref, quality=None):
    caps = _detect()
    if caps["color_matcher"]:
        from color_matcher import ColorMatcher
        from color_matcher.io_handler import load_img_file
        import numpy as np

        src = load_img_file(inp)
        tgt = load_img_file(ref)
        res = ColorMatcher(src=src, ref=tgt, method="mkl").main()
        Image = _need_pillow()
        _save(Image.fromarray(np.clip(res, 0, 255).astype("uint8")), out, quality=quality)
        return
    if caps["skimage"]:
        from skimage.exposure import match_histograms
        import numpy as np

        src = np.asarray(_open(inp).convert("RGB"))
        ref_arr = np.asarray(_open(ref).convert("RGB"))
        matched = match_histograms(src, ref_arr, channel_axis=-1)
        Image = _need_pillow()
        _save(Image.fromarray(matched.astype("uint8"), "RGB"), out, quality=quality)
        return
    _fail("grade match needs color-matcher or scikit-image, neither present. Provision one, then retry.")


def raw_develop(inp, out, quality=None):
    caps = _detect()
    if not caps["rawpy"]:
        _fail("raw develop needs rawpy, not present. Provision rawpy, then retry.")
    import rawpy

    with rawpy.imread(inp) as raw:
        rgb = raw.postprocess(no_auto_bright=False, output_bps=8)
    Image = _need_pillow()
    _save(Image.fromarray(rgb), out, quality=quality)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def cmd_detect(a):
    caps = _detect()
    print("image-edit host capabilities:")
    print(f"  core (Pillow)          : {'yes' if caps['pillow'] else 'MISSING, provision Pillow'}")
    print(f"  grade lut (numpy)      : {'yes' if caps['numpy'] else 'no, provision numpy'}")
    match = caps["color_matcher"] or caps["skimage"]
    print(f"  grade match            : {'yes' if match else 'no, provision color-matcher or scikit-image'}")
    print(f"  raw develop (rawpy)    : {'yes' if caps['rawpy'] else 'no, provision rawpy'}")
    print(f"  imagemagick (fallback) : {'yes' if caps['imagemagick'] else 'no'}")


def cmd_convert(a):
    _save(_open(a.input), a.output, quality=a.quality, optimize=a.optimize)


def cmd_resize(a):
    _save(op_resize(_open(a.input), a.width, a.height, a.scale, a.fit), a.output, quality=a.quality)


def cmd_rotate(a):
    _save(op_rotate(_open(a.input), a.degrees, not a.no_expand), a.output, quality=a.quality)


def cmd_crop(a):
    _save(op_crop(_open(a.input), a.x, a.y, a.width, a.height), a.output, quality=a.quality)


def cmd_grayscale(a):
    _save(op_grayscale(_open(a.input)), a.output, quality=a.quality)


def cmd_composite(a):
    _save(op_composite(_open(a.input), a.overlay, a.x, a.y, a.scale, a.opacity), a.output, quality=a.quality)


def cmd_optimize(a):
    _save(_open(a.input), a.output, quality=a.quality, optimize=True)


def cmd_palette(a):
    colours = op_palette(_open(a.input), a.colours)
    print(f"{len(colours)} dominant colour(s) in {a.input}:")
    for c in colours:
        line = f"  {c['hex']}  {c['share'] * 100:5.1f}%  ({c['count']} px)"
        if a.against:
            ratio = contrast_ratio(c["rgb"], _hex_to_rgb(a.against))
            line += f"   vs {a.against}: {ratio:.2f}:1 ({_wcag_verdict(ratio)})"
        print(line)
    if a.against:
        print("WCAG 2: AA needs 4.5:1 (3:1 for large text), AAA needs 7:1.")


def cmd_batch(a):
    src = Path(a.in_dir)
    if not src.is_dir():
        _fail(f"batch --in-dir is not a folder: {a.in_dir}")
    out = Path(a.out_dir)
    files = sorted(
        p for p in (src.rglob("*") if a.recursive else src.iterdir())
        if p.is_file() and p.suffix.lower() in RASTER_SUFFIXES
    )
    if not files:
        _fail(f"no images found in {a.in_dir}")
    params = {"width": a.width, "height": a.height, "scale": a.scale, "fit": a.fit,
              "degrees": a.degrees, "expand": not a.no_expand}
    ext = f".{a.to}" if a.to else None
    done = 0
    for f in files:
        img = _open(str(f))
        result = _apply_core(img, a.op, params)
        target = out / (f.stem + (ext or f.suffix))
        _save(result, str(target), quality=a.quality, optimize=(a.op == "optimize"))
        done += 1
    print(f"batch {a.op}: {done} file(s) → {a.out_dir}")


def cmd_grade(a):
    if a.lut:
        grade_lut(a.input, a.output, a.lut, quality=a.quality)
    elif a.match:
        grade_match(a.input, a.output, a.match, quality=a.quality)
    else:
        _fail("grade needs --lut <file.cube> or --match <reference-image>")


def cmd_raw(a):
    raw_develop(a.input, a.output, quality=a.quality)


def build_parser():
    p = argparse.ArgumentParser(prog="image-edit.py", description=__doc__.splitlines()[0])
    sub = p.add_subparsers(dest="cmd", required=True)

    def q(sp):  # shared quality flag for save ops
        sp.add_argument("--quality", type=int, help="JPEG/WebP quality 1-100")

    sub.add_parser("detect", help="report what this host can do").set_defaults(func=cmd_detect)

    sp = sub.add_parser("convert", help="change format (extension of output), incl. WebP")
    sp.add_argument("input"); sp.add_argument("output"); q(sp)
    sp.add_argument("--optimize", action="store_true"); sp.set_defaults(func=cmd_convert)

    sp = sub.add_parser("resize", help="resize by --scale, exact --width/--height, or fit-within")
    sp.add_argument("input"); sp.add_argument("output")
    sp.add_argument("--width", type=int); sp.add_argument("--height", type=int)
    sp.add_argument("--scale", type=float)
    sp.add_argument("--fit", action="store_true", help="fit within width/height, keep aspect")
    q(sp); sp.set_defaults(func=cmd_resize)

    sp = sub.add_parser("rotate", help="rotate clockwise by degrees")
    sp.add_argument("input"); sp.add_argument("output"); sp.add_argument("degrees", type=float)
    sp.add_argument("--no-expand", action="store_true", help="keep canvas, clip corners")
    q(sp); sp.set_defaults(func=cmd_rotate)

    sp = sub.add_parser("crop", help="crop a box: x y width height (pixels)")
    sp.add_argument("input"); sp.add_argument("output")
    sp.add_argument("x", type=int); sp.add_argument("y", type=int)
    sp.add_argument("width", type=int); sp.add_argument("height", type=int)
    q(sp); sp.set_defaults(func=cmd_crop)

    sp = sub.add_parser("grayscale", help="convert to grayscale")
    sp.add_argument("input"); sp.add_argument("output"); q(sp); sp.set_defaults(func=cmd_grayscale)

    sp = sub.add_parser("composite", help="overlay an image onto the input")
    sp.add_argument("input"); sp.add_argument("overlay"); sp.add_argument("output")
    sp.add_argument("--x", type=int, default=0); sp.add_argument("--y", type=int, default=0)
    sp.add_argument("--scale", type=float); sp.add_argument("--opacity", type=float, default=1.0)
    q(sp); sp.set_defaults(func=cmd_composite)

    sp = sub.add_parser("optimize", help="re-save smaller (optimize on, optional --quality)")
    sp.add_argument("input"); sp.add_argument("output"); q(sp); sp.set_defaults(func=cmd_optimize)

    sp = sub.add_parser("palette", help="dominant colours in a reference image, measured not eyeballed")
    sp.add_argument("input")
    sp.add_argument("--colours", type=int, default=6, help="how many dominant colours to report (default 6)")
    sp.add_argument("--against", help="hex colour to compute WCAG contrast against each dominant colour")
    sp.set_defaults(func=cmd_palette)

    sp = sub.add_parser("batch", help="apply one core op to every image in a folder")
    sp.add_argument("op", choices=["convert", "resize", "rotate", "grayscale", "optimize"])
    sp.add_argument("in_dir"); sp.add_argument("out_dir")
    sp.add_argument("--recursive", action="store_true")
    sp.add_argument("--to", help="output extension for convert (e.g. webp)")
    sp.add_argument("--width", type=int); sp.add_argument("--height", type=int)
    sp.add_argument("--scale", type=float); sp.add_argument("--fit", action="store_true")
    sp.add_argument("--degrees", type=float, default=0); sp.add_argument("--no-expand", action="store_true")
    q(sp); sp.set_defaults(func=cmd_batch)

    sp = sub.add_parser("grade", help="apply a .cube LUT or match a reference image's colour")
    sp.add_argument("input"); sp.add_argument("output")
    sp.add_argument("--lut", help="path to a .cube 3D LUT")
    sp.add_argument("--match", help="reference image to match colour to")
    q(sp); sp.set_defaults(func=cmd_grade)

    sp = sub.add_parser("raw", help="develop a camera RAW file to a viewable image")
    sp.add_argument("input"); sp.add_argument("output"); q(sp); sp.set_defaults(func=cmd_raw)

    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
