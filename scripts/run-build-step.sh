#!/usr/bin/env bash
set -uo pipefail

if [[ $# -lt 2 ]]; then
    echo "build diagnostic wrapper requires a step name and command" >&2
    exit 2
fi

step_name="$1"
shift
log_file="$(mktemp)"
trap 'rm -f "$log_file"' EXIT

set +e
"$@" 2>&1 | tee "$log_file"
command_status="${PIPESTATUS[0]}"
set -e

if [[ "$command_status" -ne 0 ]]; then
    reason="$(grep -Eia '(^|[[:space:]])(error|fatal|exception|failed|failure)([[:space:]:]|$)|(^|[[:space:]])(CS|MSB)[0-9]+' "$log_file" | tail -n 1 || true)"
    if [[ -z "$reason" ]]; then
        reason="$(tail -n 1 "$log_file" || true)"
    fi
    reason="$(printf '%s' "$reason" \
        | sed -E 's#([[:alpha:]]:)?/[^[:space:]]+#<path>#g; s/[[:space:]]+/ /g; s/%/%25/g' \
        | cut -c1-400)"
    if [[ -z "$reason" ]]; then
        reason="no diagnostic output was produced"
    fi
    echo "build step failed: ${step_name}; exit=${command_status}; reason=${reason}" >&2
    if [[ "${GITHUB_ACTIONS:-}" == "true" ]]; then
        echo "::error title=${step_name} failed::command=${step_name}; exit=${command_status}; reason=${reason}"
    fi
fi

exit "$command_status"
