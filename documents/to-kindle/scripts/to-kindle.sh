#!/usr/bin/env bash
# Convert (if needed) and email documents to your Kindle via the himalaya CLI.
set -euo pipefail

KINDLE_ADDR="${KINDLE_ADDR:-YOUR_KINDLE_ADDR@kindle.com}"
MAX_BYTES=$((50 * 1024 * 1024))   # Amazon's per-email limit
REFLOW=0
KEEP=0
OUTDIR=""

usage() {
  cat >&2 <<'U'
usage: to-kindle.sh [--reflow] [--keep] [--outdir DIR] <file> [file...]

  --reflow       ask Amazon to reflow a PDF into Kindle format (subject: Convert).
                 Only meaningful for PDFs; ignored for everything else.
  --keep         keep converted intermediates instead of using a temp dir.
  --outdir DIR   where converted files land (implies --keep).
U
  exit 2
}

args=()
while [ $# -gt 0 ]; do
  case "$1" in
    --reflow) REFLOW=1 ;;
    --convert) REFLOW=1 ;;          # back-compat with the old flag name
    --keep) KEEP=1 ;;
    --outdir) OUTDIR="${2:?--outdir needs a path}"; KEEP=1; shift ;;
    -h|--help) usage ;;
    -*) echo "unknown flag: $1" >&2; usage ;;
    *) args+=("$1") ;;
  esac
  shift
done
[ "${#args[@]}" -gt 0 ] || usage

# Formats Send-to-Kindle accepts directly. Everything else gets converted.
native="epub pdf doc docx txt rtf htm html png gif jpg jpeg bmp"
# Formats we know how to turn into EPUB locally.
convertible="md markdown mobi azw3 azw fb2 odt lit pdb rst textile org tex latex docbook ipynb"

tmpdir=""
cleanup() { if [ -n "$tmpdir" ] && [ "$KEEP" = 0 ]; then rm -rf "$tmpdir"; fi; }
trap cleanup EXIT

workdir() {
  if [ -n "$OUTDIR" ]; then mkdir -p "$OUTDIR"; echo "$OUTDIR"; return; fi
  [ -n "$tmpdir" ] || tmpdir=$(mktemp -d)
  echo "$tmpdir"
}

# convert <file> -> prints path to an .epub, or returns non-zero.
convert_to_epub() {
  local src="$1" ext="$2" out
  out="$(workdir)/$(basename "${src%.*}").epub"

  # calibre handles every ebook format including mobi/azw3/fb2; prefer it when present.
  if command -v ebook-convert >/dev/null 2>&1; then
    ebook-convert "$src" "$out" >/dev/null 2>&1 && { echo "$out"; return 0; }
  fi

  # pandoc covers the markup formats (md, rst, org, odt, docbook, latex, ipynb...).
  case " $ext " in
    " mobi "|" azw3 "|" azw "|" fb2 "|" lit "|" pdb ")
      echo "no converter for .$ext (install calibre: brew install --cask calibre)" >&2
      return 1 ;;
  esac
  if command -v pandoc >/dev/null 2>&1; then
    pandoc "$src" -o "$out" >/dev/null 2>&1 && { echo "$out"; return 0; }
  fi
  echo "conversion failed for .$ext" >&2
  return 1
}

lower() { echo "$1" | tr '[:upper:]' '[:lower:]'; }

rc=0
for f in "${args[@]}"; do
  if [ ! -f "$f" ]; then
    echo "SKIP  $f: no such file" >&2; rc=1; continue
  fi

  ext=$(lower "${f##*.}")
  send="$f"
  note=""

  if [[ " $native " != *" $ext "* ]]; then
    if [[ " $convertible " == *" $ext "* ]]; then
      if out=$(convert_to_epub "$f" "$ext"); then
        send="$out"; note=" (converted .$ext -> .epub)"
      else
        echo "SKIP  $f: conversion failed" >&2; rc=1; continue
      fi
    else
      echo "WARN  $f: .$ext is neither native nor convertible; sending as-is" >&2
    fi
  fi

  size=$(stat -f%z "$send")
  if [ "$size" -gt "$MAX_BYTES" ]; then
    echo "SKIP  $send: $((size/1024/1024))MB exceeds Amazon's 50MB limit" >&2; rc=1; continue
  fi

  # Amazon keys PDF reflow off the literal subject "Convert".
  subject="$(basename "$send")"
  if [ "$REFLOW" = 1 ] && [ "$(lower "${send##*.}")" = pdf ]; then
    subject="Convert"; note="$note (Amazon reflow requested)"
  fi

  if himalaya message compose \
       --to "$KINDLE_ADDR" \
       --subject "$subject" \
       --body "Sent from to-kindle." \
       --attach "$send" \
       --send >/dev/null 2>&1; then
    echo "SENT  $(basename "$send") -> $KINDLE_ADDR ($((size/1024))KB)$note"
  else
    echo "FAIL  $send: himalaya send failed" >&2; rc=1
  fi
done
exit $rc
