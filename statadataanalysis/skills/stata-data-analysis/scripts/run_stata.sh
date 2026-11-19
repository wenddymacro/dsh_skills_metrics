#!/usr/bin/env bash
# run_stata.sh -- run a do-file in Stata batch mode from the current directory and check its log.
#
# Usage:
#   run_stata.sh --which-stata          print the Stata binary that would be used
#   run_stata.sh --version              print the Stata version (c(stata_version))
#   run_stata.sh [--tail N] FILE.do [ARG ...]
#
#   FILE.do  do-file path, relative to the current directory (the project root) or absolute.
#            Paths inside the do-file are resolved against the current directory.
#   ARG      passed to the do-file as `1', `2', ...
#   --tail N lines of the log to print at the end (default 40; 0 prints none)
#
# Environment:
#   STATA_BIN  path to a Stata console binary (stata-mp / stata-se / stata);
#              found automatically when unset.
#
# The batch log <basename>.log is left next to the do-file. The script prints
# the log path, any Stata error code with the lines before it, the warnings that
# usually mean a silently wrong result (collinearity, singletons, non-convergence,
# singular VCE, perfect prediction), and the last N lines of the log.
# Exit status: 0 = ran without an r(###) error, 1 = Stata stopped with an error,
# 2 = bad arguments or Stata not found.

set -euo pipefail

die() { echo "run_stata: $*" >&2; exit 2; }

find_stata() {
  if [[ -n "${STATA_BIN:-}" ]]; then
    [[ -x "$STATA_BIN" ]] || die "STATA_BIN=$STATA_BIN is not executable"
    echo "$STATA_BIN"; return
  fi
  local name candidate
  for name in stata-mp stata-se stata stata-be; do
    if command -v "$name" >/dev/null 2>&1; then command -v "$name"; return; fi
  done
  # macOS app bundles, then Linux defaults.
  for candidate in \
    /Applications/StataNow/Stata*.app/Contents/MacOS/stata-* \
    /Applications/Stata*/Stata*.app/Contents/MacOS/stata-* \
    /Applications/Stata/Stata*.app/Contents/MacOS/stata-* \
    /usr/local/stata*/stata-mp /usr/local/stata*/stata-se /usr/local/stata*/stata; do
    if [[ -x "$candidate" ]]; then echo "$candidate"; return; fi
  done
  die "Stata not found. Install Stata 16+ or set STATA_BIN to its console binary (e.g. .../StataMP.app/Contents/MacOS/stata-mp)."
}

tail_n=40
while [[ $# -gt 0 ]]; do
  case "$1" in
    --which-stata) find_stata; exit 0 ;;
    --version)
      stata="$(find_stata)"
      work="$(mktemp -d "${TMPDIR:-/tmp}/runstata.XXXXXX")"
      trap 'rm -rf "$work"' EXIT
      printf 'display "__V__" c(stata_version)\n' > "$work/v.do"
      (cd "$work" && "$stata" -b do v.do) >/dev/null 2>&1 || true
      v="$(grep -Eo '^__V__[0-9.]+' "$work/v.log" 2>/dev/null | head -1 || true)"
      [[ -n "$v" ]] || die "could not read the Stata version (binary: $stata)"
      echo "${v#__V__}"; exit 0 ;;
    --tail) [[ $# -ge 2 && "$2" =~ ^[0-9]+$ ]] || die "--tail needs a number"; tail_n="$2"; shift 2 ;;
    -h|--help) sed -n '2,25p' "${BASH_SOURCE[0]}"; exit 0 ;;
    --) shift; break ;;
    -*) die "unknown flag $1" ;;
    *) break ;;
  esac
done

[[ $# -ge 1 ]] || die "expected FILE.do [ARG ...]; run with --help"
dofile="$1"; shift
[[ "$dofile" == *.do ]] || die "not a do-file: $dofile"
[[ -f "$dofile" ]] || die "do-file not found: $dofile"
[[ "$dofile" != *" "* ]] || die "Stata batch mode cannot take a do-file path with spaces: $dofile"

stata="$(find_stata)"
# Batch mode always writes <basename>.log into the cwd; move it next to the do-file
# so batch logs do not pile up in the project root.
cwd_log="$PWD/$(basename "${dofile%.do}").log"
log="$(cd "$(dirname "$dofile")" && pwd)/$(basename "${dofile%.do}").log"
rm -f "$cwd_log" "$log"

"$stata" -b do "$dofile" "$@" || true
[[ -f "$cwd_log" ]] || die "Stata produced no log at $cwd_log (binary: $stata)"
[[ "$cwd_log" == "$log" ]] || mv "$cwd_log" "$log"

echo "log: $log"

status=0
# Batch mode exits 0 even when the do-file fails; an `r(###);` line is the error.
if grep -Eq '^r\([0-9]+\);' "$log"; then
  code="$(grep -Eo '^r\([0-9]+\)' "$log" | head -1)"
  line="$(grep -nE '^r\([0-9]+\);' "$log" | head -1 | cut -d: -f1)"
  echo "ERROR: Stata stopped with $code at log line $line. Context:"
  start=$(( line > 15 ? line - 15 : 1 ))
  sed -n "${start},${line}p" "$log"
  status=1
fi

warn='omitted because of collinearity|singleton observations? dropped|convergence not achieved|not concave|backed up|variance matrix is nonsymmetric or highly singular|predicts (success|failure) perfectly|observations? (not used|completely determined)'
if grep -Eqi "$warn" "$log"; then
  echo "WARNINGS (check whether they change the result):"
  grep -nEi "$warn" "$log" | head -40
fi

if [[ $tail_n -gt 0 ]]; then
  echo "--- last $tail_n lines ---"
  tail -n "$tail_n" "$log"
fi
exit $status
