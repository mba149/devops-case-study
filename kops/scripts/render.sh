#!/usr/bin/env bash

set -euo pipefail

kops_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
values_file="${1:-${kops_root}/values/example.yaml}"
output_file="${2:-${kops_root}/generated/example.yaml}"

if ! command -v kops >/dev/null 2>&1; then
  echo "kops is required but was not found in PATH" >&2
  exit 1
fi

if [[ ! -f "${values_file}" ]]; then
  echo "values file not found: ${values_file}" >&2
  exit 1
fi

mkdir -p "$(dirname "${output_file}")"

kops toolbox template template.invalid \
  --values "${values_file}" \
  --template "${kops_root}/templates" \
  --format-yaml \
  --out "${output_file}"

echo "Rendered kOps configuration: ${output_file}"
