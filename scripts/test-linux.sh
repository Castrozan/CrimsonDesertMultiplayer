#!/usr/bin/env bash
set -euo pipefail
repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export WINEPREFIX="${WINEPREFIX:-$repository_root/build/linux/wineprefix}"
export WINEDEBUG="${WINEDEBUG:--all}"
exec nix shell nixpkgs#wineWow64Packages.stable -c wine "$repository_root/build/linux/bin/cdmp_tests.exe" "$@"
