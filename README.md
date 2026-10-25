# Garlic Press: read, search and view PDFs, written in AIL

License: AGPL-3.0 (see `LICENSE`). Moved from kksimp/ail (`tools/pdf`) with its history.

Needs the AIL toolchain: clone [kksimp/ail](https://github.com/kksimp/ail) next to this repo at the commit in `.ail-version`. Commands below use `../ail/ail`; `tools/check.sh` runs check, fmt and the tests against that pin. Builds and tests run on a dev machine, not in a container.

`garlic-press` reads a PDF's text layer: each glyph's text from its font's own
map to Unicode, and its position from the page's matrices, so text is exact
([ADR 0520](https://github.com/kksimp/ail/blob/main/docs/decisions/0520-pdf-reader-on-the-text-layer.md),
[design note](https://github.com/kksimp/ail/blob/main/docs/design/pdf-viewer.md)). A scanned page (images, no
text) is read by OCR written in AIL, only when it is shown or searched
([ADR 0512](https://github.com/kksimp/ail/blob/main/docs/decisions/0512-pdf-ocr-by-nearest-shape.md)).

```sh
../ail/ail run pdf.ail text FILE.pdf [--page N]      # the text; pages split by form feeds
../ail/ail run pdf.ail grep "phrase" FILE.pdf...     # PAGE: line, for each line with a hit
../ail/ail run pdf.ail grep --json "phrase" FILE.pdf # hits with page, line, boxes and spans
../ail/ail run pdf.ail json FILE.pdf [--page N]      # the page model for agents
../ail/ail run pdf.ail info FILE.pdf                 # pages, metadata, scans, unreadable glyphs
../ail/ail run pdf.ail outline FILE.pdf              # bookmarks with their pages
../ail/ail run pdf.ail bench FILE.pdf                # milliseconds per stage
../ail/ail run pdf.ail view FILE.pdf [--find TEXT]   # the viewer, in a window
../ail/ail run pdf.ail view FILE.pdf --find TEXT --keys "n pagedown" --print   # its screen, here
../ail/ail run pdf.ail view FILE.pdf --find TEXT --json                        # its state
../ail/ail run pdf.ail images FILE.pdf --page N --out F.pgm  # decode a page's images
../ail/ail run pdf.ail layout FILE.pdf --page N      # the lines and glyph boxes OCR finds
../ail/ail run pdf.ail train FONT.ttf... --out ocr/shapes.ail  # rebuild OCR's shapes
../ail/ail test pdf.ail                              # the headless tests
```

## Scans

`text`, `grep`, `json` and `view` read a scanned page by OCR the first time
they need it; `--no-ocr` skips it. `json` marks such pages `"ocr": true`
with a `confidence` (mean per word, 0 to 1), and the viewer's title bar says
"scan, read by OCR". Fax (CCITT Group 3 and 4), baseline JPEG and Flate or
raw images are decoded; JBIG2 and JPEG 2000 are not yet. Expect about 1% to
4% wrong characters on clean 200 to 300 dpi scans; search ignores case,
which hides some of them.

Only the pages a command needs are read
([ADR 0511](https://github.com/kksimp/ail/blob/main/docs/decisions/0511-pdf-pages-read-on-demand.md)): `--page
N` reads one, the viewer reads what it shows and searches forward page by
page, and `grep` prints each page's hits as it goes (`--first` stops at the
first page with a match). The viewer's `--json` lists the lines visible on
screen with their positions.

Search ignores case (`--case` keeps it) and whitespace runs, crosses line
breaks, and joins a word hyphenated at a line end. `grep` exits 1 when
nothing matches.

## Viewer keys

| Key | Does |
|---|---|
| `/` or Ctrl-F | type a search; Enter runs it, Escape cancels |
| `n`, Shift-N | next and previous match, across pages |
| PgDn or Space, PgUp or Backspace | next and previous page |
| Down or `j`, Up or `k`, wheel | scroll |
| Home, End | first and last page |
| `q` or Escape | quit |

The page is laid out on text cells at its positions, one cell per typical
character width. Lines with links are blue; matches are yellow, the current
one orange. The window font is Latin-1, so other characters show as `?` on
screen while `--print`, `--json` and search keep them.

## Fixtures

`testdata/make_fixtures.py` writes the hand-made PDFs (a classic table with
a standard font, a cross-reference stream with an object stream and a PNG
predictor, an image-only page, a damaged table). `report.pdf` is LibreOffice
24.2's export of `report.html`, with subset fonts and a ToUnicode CMap. Each
`NAME.txt` is the expected `pdf text`, checked against `pdftotext`; the
gate's `tools` suite compares them. `scan-ocr.pdf` is a
300 dpi Group 4 scan of a paragraph set in FreeSerif (a font the reference
shapes don't include), rendered with `pdftoppm` and compressed with
Pillow; `scan-ocr.txt` is its OCR output, which matches the source text
exactly. Rebuilding the shapes can change it: check it against the source
before updating it.

## Colour images (Garlic)

`image` also decodes web images: `image.decode(bytes)` returns an
`Rgba` (`px[y * width + x]` as `0xAARRGGBB`) for PNG (every colour type and
depth, tRNS, Adam7), JPEG (baseline and progressive, any subsampling, restart
intervals, YCbCr, RGB, CMYK) and the first frame of a GIF. `image.dims` reads
a size from the header alone. Garlic imports the module with `dep image path
../pdf/image caps fs`. Regenerate the fixtures with `testdata/make_fixtures.py`.
