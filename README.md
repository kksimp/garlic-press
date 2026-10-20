# pdf: read, search and view PDFs, written in AIL

`tools/pdf` reads a PDF's text layer: each glyph's text from its font's own
map to Unicode, and its position from the page's matrices. There is no OCR,
so text is exact; a scanned page (images, no text) is reported as needing
OCR instead ([ADR 0520](../../docs/decisions/0520-pdf-reader-on-the-text-layer.md),
[design note](../../docs/design/pdf-viewer.md)).

```sh
./ail run tools/pdf/pdf.ail text FILE.pdf [--page N]      # the text; pages split by form feeds
./ail run tools/pdf/pdf.ail grep "phrase" FILE.pdf...     # PAGE: line, for each line with a hit
./ail run tools/pdf/pdf.ail grep --json "phrase" FILE.pdf # hits with page, line, boxes and spans
./ail run tools/pdf/pdf.ail json FILE.pdf [--page N]      # the page model for agents
./ail run tools/pdf/pdf.ail info FILE.pdf                 # pages, metadata, scans, unreadable glyphs
./ail run tools/pdf/pdf.ail outline FILE.pdf              # bookmarks with their pages
./ail run tools/pdf/pdf.ail bench FILE.pdf                # milliseconds per stage
./ail run tools/pdf/pdf.ail view FILE.pdf [--find TEXT]   # the viewer, in a window
./ail run tools/pdf/pdf.ail view FILE.pdf --find TEXT --keys "n pagedown" --print   # its screen, here
./ail run tools/pdf/pdf.ail view FILE.pdf --find TEXT --json                        # its state
./ail test tools/pdf/pdf.ail                              # the headless tests
```

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
selftest (`bootstrap/tests/tools.rs`) compares them.
