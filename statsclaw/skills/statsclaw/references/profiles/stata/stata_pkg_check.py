#!/usr/bin/env python3
"""stata_pkg_check.py -- static checks for a Stata command package.

Usage:
    python3 stata_pkg_check.py [--json] [PROJECT_DIR]

Scans PROJECT_DIR (default: the current directory) for .ado, .sthlp, .pkg and
stata.toc files and reports problems that Stata itself does not flag:

  ERROR  ado file defines no program with its own name
  ERROR  a comment line contains "/*" without a closing "*/" (swallows the code after it)
  ERROR  the main command (named like the .pkg) has no help file
  ERROR  .pkg lists a file (f or g line) that does not exist, or lacks the "v 3" first line
  ERROR  stata.toc names a .pkg that does not exist
  WARN   public ado file has no "*!" header line; headers without a version number are counted
  WARN   public command is documented nowhere (own help, a mention in any help file,
         or the estat/predict parent help file) -- rename internal helpers with "_"
  WARN   package version numbers disagree (main ado header or displayed version,
         main help file, "d Version:" in the .pkg, README badge)
  WARN   the main program has no "version" statement
  WARN   eclass main command never sets e(cmd)
  WARN   "set seed" inside an ado (seeds should come from a seed() option)
  WARN   "merge m:m"
  WARN   public ado or help file is not listed in any .pkg

Directories named cert, test, tests, sim, simulations, .statsclaw and .git are
skipped. Exit status: 0 = no ERROR, 1 = at least one ERROR, 2 = bad arguments.
Standard library only.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SKIP_DIRS = {"cert", "test", "tests", "sim", "simulations", ".statsclaw", ".git", "__pycache__"}

PROGRAM_RE = re.compile(r"^\s*program\s+(?:define\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*(,\s*(.*))?$")
VERSION_STMT_RE = re.compile(r"^\s*version\s+\d")
STARBANG_RE = re.compile(r"\bversion\s+v?(\d+(?:\.\d+)+)", re.I)
DISPLAY_VERSION_RE = re.compile(r'"[^"\n]*\bversion\s+v?(\d+\.\d+\.\d+)[^"\n]*"', re.I)
PKG_VERSION_RE = re.compile(r"^\s*d\s+version\s*:?\s*v?(\d+(?:\.\d+)+)", re.I)
README_VERSION_RE = re.compile(r"\bversion[-:\s]+v?(\d+\.\d+\.\d+)", re.I)
HELP_VERSION_RE = re.compile(r"\*!\s*version\s+v?(\d+(?:\.\d+)+)", re.I)
ECMD_RE = re.compile(r"ereturn\s+local\s+cmd\b")
SEED_RE = re.compile(r"^\s*set\s+seed\b")
MERGE_MM_RE = re.compile(r"\bmerge\s+m:m\b")


def walk(root: Path, suffixes: tuple[str, ...]) -> list[Path]:
    out = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if any(part in SKIP_DIRS for part in rel.parts[:-1]):
            continue
        if path.is_file() and path.name.lower().endswith(suffixes):
            out.append(path)
    return out


def comment_swallow(line: str) -> bool:
    """A line comment that opens a block comment it never closes."""
    stripped = line.lstrip()
    if stripped.startswith("*"):
        body = stripped[1:]
    elif "//" in line:
        body = line.split("//", 1)[1]
    else:
        return False
    if "/*" not in body:
        return False
    return body.rfind("*/") < body.rfind("/*")


def programs(text: str) -> list[dict]:
    """Programs in an ado file, each with its options and body lines."""
    found, current = [], None
    for lineno, line in enumerate(text.splitlines(), 1):
        m = PROGRAM_RE.match(line)
        if m and m.group(1) not in {"drop", "dir", "list"}:
            current = {"name": m.group(1), "options": (m.group(3) or "").lower(), "line": lineno, "body": []}
            found.append(current)
            continue
        if re.match(r"^\s*end\s*$", line):
            current = None
            continue
        if current is not None:
            current["body"].append(line)
    return found


def check(root: Path) -> list[dict]:
    issues: list[dict] = []

    def add(level: str, path: Path | None, msg: str, line: int | None = None) -> None:
        issues.append({
            "level": level,
            "file": str(path.relative_to(root)) if path else None,
            "line": line,
            "message": msg,
        })

    ados = walk(root, (".ado",))
    helps = {p.stem.lower(): p for p in walk(root, (".sthlp", ".hlp"))}
    help_text = "\n".join(p.read_text(encoding="utf-8", errors="replace") for p in helps.values()).lower()
    pkgs = walk(root, (".pkg",))
    pkg_names = {p.stem.lower() for p in pkgs}
    listed: set[str] = set()
    versions: list[tuple[str, str]] = []  # (version, where) for the package-level version number
    unversioned: list[str] = []

    def rel(path: Path) -> str:
        return str(path.relative_to(root))

    def documented(name: str) -> bool:
        """Own help file, a mention in any help file, or an estat/predict parent help file."""
        if name in helps or re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", help_text):
            return True
        m = re.match(r"^(.+?_(?:estat|predict))_\w+$", name) or re.match(r"^(.+)_(?:p|estat)$", name)
        return bool(m and m.group(1) in helps)

    for ado in ados:
        text = ado.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        name = ado.stem.lower()
        main = name in pkg_names
        first = next((l for l in lines if l.strip()), "")
        if first.startswith("*!"):
            header = "\n".join(l for l in lines[:5] if l.startswith("*!"))
            m = STARBANG_RE.search(header)
            if m and main:
                versions.append((m.group(1), rel(ado)))
            elif not m:
                unversioned.append(rel(ado))
        elif not name.startswith("_"):
            add("WARN", ado, 'no "*! version X.Y.Z  DDmonYYYY" header line at the top', 1)
        if main:
            for m in DISPLAY_VERSION_RE.finditer(text):
                versions.append((m.group(1), f"{rel(ado)} (displayed)"))

        progs = programs(text)
        if not any(p["name"].lower() == name for p in progs):
            add("ERROR", ado, f"defines no program named {ado.stem}")
        for p in progs:
            if p["name"].lower() != name:
                continue
            if not any(VERSION_STMT_RE.match(l) for l in p["body"][:15]):
                add("WARN", ado, f'program {p["name"]} has no "version" statement near its top', p["line"])
            if "eclass" in p["options"] and (main or name in helps) and not ECMD_RE.search("\n".join(p["body"])):
                add("WARN", ado, f"eclass program {p['name']} never sets e(cmd)", p["line"])

        in_mata = False
        for lineno, line in enumerate(lines, 1):
            if re.match(r"^\s*mata\s*:?\s*$", line):
                in_mata = True
            elif in_mata and re.match(r"^\s*end\s*$", line):
                in_mata = False
            if not in_mata and comment_swallow(line):
                add("ERROR", ado, 'comment contains "/*" without "*/": the code after it is silently skipped', lineno)
            if SEED_RE.match(line):
                add("WARN", ado, '"set seed" inside an ado: take the seed from a seed() option instead', lineno)
            if MERGE_MM_RE.search(line):
                add("WARN", ado, '"merge m:m" pairs observations by sort order; use 1:1 or m:1', lineno)

        if name.startswith("_"):
            pass
        elif main and name not in helps:
            add("ERROR", ado, f"main command {ado.stem} has no help file {ado.stem}.sthlp")
        elif not documented(name):
            add("WARN", ado, f"{ado.stem} is not documented in any help file; if it is internal, rename it with a leading underscore")

    if unversioned:
        shown = ", ".join(unversioned[:3]) + (" …" if len(unversioned) > 3 else "")
        add("WARN", None, f"{len(unversioned)} ado file(s) have a *! header without a version number ({shown}); "
                          "so `which` shows no version for them")

    for stem, hp in helps.items():
        if stem in pkg_names:
            hv = HELP_VERSION_RE.search(hp.read_text(encoding="utf-8", errors="replace")[:2000])
            if hv:
                versions.append((hv.group(1), rel(hp)))

    for pkg in pkgs:
        lines = pkg.read_text(encoding="utf-8", errors="replace").splitlines()
        first = next((l.strip() for l in lines if l.strip()), "")
        if first != "v 3":
            add("ERROR", pkg, 'first line must be "v 3"', 1)
        for lineno, line in enumerate(lines, 1):
            m = PKG_VERSION_RE.match(line)
            if m:
                versions.append((m.group(1), rel(pkg)))
            parts = line.split(None, 1)
            if len(parts) == 2 and parts[0] in {"f", "F", "g", "G"}:
                target = parts[1].strip()
                if parts[0] in {"f", "F"}:
                    listed.add(Path(target).name.lower())
                if not (pkg.parent / target).is_file():
                    add("ERROR", pkg, f"lists {target}, which does not exist", lineno)

    for readme in sorted(root.glob("README*.md")):
        m = README_VERSION_RE.search(readme.read_text(encoding="utf-8", errors="replace"))
        if m:
            versions.append((m.group(1), rel(readme)))

    distinct: dict[str, list[str]] = {}
    for v, where in versions:
        distinct.setdefault(v, []).append(where)
    if len(distinct) > 1:
        parts = "; ".join(f"{v} ({', '.join(sorted(set(w)))})" for v, w in distinct.items())
        add("WARN", None, f"package version numbers disagree: {parts}")

    if pkgs:
        for path in ados + list(helps.values()):
            stem = path.stem.lower()
            if stem.startswith("_") and path.suffix.lower() != ".ado":
                continue
            if path.name.lower() not in listed:
                add("WARN", path, "not listed in any .pkg file, so net install will not copy it")

    toc = root / "stata.toc"
    if toc.is_file():
        for lineno, line in enumerate(toc.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "p":
                if not (root / f"{parts[1]}.pkg").is_file():
                    add("ERROR", toc, f"names package {parts[1]}, but {parts[1]}.pkg does not exist", lineno)

    if not ados:
        add("WARN", None, "no .ado files found (is this a do-file project rather than a command package?)")
    return issues


def main(argv: list[str]) -> int:
    as_json = "--json" in argv
    args = [a for a in argv if a != "--json"]
    if any(a.startswith("-") for a in args) or len(args) > 1:
        print(__doc__.strip().split("\n\n")[1], file=sys.stderr)
        return 2
    root = Path(args[0] if args else ".").resolve()
    if not root.is_dir():
        print(f"stata_pkg_check: not a directory: {root}", file=sys.stderr)
        return 2
    issues = check(root)
    errors = sum(i["level"] == "ERROR" for i in issues)
    if as_json:
        print(json.dumps({"root": str(root), "errors": errors, "issues": issues}, ensure_ascii=False, indent=2))
    else:
        for i in issues:
            where = i["file"] or "."
            if i["line"]:
                where += f":{i['line']}"
            print(f"{i['level']:5}  {where}  {i['message']}")
        warns = len(issues) - errors
        print(f"stata_pkg_check: {errors} error(s), {warns} warning(s) in {root}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
