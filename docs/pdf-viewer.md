# PDF viewer: search the text layer, OCR for scans

> Non-normative design note, 2026-10-20. The decisions are
> [ADR 0520](../decisions/0520-pdf-reader-on-the-text-layer.md) (text layer),
> [ADR 0511](../decisions/0511-pdf-pages-read-on-demand.md) (pages on demand),
> [ADR 0512](../decisions/0512-pdf-ocr-by-nearest-shape.md) (OCR) and
> [ADR 0513](../decisions/0513-image-decoders-and-font-rasterizer-in-ail.md)
> (image decoders, font rasterizer); the tool is
> [`tools/pdf`](../../tools/pdf/README.md).

## The claim, stated plainly

The designer asked for a PDF viewer that searches PDFs without OCR, using
AIL's machine-first awareness of what is on screen. Most PDFs already carry
their text: a page's content stream shows strings of glyph codes in a font,
and the font says what Unicode each code is (a `/ToUnicode` CMap, or an
encoding whose glyph names map to Unicode, ISO 32000-2 sections 9.6-9.10).
A reader that parses the file, decompresses its streams and runs the text
operators gets every glyph's text and position exactly, with no OCR and no
pixels. That is what `tools/pdf` does.

Two limits are real and no window awareness changes them:

- **Scanned PDFs** are pictures of pages. They have no glyphs, so there is
  no text without OCR. The reader detects them (images painted, no text,
  `image_only`) and, when such a page is shown or searched, reads it by
  OCR in AIL (ADR 0512); its lines then say `ocr` with a `confidence`.
- **Fonts without a Unicode map** (some Type3 and symbolic fonts with no
  `/ToUnicode`) give glyph codes with no meaning. The reader counts them
  (`unreadable`) instead of guessing.

## Architecture

```
tools/pdf/
  pdf.ail            CLI: text, grep, json, info, outline, bench, view, images, layout, train
  reader/            the reader module (no effects except read_file)
    source.ail       bytes (List[int]) and PdfError; read_file (fs.read_bytes)
    inflate.ail      RFC 1950/1951 inflate (fallback for damaged Flate)
    lex.ail          tokens and objects (7.2-7.3)
    doc.ail          xref tables and streams, object streams, repair, pages (7.5, 7.7)
    filters.ail      Flate, LZW, ASCII85, ASCIIHex, RunLength, PNG/TIFF predictors (7.4)
    fonts.ail        codes, ToUnicode CMaps, encodings, glyph names, widths (9.5-9.10)
    content.ail      text state machine to glyphs, glyphs to lines (8.4, 9.3, 9.4)
    model.ail        the page model, lazy `Pages`, links, outline, text strings (7.9, 12.3, 12.5)
    search.ail       normalised search with boxes
  view/view.ail      headless viewer core plus the std.ui window
  image/             the pixel layer (moves to std.ui.image and std.ui.raster)
    image.ail        Gray bitmaps; raw samples, CCITT G3/G4 (T.4, T.6), baseline JPEG (T.81)
    font.ail         TrueType outlines (glyf, loca, cmap 4/12, hmtx, composites); anti-aliased Canvas
  ocr/               OCR of scanned pages (ADR 0512)
    images.ail       an image XObject as grey or as ink runs (fax straight from its changing elements)
    layout.ail       Otsu threshold, runs, components, lines, words, marks
    recognize.ail    features (ink and edge grids, geometry) and nearest-shape classification
    read.ail         `Ocr.page`: recognise once, map words to page space, feed the line builder
    train.ail        reference shapes from fonts (`pdf train`)
    shapes.ail       the generated reference shapes
```

The viewer follows the editor's shape (ADR 0181): a `Viewer` value, keys
that change it, and a pure `render` to runs. The window, `--print` and the
tests draw the same runs.

## The PDF subset read today

| Area | Supported | Not yet |
|---|---|---|
| File structure | classic tables, cross-reference streams, hybrid files, `/Prev` chains, object streams, rebuild by scanning when damaged | linearization hints (ignored, harmless) |
| Filters | Flate and LZW with predictors, ASCII85, ASCIIHex, RunLength; for images CCITT G3/G4 and baseline JPEG | JBIG2, JPEG 2000, progressive and CMYK JPEG |
| Security | none | encryption; most "encrypted" files use an empty user password (RC4 or AES with MD5/SHA-256), so this is the next slice |
| Fonts | Type1, TrueType, Type3, Type0 with Identity or embedded CMaps; ToUnicode bfchar/bfrange; Standard and WinAnsi encodings with Differences; glyph names incl. `uniXXXX` | MacRoman and MacExpert tables; predefined CJK CMaps (UniGB-UCS2-H and friends) |
| Text state | `Tc Tw Tz TL Ts Tf Td TD Tm T* Tj TJ ' "`, `q Q cm`, form XObjects, inline images skipped | vertical writing; rotated text is read but laid out as horizontal |
| Document | page tree inheritance, CropBox/MediaBox, link annotations (URI, GoTo, named destinations), outline, Info | tagged-PDF structure tree (reading order from tags), form fields, annotations' text |

Reading order is content order with lines grouped by baseline. That matches
`pdftotext -raw` and keeps label-value pairs together; tagged PDFs give a
better order and are the planned improvement.

## The agent-facing surface

Agents should never need a screenshot of a PDF. Every command has a
machine form:

- `pdf json FILE [--page N]`: per page `width`, `height`, `rotate`,
  `lines` (`text`, `x`, `y`, `size`, `right`), `links` (`rect`, `uri`,
  `page`), `images`, `unreadable`, `image_only`; plus `info` and `outline`.
  Coordinates are points from the crop box's lower left, rounded to 0.01.
- `pdf grep --json PATTERN FILE...`: one object per hit with `page`,
  `line`, `text`, `boxes` and `spans` (`[line, a, b]` character ranges).
  Search ignores case and runs of whitespace, crosses line breaks, and joins
  a word hyphenated at a line end. Exit status 1 when nothing matches.
- `pdf view FILE --print` and `--json`: the viewer's screen as text, and its
  state (page, scroll, query, hits, the rows on screen, `visible`: the
  page's lines with a character on screen, with positions, and
  `pages_read`). This is the "window awareness": the viewer knows which
  document character is in every cell, so what it reports is exactly what a
  person sees, not a recognition of it.

## Only what is asked for is read (ADR 0511)

Readers that parse the whole document before showing page one pay for
pages nobody looks at. `tools/pdf` opens a file by reading the
cross-reference data and the page tree only. `Pages.get(i)` reads a page's
content the first time it is needed and keeps it. `text --page N` and
`json --page N` read one page; the viewer reads the pages it shows; its
search reads forward page by page and stops at the first page with a match
(`n` reads on from there); `grep` prints each page's hits as soon as that
page is read, and `--first` stops at the first page with a match. Only
`info`, `outline` and a whole-document `text` or `grep` read every page.

## OCR of scanned pages (ADR 0512)

A page that paints images and shows no text is read by OCR the first time
it is shown or searched, and the result is cached with the page. Each
image is decoded to ink runs (fax data straight from its changing
elements, never as pixels), components are grouped into lines and words,
each glyph is described by 212 features (an 8 by 8 ink grid, four 6 by 6
outline-edge grids, and its size and position against the line), and the
nearest of 1,399 reference shapes names it. Look-alikes are settled by the
word (l, I, 1; o, 0). Words are mapped to page space through the matrix
the image was painted with, then go through the same line builder as
text-layer glyphs, so `grep`, `json` and the viewer need no OCR-specific
code. `--no-ocr` turns it off.

The reference shapes are drawn by the AIL rasterizer from DejaVu,
Liberation, Carlito and Caladea (the designer's choice), cut out by the
same layout code that reads scans, averaged per font and merged to at most
eight per character (`pdf train`). Touching pairs (fi, ff, ti, rn...) are
shapes of their own. Accuracy on unseen fonts is in ADR 0512: 0.4% to 3.3%
character errors on 300 dpi fax scans, 2.4% to 3.9% on 200 dpi JPEG.

`pdf images FILE --page N --out F.pgm` and `pdf layout FILE` show the
decoded image and the lines and glyph boxes found, for checking a scan
that reads badly.

## The pixel layer (ADR 0513)

`tools/pdf/image` holds what OCR, the PDF pixel view, Garlic and the
editor share, written from the standards: `Gray` bitmaps (0 black to 255
white); `from_samples` and `from_indexed` for raw samples (1 to 16 bits,
grey, RGB, CMYK, palettes); `ccitt` and `ccitt_rows` for fax (Group 3
one- and two-dimensional, Group 4); `jpeg` for baseline and extended
Huffman JPEG, with the inverse DCT of a whole plane done as two matrix
products; `Font.parse`, `glyph`, `advance` and `outline` for TrueType; and
`Canvas` (`glyph`, `text`, `gray`), which adds each edge's signed area to
the pixels it crosses and sums along the row. Decoded images match the
reference decoders (fax and Flate exactly, JPEG within one grey level of
libjpeg). The modules move to `std.ui.image` and `std.ui.raster` (agreed
with the window-layer owner) once the API settles; an RGB bitmap joins
`Gray` when a colour user needs one.

## Measurements (2026-10-20, Linux x86-64, release bootstrap)

| Input | AIL reader | `pdftotext` (C++) |
|---|---|---|
| 2-page LibreOffice report, 29 KB | 125 ms for `pdf text`, process start included | 12 ms |
| 53-page LibreOffice document, 231 KB, 252,529 glyphs: every page | 3.0 s (`grep`; read 4 ms, pages 2.8 s) | 0.08 s |
| the same, one page: `text --page 30`, `view --page 30 --print` | 0.18-0.23 s | 0.02 s |
| the same, `grep --first` (hit on page 1) | 0.18 s | n/a |
| OCR of a 300 dpi Group 4 page (931 glyphs), `pdf text` | 2.3 s: shapes 0.25, ink 0.28, layout 0.16, features 0.9, classify 0.6 | Tesseract: not installed here |
| OCR of a 200 dpi JPEG page | ~6 s, of which JPEG decoding ~4 s | |
| Decoding a 1654 by 2339 Group 4 page | 0.27 s | |

Text output matches `pdftotext` on the LibreOffice fixtures and on a
10-page ReportLab PDF, apart from line order on the ReportLab one (content
order versus `pdftotext`'s layout order). The cost is the interpreter: about
7 µs per glyph on the bytecode tier. The first speed pass (decode each
font's codes once, move the text matrix by its translation only) took the
53-page file from 4.3 s to 2.9 s. The native backend (lane 120) is where
the rest comes from; `pdf bench FILE` tracks it. The source is 3,249 lines,
33,570 tokens (tokbench mean).

## Dependencies and stopgaps

| Need | Today | Replaced by |
|---|---|---|
| Binary file reads | done: `fs.read_bytes` (lane 123); the `od` stopgap is gone (19 ms to 4 ms on the report) | |
| Flate | done: `std.compress.unzlib`, falling back to `inflate_zlib` on any error (truncated streams, bad Adler-32) | |
| Byte strings | `List[int]` | `bytes` (lane 123) |
| Regex search | plain substring | `std.regex` (lane 127, merged) as `pdf grep --regex` |

## What the window layer needs for pixels

The viewer draws the text layer on the text-cell grid. Drawing pages as
they look needs, in `std.ui` or a new `std.canvas`:

1. **A pixel surface**: `blit(x, y, w, h, rgba)` of a framebuffer region,
   or a canvas with `fill_rect`, `fill_path` (non-zero and even-odd) and
   `stroke_path`, with a transform and clip. The bootstrap's minifb window is
   already a framebuffer, so this is a thin addition.
2. **Glyph outlines**: TrueType outlines and an anti-aliased rasteriser
   are done (`tools/pdf/image/font.ail`, ADR 0513); CFF (Type 2
   charstrings) and Type 1 fonts are still needed for embedded fonts.
3. **Images**: done for fax, baseline JPEG and raw samples
   (`tools/pdf/image/image.ail`); JPX and JBIG2 later.
4. **Colour**: DeviceRGB/Gray/CMYK, ICC as sRGB approximations.
5. **HiDPI and scaling** (already listed in [gui-path.md](gui-path.md)).

None of this is needed for search or for agents. A pixel view would overlay
the same page model, so search hits and agent queries keep working on it.

## Rejected alternatives

- **OCR on every page.** Slower, lossy, and pointless where the text is in
  the file; OCR runs only on image-only pages (ADR 0512).
- **A neural recogniser or Tesseract.** See ADR 0512: a network needs
  weights and training and is slower on the interpreter; Tesseract is an
  external C++ library (ADR 0009, ADR 0010).
- **Linking a C library (Poppler, MuPDF, pdf.js).** ADR 0009 (custom
  tooling) and ADR 0010 (no external backend) rule it out; MuPDF's AGPL also
  conflicts with the licence (ADR 0510).
- **Waiting for `bytes` and `std.compress` before starting.** The stopgaps
  are two functions; the parser, fonts, search and viewer are written
  against `List[int]` and are unaffected by the swap.
- **Reading-order heuristics (column detection) first.** Content order is
  right for most generated PDFs; tagged structure is the better source and
  comes next.

## Next slices

1. Read pages on several cores (a `par` comprehension needs the object cache
   out of the page reader's `ref`).
2. Decryption with an empty user password (RC4, AES-128, AES-256).
3. `--regex` through `std.regex`; MacRoman; predefined CJK CMaps.
4. Tagged-PDF reading order; form fields and annotation text.
5. Pixel rendering once the window layer has a surface (above).
6. OCR: page-adaptive shapes (re-learn confident glyphs on the page),
   correction against the document's own vocabulary, skew correction,
   splitting touching glyphs, OCR of images on pages that also have text,
   and speed (argmax and broadcasting in `std.tensor`, asked of lane 154;
   the native backend).
