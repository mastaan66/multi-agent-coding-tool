#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="$ROOT_DIR/docs/assets"
FONT="${AI_FACTORY_DEMO_FONT:-DejaVu-Sans-Mono}"
TEMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TEMP_DIR"' EXIT

mkdir -p "$OUTPUT_DIR"

render_frame() {
    local number="$1"
    local command="$2"
    local line_one="$3"
    local line_two="$4"
    local status="$5"

    convert -size 1200x674 "xc:#07101f" \
        -fill "#0d1729" -stroke "#284461" -strokewidth 2 \
        -draw "roundrectangle 36,36 1164,638 18,18" \
        -fill "#ff6b6b" -stroke none -draw "circle 76,76 86,76" \
        -fill "#ffd166" -draw "circle 108,76 118,76" \
        -fill "#55e69b" -draw "circle 140,76 150,76" \
        -font "$FONT" -pointsize 18 -fill "#7897ad" \
        -gravity North -annotate +0+62 "AI Software Factory — quick start" \
        -gravity NorthWest -pointsize 25 -fill "#55e69b" \
        -annotate +72+138 "$" \
        -fill "#e8f4ff" -annotate +105+138 "$command" \
        -pointsize 30 -fill "#62d7ff" -annotate +72+245 "$line_one" \
        -pointsize 25 -fill "#a8c7d5" -annotate +72+315 "$line_two" \
        -fill "#102d2c" -stroke "#55e69b" -strokewidth 2 \
        -draw "roundrectangle 68,520 1132,594 12,12" \
        -stroke none -pointsize 24 -fill "#c8ffe1" \
        -annotate +96+555 "$status" \
        "$TEMP_DIR/frame-${number}.png"
}

render_frame 1 \
    "curl -fsSL …/install.sh | sh" \
    "Install the standalone binary" \
    "Checksums are verified before installation." \
    "✓ Installed to ~/.local/bin/ai-factory"

render_frame 2 \
    'ai-factory --demo "Build a todo API"' \
    "Start without an API key" \
    "Demo mode is deterministic and fully offline." \
    "✓ Architect agent is planning"

render_frame 3 \
    'ai-factory --demo "Build a todo API"' \
    "Planner → Coder → Reviewer" \
    "Tester → Test Runner → Deployer" \
    "✓ All demo tests passed"

render_frame 4 \
    'ls output/todo_api_*' \
    "Source + tests + deployment" \
    "Docker, CI configuration, and instructions included." \
    "✓ Project artifacts written"

render_frame 5 \
    "ai-factory --help" \
    "Ready to build" \
    "Use interactive mode or pass a direct prompt." \
    "✓ Open source under the MIT License"

convert -delay 180 -loop 0 "$TEMP_DIR"/frame-*.png -layers Optimize "$OUTPUT_DIR/demo.gif"

{
    for frame in "$TEMP_DIR"/frame-*.png; do
        printf "file '%s'\n" "$frame"
        printf "duration 2.4\n"
    done
    printf "file '%s'\n" "$TEMP_DIR/frame-5.png"
} > "$TEMP_DIR/frames.txt"

ffmpeg -hide_banner -loglevel error -y \
    -f concat -safe 0 -i "$TEMP_DIR/frames.txt" \
    -vf "fps=30,format=yuv420p" -movflags +faststart -an \
    "$OUTPUT_DIR/demo.mp4"

printf 'Rendered %s and %s\n' "$OUTPUT_DIR/demo.gif" "$OUTPUT_DIR/demo.mp4"
