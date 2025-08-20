#!/bin/bash
# Converts Markdown report to HTML using pandoc (or fallback)

INPUT="$1"
[ -z "$INPUT" ] && echo "Usage: $0 report.md" && exit 1
[ ! -f "$INPUT" ] && echo "File not found: $INPUT" && exit 1

OUTPUT="html/$(basename "$INPUT" .md).html"
mkdir -p html

if command -v pandoc >/dev/null; then
  pandoc "$INPUT" -s -o "$OUTPUT"
else
  # fallback minimal HTML
  echo "<html><body><pre>" > "$OUTPUT"
  cat "$INPUT" >> "$OUTPUT"
  echo "</pre></body></html>" >> "$OUTPUT"
fi

echo "HTML saved to: $OUTPUT"
