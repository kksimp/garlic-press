"""Writes the small image fixtures in this directory for the decoders in
image (PNG, JPEG, GIF). Each NAME.png/.jpg/.gif has a NAME.rgba
beside it: the expected decode as R, G, B, A bytes row by row, from this
script's own arithmetic for PNG (lossless, exact) and from Pillow's decoder for
JPEG and GIF. Fixture generator only; the tests are in color.ail.

    python3 image/testdata/make_fixtures.py
"""
import os
import struct
import zlib

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = 37, 29


def picture():
    """A smooth gradient with hard edges, so filters and chroma both matter."""
    y, x = np.mgrid[0:H, 0:W]
    r = (x * 255 // (W - 1)).astype(np.uint8)
    g = (y * 255 // (H - 1)).astype(np.uint8)
    b = (((x * 7 + y * 13) % 256)).astype(np.uint8)
    img = np.stack([r, g, b], axis=-1)
    img[8:20, 10:25] = [250, 30, 30]
    img[14:26, 20:33] = [30, 30, 250]
    return img


def chunk(kind, data):
    c = struct.pack(">I", len(data)) + kind + data
    return c + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def pack_row(samples, depth):
    if depth == 16:
        return b"".join(struct.pack(">H", s) for s in samples)
    if depth == 8:
        return bytes(samples)
    out = bytearray()
    acc, n = 0, 0
    for s in samples:
        acc = (acc << depth) | s
        n += depth
        if n == 8:
            out.append(acc)
            acc, n = 0, 0
    if n:
        out.append(acc << (8 - n))
    return bytes(out)


def filtered(rows, bpp, interlace_pass):
    """Filter each row with a different filter type (0-4, rotating)."""
    out = b""
    prev = bytes(len(rows[0])) if rows else b""
    for i, row in enumerate(rows):
        ft = (i + interlace_pass) % 5
        cur = bytearray()
        for j, v in enumerate(row):
            a = row[j - bpp] if j >= bpp else 0
            b = prev[j]
            c = prev[j - bpp] if j >= bpp else 0
            if ft == 0:
                p = 0
            elif ft == 1:
                p = a
            elif ft == 2:
                p = b
            elif ft == 3:
                p = (a + b) // 2
            else:
                pp = a + b - c
                pa, pb, pc = abs(pp - a), abs(pp - b), abs(pp - c)
                p = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
            cur.append((v - p) & 255)
        out += bytes([ft]) + bytes(cur)
        prev = row
    return out


ADAM = [(0, 0, 8, 8), (4, 0, 8, 8), (0, 4, 4, 8), (2, 0, 4, 4), (0, 2, 2, 4), (1, 0, 2, 2), (0, 1, 1, 2)]


def write_png(name, ctype, depth, samples, expected, palette=None, trns=None, interlace=False):
    """`samples[y][x]` is a tuple of the pixel's samples; `expected[y][x]` its RGBA."""
    spp = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[ctype]
    bpp = max(1, spp * depth // 8)
    if interlace:
        passes = [(x0, y0, dx, dy) for x0, y0, dx, dy in ADAM]
    else:
        passes = [(0, 0, 1, 1)]
    raw = b""
    for pi, (x0, y0, dx, dy) in enumerate(passes):
        ys = range(y0, H, dy)
        xs = range(x0, W, dx)
        if not len(ys) or not len(xs):
            continue
        rows = [pack_row([s for x in xs for s in samples[y][x]], depth) for y in ys]
        raw += filtered(rows, bpp, pi)
    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, depth, ctype, 0, 0, 1 if interlace else 0))
    if palette is not None:
        png += chunk(b"PLTE", bytes(v for p in palette for v in p))
    if trns is not None:
        png += chunk(b"tRNS", trns)
    z = zlib.compress(raw, 9)
    half = len(z) // 2
    png += chunk(b"IDAT", z[:half]) + chunk(b"IDAT", z[half:]) + chunk(b"IEND", b"")
    open(os.path.join(HERE, name + ".png"), "wb").write(png)
    write_rgba(name, expected)


def write_rgba(name, rgba):
    data = bytes(v for row in rgba for px in row for v in px)
    open(os.path.join(HERE, name + ".rgba"), "wb").write(data)


def scale(v, depth):
    return v * 255 // ((1 << depth) - 1)


def png_fixtures():
    img = picture()
    # Truecolour, 8 and 16 bits; RGBA; interlaced RGB.
    s = [[tuple(int(c) for c in img[y, x]) for x in range(W)] for y in range(H)]
    e = [[(*px, 255) for px in row] for row in s]
    write_png("rgb8", 2, 8, s, e)
    write_png("rgb8_adam7", 2, 8, s, e, interlace=True)
    s16 = [[tuple(min(c * 257 + (x + y) % 3, 65535) for c in px) for x, px in enumerate(row)] for y, row in enumerate(s)]
    e16 = [[(*(scale(c, 16) for c in px), 255) for px in row] for row in s16]
    write_png("rgb16", 2, 16, s16, e16)
    sa = [[(*px, (x * 255) // (W - 1)) for x, px in enumerate(row)] for row in s]
    write_png("rgba8", 6, 8, sa, sa)
    write_png("rgba8_adam7", 6, 8, sa, sa, interlace=True)
    # Grey at every depth, with and without alpha / colour key.
    for d in (1, 2, 4, 8, 16):
        top = (1 << d) - 1
        g = [[((x * 3 + y * 5) % (top + 1),) for x in range(W)] for y in range(H)]
        eg = [[(scale(v[0], d),) * 3 + (255,) for v in row] for row in g]
        write_png(f"gray{d}", 0, d, g, eg)
    top = 255
    g = [[((x * 3 + y * 5) % 256,) for x in range(W)] for y in range(H)]
    key = 77
    eg = [[(v[0],) * 3 + (0 if v[0] == key else 255,) for v in row] for row in g]
    write_png("gray8_key", 0, 8, g, eg, trns=struct.pack(">H", key))
    ga = [[(v[0], (x * 255) // (W - 1)) for x, v in enumerate(row)] for row in g]
    ega = [[(v[0], v[0], v[0], v[1]) for v in row] for row in ga]
    write_png("graya8", 4, 8, ga, ega)
    write_png("graya8_adam7", 4, 8, ga, ega, interlace=True)
    # RGB colour key.
    ck = [[(0, 0, 0) for _ in range(W)] for _ in range(H)]
    ek = []
    for y in range(H):
        row = []
        for x in range(W):
            px = s[y][x]
            row.append((*px, 0 if px == s[3][3] else 255))
        ek.append(row)
    write_png("rgb8_key", 2, 8, s, ek, trns=bytes([0, s[3][3][0], 0, s[3][3][1], 0, s[3][3][2]]))
    # Palettes at 1, 2, 4 and 8 bits, with partial alpha.
    for d in (1, 2, 4, 8):
        n = min(1 << d, 40)
        pal = [(i * 37 % 256, i * 91 % 256, i * 53 % 256) for i in range(n)]
        alpha = [255 - (i * 20) % 256 if i % 3 == 1 else 255 for i in range(n)]
        idx = [[((x + 2 * y) % n,) for x in range(W)] for y in range(H)]
        ep = [[(*pal[v[0]], alpha[v[0]]) for v in row] for row in idx]
        write_png(f"pal{d}", 3, d, idx, ep, palette=pal, trns=bytes(alpha))
    write_png("pal4_adam7", 3, 4, [[((x + 2 * y) % 16,) for x in range(W)] for y in range(H)],
              [[(*((i * 37 % 256, i * 91 % 256, i * 53 % 256)), 255) for i in [(x + 2 * y) % 16 for x in range(W)]] for y in range(H)],
              palette=[(i * 37 % 256, i * 91 % 256, i * 53 % 256) for i in range(16)], interlace=True)


def pil_rgba(im):
    return np.asarray(im.convert("RGBA")).reshape(H, W, 4)


def jpeg_fixtures():
    img = Image.fromarray(picture(), "RGB")
    cases = {
        "jpeg444": dict(subsampling=0, quality=90),
        "jpeg420": dict(subsampling=2, quality=85),
        "jpeg422": dict(subsampling=1, quality=85),
        "jpeg444_prog": dict(subsampling=0, quality=90, progressive=True),
        "jpeg420_prog": dict(subsampling=2, quality=85, progressive=True),
        "jpeg444_restart": dict(subsampling=0, quality=90, restart_marker_blocks=3),
    }
    for name, kw in cases.items():
        img.save(os.path.join(HERE, name + ".jpg"), "JPEG", **kw)
        write_rgba(name, pil_rgba(Image.open(os.path.join(HERE, name + ".jpg"))))
    gray = img.convert("L")
    gray.save(os.path.join(HERE, "jpeg_gray.jpg"), "JPEG", quality=90)
    write_rgba("jpeg_gray", pil_rgba(Image.open(os.path.join(HERE, "jpeg_gray.jpg"))))
    gray.save(os.path.join(HERE, "jpeg_gray_prog.jpg"), "JPEG", quality=90, progressive=True)
    write_rgba("jpeg_gray_prog", pil_rgba(Image.open(os.path.join(HERE, "jpeg_gray_prog.jpg"))))


def gif_fixtures():
    img = Image.fromarray(picture(), "RGB").quantize(colors=24, dither=Image.Dither.NONE)
    img.save(os.path.join(HERE, "gif24.gif"), "GIF", interlace=False)
    write_rgba("gif24", pil_rgba(Image.open(os.path.join(HERE, "gif24.gif"))))
    img.save(os.path.join(HERE, "gif24_interlaced.gif"), "GIF", interlace=True)
    write_rgba("gif24_interlaced", pil_rgba(Image.open(os.path.join(HERE, "gif24_interlaced.gif"))))
    tr = img.copy()
    tr.save(os.path.join(HERE, "gif24_transparent.gif"), "GIF", transparency=3, interlace=False)
    write_rgba("gif24_transparent", pil_rgba(Image.open(os.path.join(HERE, "gif24_transparent.gif"))))


if __name__ == "__main__":
    png_fixtures()
    jpeg_fixtures()
    gif_fixtures()
