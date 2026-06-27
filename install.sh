#!/usr/bin/env sh
set -eu

REPOSITORY="mastaan66/multi-agent-coding-tool"
INSTALL_DIR="${AI_FACTORY_INSTALL_DIR:-$HOME/.local/bin}"
VERSION="${AI_FACTORY_VERSION:-latest}"

fail() {
    printf 'ai-factory installer: %s\n' "$1" >&2
    exit 1
}

command -v curl >/dev/null 2>&1 || fail "curl is required"

case "$(uname -s)" in
    Linux) platform="linux" ;;
    Darwin) platform="macos" ;;
    *) fail "supported platforms are Linux and macOS" ;;
esac

case "$(uname -m)" in
    x86_64|amd64) architecture="x86_64" ;;
    arm64|aarch64) architecture="arm64" ;;
    *) fail "unsupported architecture: $(uname -m)" ;;
esac

archive="ai-factory-${platform}-${architecture}.tar.gz"
if [ "$VERSION" = "latest" ]; then
    release_path="latest/download"
else
    release_path="download/${VERSION}"
fi
base_url="https://github.com/${REPOSITORY}/releases/${release_path}"

temporary_dir="$(mktemp -d)"
trap 'rm -rf "$temporary_dir"' EXIT INT TERM

printf 'Downloading %s...\n' "$archive"
curl -fsSL "${base_url}/${archive}" -o "${temporary_dir}/${archive}"
curl -fsSL "${base_url}/${archive}.sha256" -o "${temporary_dir}/${archive}.sha256"

(
    cd "$temporary_dir"
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum -c "${archive}.sha256"
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 -c "${archive}.sha256"
    else
        fail "sha256sum or shasum is required"
    fi
    tar -xzf "$archive"
)

mkdir -p "$INSTALL_DIR"
install -m 755 "${temporary_dir}/ai-factory" "${INSTALL_DIR}/ai-factory"

printf 'Installed ai-factory to %s\n' "$INSTALL_DIR/ai-factory"
case ":$PATH:" in
    *":$INSTALL_DIR:"*) ;;
    *) printf 'Add %s to PATH to run ai-factory globally.\n' "$INSTALL_DIR" ;;
esac
