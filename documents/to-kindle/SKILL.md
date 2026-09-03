---
name: to-kindle
description: Convert if needed, then email a document to your Kindle so it shows up on the device. Handles EPUB/PDF/DOCX/TXT/HTML natively and converts Markdown, MOBI, AZW3, FB2, ODT, RST and friends to EPUB first. Use when the user says "/to-kindle", "/pdf-to-kindle", "send this to my kindle", "kindle this", "put that PDF on my kindle", "read this on the kindle", or hands over a document and asks to get it onto the Kindle.
---

# To Kindle

Sends a local document to your Kindle by email, converting first when the format
isn't one Send-to-Kindle accepts.

## Usage

```bash
~/.claude/skills/to-kindle/scripts/to-kindle.sh <file> [more files...]
~/.claude/skills/to-kindle/scripts/to-kindle.sh --reflow paper.pdf
~/.claude/skills/to-kindle/scripts/to-kindle.sh --outdir ~/Desktop notes.md
```

One email per file. Prints `SENT` / `SKIP` / `WARN` / `FAIL` per file and exits
non-zero if any failed.

| Flag | Effect |
|---|---|
| `--reflow` | Subject becomes `Convert`, so Amazon reflows a **PDF** into Kindle format. Ignored for non-PDFs. `--convert` still works as an alias. |
| `--keep` | Keep converted intermediates instead of deleting the temp dir. |
| `--outdir DIR` | Where converted files land. Implies `--keep`. |

## Format policy

- **Sent as-is:** `epub pdf doc docx txt rtf htm html png gif jpg jpeg bmp`
- **Converted to EPUB first:** `md markdown mobi azw3 azw fb2 odt lit pdb rst textile org tex latex docbook ipynb`
- **Anything else:** warns and sends anyway.

Conversion prefers `ebook-convert` (calibre) when installed, and falls back to
`pandoc` for the markup formats. The ebook-only formats (mobi, azw3, fb2, lit, pdb)
**need calibre** - `brew install --cask calibre`. Everything pandoc handles works
out of the box.

## Prefer a real EPUB over a reflowed PDF

Kindle can't reflow a PDF, so zoom means panning around a shrunken fixed page - no
font control, no dictionary, no real TOC. `--reflow` hands the job to Amazon's
converter, which is mediocre on long or multi-column documents. If a genuine EPUB
of the same document exists (Project Gutenberg, the publisher, Standard Ebooks),
fetch that instead of reflowing the PDF. Markdown is **not** a Kindle format; it
gets converted to EPUB here, which is the right answer anyway.

Cropping a PDF's margins to reading width (`k2pdfopt`) is possible but still yields
a fixed-layout page. Not worth it when an EPUB is available.

## Prerequisites

- `himalaya` configured at `~/.config/himalaya/config.toml` with the `personal` account.
  Verify with `himalaya mailbox list`.
- `your-amazon-account@example.com` must be on Amazon's **Approved Personal Document E-mail List**
  (Amazon → Manage Your Content and Devices → Preferences → Personal Document Settings).
  If a send succeeds but nothing lands on the device, this is almost always why.
- Destination is `YOUR_KINDLE_ADDR@kindle.com`, overridable with `KINDLE_ADDR`.
- Files over 50MB are skipped (Amazon's per-email limit) - checked *after* conversion.

## Delivery is asynchronous

`SENT` means Gmail accepted the message, not that the Kindle has it. Amazon usually
delivers within a few minutes over Wi-Fi. Don't report it as landed on the device -
tell the user it's sent and to check the Kindle.
