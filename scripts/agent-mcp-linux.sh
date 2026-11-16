#!/usr/bin/env bash
set -euo pipefail
repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python_environment='(builtins.getAttr builtins.currentSystem (builtins.getFlake "nixpkgs").legacyPackages).python3.withPackages (packages: [ packages.mcp packages.evdev packages.hypothesis ])'
cd "$repository_root/tools/agent_mcp"
if [[ "${1:-}" == "test" ]]; then
  exec nix shell --impure --expr "$python_environment" -c python -m unittest discover -s tests -t .
fi
exec nix shell --impure --expr "$python_environment" -c python -m agent_mcp
