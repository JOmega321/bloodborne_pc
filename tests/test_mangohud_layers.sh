#!/usr/bin/env bash
# run.sh's MangoHud block: which layers it disables. Runs the block alone against fake layer
# directories. It proves the disable list, not that the overlay draws (that needs a real run).
set -euo pipefail
here=$(cd -- "$(dirname -- "$0")/.." && pwd)
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
block=$work/block.sh
awk '/^if \[\[ \$\{MANGOHUD:-0\} == 1 \]\]; then$/ {on=1} on {print} on && /^fi$/ {exit}' "$here/run.sh" > "$block"
[[ -s $block ]] || { echo "FAIL: MangoHud block not found in run.sh"; exit 1; }

bundled=$work/nix/store/abc-mangohud-0.8.4/share
host=$work/host/share
mkdir -p "$bundled/vulkan/implicit_layer.d" "$host/vulkan/implicit_layer.d" "$work/home"
layer() { printf '{"layer": {"name": "%s"}, "enable_environment": {"MANGOHUD": "1"}, "disable_environment": {"DISABLE_MANGOHUD": "1"}}\n' "$1"; }
layer VK_LAYER_MANGOHUD_overlay_64_x86_64 > "$bundled/vulkan/implicit_layer.d/MangoHud.x86_64.json"

# Prints VK_LOADER_LAYERS_DISABLE after the block ("-" when unset). $1: BB_PREBUILT, $2: XDG_DATA_DIRS.
run_block() {
    env -i PATH="$PATH" HOME="$work/home" XDG_DATA_HOME="$work/home/.local/share" \
        MANGOHUD=1 BB_PREBUILT="$1" XDG_DATA_DIRS="$2" bash -c \
        'pgrep() { return 1; }; source "$1" > /dev/null; echo "${VK_LOADER_LAYERS_DISABLE:--}"' _ "$block"
}
expect() {
    [[ $2 == "$3" ]] || { echo "FAIL: $1: got '$2', want '$3'"; exit 1; }
    echo "ok: $1"
}

packaged="$bundled:$host"
expect "no host MangoHud" "$(run_block 1 "$packaged")" "-"
layer VK_LAYER_MANGOHUD_overlay_x86_64 > "$host/vulkan/implicit_layer.d/MangoHud.x86_64.json"
layer VK_LAYER_MANGOHUD_overlay_x86 > "$host/vulkan/implicit_layer.d/MangoHud.x86.json"
expect "Fedora-style host layers are disabled, the bundled stays" \
    "$(run_block 1 "$packaged")" "VK_LAYER_MANGOHUD_overlay_x86,VK_LAYER_MANGOHUD_overlay_x86_64"
layer VK_LAYER_MANGOHUD_overlay_64_x86_64 > "$host/vulkan/implicit_layer.d/MangoHud.x86_64.json"
rm "$host/vulkan/implicit_layer.d/MangoHud.x86.json"
expect "a host layer with the bundled name is not disabled (the loader keeps the first)" \
    "$(run_block 1 "$packaged")" "-"
layer VK_LAYER_MANGOHUD_overlay_x86_64 > "$host/vulkan/implicit_layer.d/MangoHud.x86_64.json"
expect "from source: nothing is disabled" "$(run_block "" "$host")" "-"
echo "all ok"
