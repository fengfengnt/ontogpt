#!/usr/bin/env bash
set -euo pipefail
deploy_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
version="$(tr -d '\r\n' < "$deploy_dir/VERSION")"
[[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo 'Invalid ontology VERSION' >&2; exit 1; }
export ONTOLOGY_VERSION="$version"
exec bash "$deploy_dir/../compose.sh" --env-file "$deploy_dir/deployment.env" \
  -f "$deploy_dir/compose.yaml" "$@"
