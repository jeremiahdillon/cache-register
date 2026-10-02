#!/bin/sh
# Run a pinned, checksum-verified gitleaks (downloaded once into ~/.cache/cachereg).
# Usage: scripts/gitleaks.sh git [gitleaks args…]
set -e
VERSION=8.30.1
case "$(uname -s)-$(uname -m)" in
  Darwin-arm64)  ASSET=darwin_arm64; SUM=b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5 ;;
  Darwin-x86_64) ASSET=darwin_x64;   SUM=dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709 ;;
  Linux-x86_64)  ASSET=linux_x64;    SUM=551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb ;;
  Linux-aarch64) ASSET=linux_arm64;  SUM=e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080 ;;
  *) echo "gitleaks.sh: unsupported platform $(uname -s)-$(uname -m)" >&2; exit 1 ;;
esac
DIR="${XDG_CACHE_HOME:-$HOME/.cache}/cachereg/gitleaks-$VERSION"
BIN="$DIR/gitleaks"
if [ ! -x "$BIN" ]; then
  mkdir -p "$DIR"
  TGZ="$DIR/gitleaks.tgz"
  curl -sSfLo "$TGZ" "https://github.com/gitleaks/gitleaks/releases/download/v$VERSION/gitleaks_${VERSION}_${ASSET}.tar.gz"
  echo "$SUM  $TGZ" | shasum -a 256 -c - >/dev/null
  tar -xzf "$TGZ" -C "$DIR" gitleaks
  rm -f "$TGZ"
fi
exec "$BIN" "$@"
