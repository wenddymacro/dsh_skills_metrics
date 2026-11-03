#!/usr/bin/env bash
# run_whichdid.sh -- run the bundled `whichdidshouldiuse` Stata command in batch mode.
#
# Usage:
#   run_whichdid.sh --describe DATA
#   run_whichdid.sh --which-stata
#   run_whichdid.sh [--prep 'STATA CODE'] [--if 'EXPR'] DATA Y G T D [OPTION ...]
#
#   DATA     .dta, .csv or .xlsx/.xls file (absolute or relative to the cwd)
#   Y G T D  outcome, group id, calendar time, treatment -- in that order
#   OPTION   options passed after the comma, e.g. `detail` or `strict`
#   --prep   Stata code run after loading and before classifying (e.g. a reshape);
#            separate several commands with `;` or newlines
#   --if     an `if` qualifier, without the word `if`
#
# Environment:
#   STATA_BIN  path to a Stata console binary (stata-mp / stata-se / stata);
#              found automatically when unset.
#
# Prints the classification report followed by `return list`. Exits non-zero
# when Stata is missing or the do-file stops with an error code.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ADO_DIR="$SKILL_DIR/stata"

die() { echo "run_whichdid: $*" >&2; exit 2; }

find_stata() {
  if [[ -n "${STATA_BIN:-}" ]]; then
    [[ -x "$STATA_BIN" ]] || die "STATA_BIN=$STATA_BIN is not executable"
    echo "$STATA_BIN"; return
  fi
  local name candidate
  for name in stata-mp stata-se stata stata-be; do
    if command -v "$name" >/dev/null 2>&1; then command -v "$name"; return; fi
  done
  # macOS app bundles (StataNow before versioned installs), then Linux defaults.
  for candidate in \
    /Applications/StataNow/Stata*.app/Contents/MacOS/stata-* \
    /Applications/Stata*/Stata*.app/Contents/MacOS/stata-* \
    /Applications/Stata/Stata*.app/Contents/MacOS/stata-* \
    /usr/local/stata*/stata-mp /usr/local/stata*/stata-se /usr/local/stata*/stata; do
    if [[ -x "$candidate" ]]; then echo "$candidate"; return; fi
  done
  die "Stata not found. Install Stata 16+ or set STATA_BIN to its console binary (e.g. .../StataMP.app/Contents/MacOS/stata-mp)."
}

# Stata string literal: compound quotes survive embedded double quotes.
stata_str() { printf '`"%s"'"'" "$1"; }

load_cmd() {
  local file="$1" lower
  lower="$(printf '%s' "$file" | tr '[:upper:]' '[:lower:]')"
  case "$lower" in
    *.dta) echo "use $(stata_str "$file"), clear" ;;
    *.csv) echo "import delimited using $(stata_str "$file"), clear varnames(1)" ;;
    *.xlsx|*.xls) echo "import excel using $(stata_str "$file"), clear firstrow" ;;
    *) die "unsupported data file '$file' (use .dta, .csv, .xlsx or .xls)" ;;
  esac
}

describe=0 prep="" ifexpr=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --describe) describe=1; shift ;;
    --which-stata) find_stata; exit 0 ;;
    --prep) [[ $# -ge 2 ]] || die "--prep needs an argument"; prep="$2"; shift 2 ;;
    --if) [[ $# -ge 2 ]] || die "--if needs an argument"; ifexpr="$2"; shift 2 ;;
    -h|--help) sed -n '2,22p' "${BASH_SOURCE[0]}"; exit 0 ;;
    --) shift; break ;;
    -*) die "unknown flag $1" ;;
    *) break ;;
  esac
done

if [[ $describe -eq 1 ]]; then
  [[ $# -eq 1 ]] || die "--describe takes exactly one DATA argument"
else
  [[ $# -ge 5 ]] || die "expected DATA Y G T D [OPTION ...]; run with --help"
fi

data="$1"; shift
[[ -f "$data" ]] || die "data file not found: $data"
data="$(cd "$(dirname "$data")" && pwd)/$(basename "$data")"

stata="$(find_stata)"
work="$(mktemp -d "${TMPDIR:-/tmp}/whichdid.XXXXXX")"
trap 'rm -rf "$work"' EXIT

{
  echo "set more off"
  echo "adopath ++ $(stata_str "$ADO_DIR")"
  echo 'display "__WHICHDID_BEGIN__"'
  load_cmd "$data"
  if [[ $describe -eq 1 ]]; then
    echo "describe"
    echo "summarize"
  else
    if [[ -n "$prep" ]]; then
      printf '%s\n' "$prep" | tr ';' '\n'
    fi
    y="$1" g="$2" t="$3" d="$4"; shift 4
    cmd="whichdidshouldiuse $y $g $t $d"
    [[ -n "$ifexpr" ]] && cmd="$cmd if $ifexpr"
    [[ $# -gt 0 ]] && cmd="$cmd, $*"
    echo "$cmd"
    echo "return list"
  fi
} > "$work/whichdid.do"

(cd "$work" && "$stata" -b do whichdid.do) || true
log="$work/whichdid.log"
[[ -f "$log" ]] || die "Stata produced no log (binary: $stata)"

# Drop Stata's banner (licence details) and echo only what the do-file produced.
awk 'found { print } /^__WHICHDID_BEGIN__/ { found = 1 }' "$log"

# Batch mode exits 0 even when the do-file fails; an `r(###);` line is the error.
if grep -Eq '^r\([0-9]+\);' "$log"; then
  echo "run_whichdid: Stata stopped with $(grep -Eo '^r\([0-9]+\)' "$log" | tail -1)" >&2
  exit 1
fi
