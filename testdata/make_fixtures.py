"""Writes the small hand-made PDFs in this directory (fixture generator
only; the reader is tools/pdf). Each one exercises a structure: a classic
table with a standard font, a cross-reference stream with an object stream
and a PNG predictor, an image-only page, and a damaged table.

    python3 tools/pdf/testdata/make_fixtures.py
"""
import os
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))


def classic(objs, root=1, extra=b""):
    out = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offs = []
    for i, body in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    x = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    for o in offs:
        out += b"%010d 00000 n \n" % o
    out += b"trailer\n<< /Size %d /Root %d 0 R%s >>\nstartxref\n%d\n%%%%EOF\n" % (len(objs) + 1, root, extra, x)
    return out


def stream(d, data):
    return b"<< " + d + b" /Length %d >>\nstream\n" % len(data) + data + b"\nendstream"


def simple():
    content = b"""BT /F1 24 Tf 72 720 Td (Hello, PDF) Tj ET
BT /F1 12 Tf 72 690 Td 14 TL (Standard fonts have no widths in the file,) Tj
T* (so the reader estimates them.) Tj T* [(Kerned) -250 (words)] TJ
T* (Caf\\351 \\(parens\\) and a backslash \\\\) Tj ET"""
    return classic([
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 /MediaBox [0 0 612 792] >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        stream(b"", content),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
        b"<< /Title (Simple fixture) /Author (AIL) >>",
    ], extra=b" /Info 6 0 R")


def png_up(rows, width):
    out = b""
    prev = bytes(width)
    for r in rows:
        out += b"\x02" + bytes((r[i] - prev[i]) % 256 for i in range(width))
        prev = r
    return out


def xref_stream():
    """Objects 1-4 in an object stream; a Differences encoding and a form
    XObject; the table is a cross-reference stream with /Predictor 12."""
    content = zlib.compress(b"BT /F1 20 Tf 72 700 Td <0102030405> Tj ET q 1 0 0 1 72 600 cm /X1 Do Q")
    form = b"BT /F1 10 Tf 0 0 Td (Inside a form) Tj ET"
    inner = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 800] /Resources << /Font << /F1 4 0 R >> /XObject << /X1 7 0 R >> >> /Contents 6 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Times-Roman /FirstChar 1 /LastChar 5 /Widths [500 500 500 500 500] /Encoding << /Differences [1 /fi /n /e /eacute /space] >> >>",
    ]
    head = b""
    body = b""
    for i, o in enumerate(inner, 1):
        head += b"%d %d " % (i, len(body))
        body += o + b" "
    objstm = zlib.compress(head + body)
    out = b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n"
    offs = {}
    offs[5] = len(out)
    out += b"5 0 obj\n" + stream(b"/Type /ObjStm /N 4 /First %d /Filter /FlateDecode" % len(head), objstm) + b"\nendobj\n"
    offs[6] = len(out)
    out += b"6 0 obj\n" + stream(b"/Filter /FlateDecode", content) + b"\nendobj\n"
    offs[7] = len(out)
    out += b"7 0 obj\n" + stream(b"/Type /XObject /Subtype /Form /BBox [0 0 200 50] /Resources << /Font << /F1 4 0 R >> >>", form) + b"\nendobj\n"
    offs[8] = len(out)
    rows = [bytes([0, 0, 0, 0, 0])]
    for i in range(1, 5):
        rows.append(bytes([2, 0, 0, 5, i - 1]))
    for i in (5, 6, 7, 8):
        o = offs[i]
        rows.append(bytes([1, (o >> 16) & 255, (o >> 8) & 255, o & 255, 0]))
    data = zlib.compress(png_up(rows, 5))
    d = b"/Type /XRef /Size 9 /W [1 3 1] /Root 1 0 R /Filter /FlateDecode /DecodeParms << /Predictor 12 /Columns 5 >>"
    out += b"8 0 obj\n" + stream(d, data) + b"\nendobj\nstartxref\n%d\n%%%%EOF\n" % offs[8]
    return out


def scan():
    img = zlib.compress(bytes(64 * 64))
    return classic([
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /XObject << /Im1 5 0 R >> >> /Contents 4 0 R >>",
        stream(b"", b"q 612 0 0 792 0 0 cm /Im1 Do Q"),
        stream(b"/Type /XObject /Subtype /Image /Width 64 /Height 64 /ColorSpace /DeviceGray /BitsPerComponent 8 /Filter /FlateDecode", img),
    ])


def damaged():
    good = simple()
    # Point startxref at nonsense and shift every object by a comment, so
    # the reader has to rebuild the table by scanning.
    good = good.replace(b"%\xe2\xe3\xcf\xd3\n", b"%\xe2\xe3\xcf\xd3\n% inserted after the table was written\n", 1)
    i = good.rindex(b"startxref")
    return good[:i] + b"startxref\n999999\n%%EOF\n"


for name, data in [("simple.pdf", simple()), ("xrefstream.pdf", xref_stream()), ("scan.pdf", scan()), ("damaged.pdf", damaged())]:
    with open(os.path.join(HERE, name), "wb") as f:
        f.write(data)
