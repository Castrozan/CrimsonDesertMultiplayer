#!/usr/bin/env bash
set -euo pipefail
repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export WINEPREFIX="${WINEPREFIX:-$repository_root/build/linux/wineprefix}"
export WINEDEBUG="${WINEDEBUG:--all}"
if [ "$#" -eq 0 ]; then
	set -- --mode relay --delay 50 --offset 0
fi
exec nix shell nixpkgs#wineWow64Packages.stable -c wine "$repository_root/build/linux/bin/cdmp_peer.exe" "$@"
