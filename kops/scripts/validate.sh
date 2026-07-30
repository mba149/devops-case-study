#!/usr/bin/env bash

set -euo pipefail

kops_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
values_file="${1:-${kops_root}/values/example.yaml}"

if ! command -v kops >/dev/null 2>&1; then
  echo "kops is required but was not found in PATH" >&2
  exit 1
fi

case "$(kops version)" in
  *"1.36."*) ;;
  *) echo "warning: these manifests were validated with kOps 1.36.x" >&2 ;;
esac

validation_dir="$(mktemp -d "${TMPDIR:-/tmp}/devops-kops-validation.XXXXXX")"
trap 'rm -rf "${validation_dir}"' EXIT

state_uri="file://${validation_dir}/state"
rendered_file="${validation_dir}/rendered.yaml"

"${kops_root}/scripts/render.sh" "${values_file}" "${rendered_file}"
cluster_name="$(awk '$1 == "name:" { print $2; exit }' "${rendered_file}")"

if [[ -z "${cluster_name}" ]]; then
  echo "unable to read cluster name from rendered configuration" >&2
  exit 1
fi

kops replace --force --state "${state_uri}" -f "${rendered_file}"

kops get cluster "${cluster_name}" --state "${state_uri}" >/dev/null
kops get instancegroups --name "${cluster_name}" --state "${state_uri}"

echo "Rendered templates and loaded them into a temporary local kOps state store."
echo "No AWS resources were created or modified."
