#!/usr/bin/env python3
"""MaRCo@BIS 工作区管理：初始化、查看状态、升级、环境检查。

插件安装目录会在升级时被整体替换，不能存放用户的数据和分析结果。所以第一次使用时，
把插件自带的框架（``framework/``：skills、scripts/lib、复现脚本、数据注册表、测试）
复制到一个独立的工作区目录，之后所有研究都在工作区里进行。

用法::

    python3 marco_workspace.py init    [--workspace 路径]   # 新建工作区
    python3 marco_workspace.py status  [--workspace 路径]   # 工作区位置、版本、数据面板状态
    python3 marco_workspace.py upgrade [--workspace 路径]   # 用插件的新版本更新框架文件
    python3 marco_workspace.py doctor  [--workspace 路径]   # 检查 Python 版本和依赖

工作区位置的确定顺序：``--workspace`` 参数 → 环境变量 ``MARCO_WORKSPACE`` →
默认 ``~/marco-workspace``。

升级规则：工作区里每个框架文件在安装时都记录了哈希值（``.marco-workspace.json``）。
升级时只覆盖"用户没改过"的文件；用户改过的文件保留原样，新版本写成 ``<文件>.new``
并在结果里列出，由用户决定是否合并。用户自己的东西（``data/<id>/dataset.csv``、
``scripts/applications/``、各处 ``outputs/``、知识库 ``context/``、
``data/registry.local.yaml``）从不触碰。

所有命令都向标准输出打印一个 JSON 对象，便于 agent 解析。只用标准库。
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

MANIFEST = ".marco-workspace.json"
DEFAULT_WORKSPACE = Path.home() / "marco-workspace"

#: 不复制、也不在升级时触碰的路径（相对工作区）。
SKIP_PARTS = {"__pycache__", ".pytest_cache", "outputs", ".DS_Store"}
USER_OWNED_PREFIXES = (
    "scripts/applications/",
    "skills/knowledge-base/context/",
    "data/staging/",
    "data/nbs_catalog/",
    "data/gmd/cache/",
)
USER_OWNED_FILES = {"data/registry.local.yaml", "skills/research-log/tools_to_promote.yaml"}

REQUIRED_PY = (3, 10)
PY_DEPS = ("numpy", "pandas", "scipy", "statsmodels", "plotly", "yaml")


def plugin_root() -> Path:
    """插件根目录：本脚本位于 <插件>/skills/marco-bis/scripts/。"""
    return Path(__file__).resolve().parents[3]


def framework_dir() -> Path:
    d = plugin_root() / "framework"
    if not (d / "CLAUDE.md").is_file():
        raise SystemExit(json.dumps({
            "ok": False,
            "error": f"插件缺少 framework/ 目录（应在 {d}）；请重新安装插件。",
        }, ensure_ascii=False))
    return d


def plugin_version() -> str:
    try:
        pkg = json.loads((plugin_root() / "package.json").read_text(encoding="utf-8"))
        return str(pkg.get("version", "unknown"))
    except (OSError, json.JSONDecodeError):
        return "unknown"


def resolve_workspace(arg: str | None) -> Path:
    raw = arg or os.environ.get("MARCO_WORKSPACE") or str(DEFAULT_WORKSPACE)
    return Path(raw).expanduser().resolve()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def is_user_owned(rel: str) -> bool:
    return rel in USER_OWNED_FILES or any(rel.startswith(p) for p in USER_OWNED_PREFIXES)


def framework_files() -> dict[str, Path]:
    """框架中应当复制到工作区的文件：相对路径 → 源文件。"""
    root = framework_dir()
    out: dict[str, Path] = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        rel_parts = p.relative_to(root).parts
        if any(part in SKIP_PARTS for part in rel_parts) or p.suffix == ".pyc":
            continue
        rel = "/".join(rel_parts)
        if rel.endswith("/dataset.csv"):
            continue
        if rel.startswith("data/gmd/") and rel != "data/gmd/UPDATE.md":
            continue  # gmd_tool.py update 生成的文件（学术许可，不分发）
        out[rel] = p
    return out


def read_manifest(ws: Path) -> dict | None:
    m = ws / MANIFEST
    if not m.is_file():
        return None
    try:
        return json.loads(m.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def write_manifest(ws: Path, files: dict[str, str], created: str | None = None) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (ws / MANIFEST).write_text(json.dumps({
        "kind": "marco-bis-workspace",
        "plugin_version": plugin_version(),
        "framework_source": str(framework_dir()),
        "created": created or now,
        "updated": now,
        "files": files,
    }, ensure_ascii=False, indent=1), encoding="utf-8")


def panel_status(ws: Path) -> list[dict]:
    out = []
    for pid in ("nbs_m", "nbs_q", "nbs_a", "fred_md", "fred_qd"):
        d = ws / "data" / pid
        csv = d / "dataset.csv"
        info = {"id": pid, "downloaded": csv.is_file()}
        if csv.is_file():
            info["size_kb"] = round(csv.stat().st_size / 1024, 1)
            info["modified"] = datetime.fromtimestamp(csv.stat().st_mtime).isoformat(timespec="seconds")
        out.append(info)
    cached = sorted((ws / "data" / "gmd" / "cache").glob("GMD_*.csv"))
    info = {"id": "gmd", "downloaded": bool(cached)}
    if cached:
        info["versions"] = [p.stem[len("GMD_"):] for p in reversed(cached)]
        info["size_kb"] = round(cached[-1].stat().st_size / 1024, 1)
        info["modified"] = datetime.fromtimestamp(cached[-1].stat().st_mtime).isoformat(timespec="seconds")
    out.append(info)
    return out


def cmd_init(args) -> dict:
    ws = resolve_workspace(args.workspace)
    manifest = read_manifest(ws)
    if manifest:
        return {"ok": True, "action": "exists", "workspace": str(ws),
                "plugin_version": plugin_version(),
                "workspace_version": manifest.get("plugin_version"),
                "message": "工作区已存在，未做改动。需要更新框架文件时运行 upgrade。"}
    if ws.exists() and any(ws.iterdir()):
        return {"ok": False, "workspace": str(ws),
                "error": "目标目录已存在且不是空目录，也不是 MaRCo 工作区。"
                         "请换一个路径（--workspace），或先清空该目录。"}
    ws.mkdir(parents=True, exist_ok=True)
    hashes: dict[str, str] = {}
    for rel, src in framework_files().items():
        dst = ws / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        hashes[rel] = sha256(dst)
    for d in ("scripts/applications", "data/staging", "skills/knowledge-base/context", "papers", "outputs"):
        (ws / d).mkdir(parents=True, exist_ok=True)
    write_manifest(ws, hashes)
    return {"ok": True, "action": "created", "workspace": str(ws),
            "files": len(hashes), "plugin_version": plugin_version(),
            "next_steps": [
                f"cd {ws}",
                "python3 -m pip install -r requirements.txt",
                "python3 scripts/tools/nbs_update.py --panel all   # 下载国家统计局月度/季度/年度面板",
            ]}


def cmd_status(args) -> dict:
    ws = resolve_workspace(args.workspace)
    manifest = read_manifest(ws)
    if not manifest:
        return {"ok": True, "initialized": False, "workspace": str(ws),
                "plugin_version": plugin_version(),
                "message": "工作区尚未初始化：运行 init。"}
    return {"ok": True, "initialized": True, "workspace": str(ws),
            "plugin_version": plugin_version(),
            "workspace_version": manifest.get("plugin_version"),
            "upgrade_available": manifest.get("plugin_version") != plugin_version(),
            "created": manifest.get("created"), "updated": manifest.get("updated"),
            "panels": panel_status(ws)}


def cmd_upgrade(args) -> dict:
    ws = resolve_workspace(args.workspace)
    manifest = read_manifest(ws)
    if not manifest:
        return {"ok": False, "workspace": str(ws), "error": "工作区尚未初始化：先运行 init。"}
    old_hashes: dict[str, str] = manifest.get("files", {})
    new_hashes: dict[str, str] = {}
    added, updated, unchanged, conflicts, kept_user = [], [], [], [], []
    for rel, src in framework_files().items():
        dst = ws / rel
        src_hash = sha256(src)
        if is_user_owned(rel):
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                added.append(rel)
            new_hashes[rel] = sha256(dst)
            continue
        if not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            added.append(rel)
            new_hashes[rel] = src_hash
            continue
        cur = sha256(dst)
        if cur == src_hash:
            unchanged.append(rel)
            new_hashes[rel] = cur
        elif rel in old_hashes and cur == old_hashes[rel]:
            shutil.copy2(src, dst)  # 用户没改过：直接更新
            updated.append(rel)
            new_hashes[rel] = src_hash
        else:
            if args.dry_run:
                conflicts.append(rel)
            else:
                shutil.copy2(src, dst.with_name(dst.name + ".new"))
                conflicts.append(rel)
            new_hashes[rel] = old_hashes.get(rel, cur)
            kept_user.append(rel)
    if not args.dry_run:
        write_manifest(ws, new_hashes, created=manifest.get("created"))
    return {"ok": True, "workspace": str(ws), "dry_run": bool(args.dry_run),
            "from_version": manifest.get("plugin_version"), "to_version": plugin_version(),
            "added": added, "updated": updated, "unchanged": len(unchanged),
            "conflicts": conflicts,
            "message": ("有 %d 个文件你改过，已保留原样，新版本另存为 <文件>.new，请逐个合并。" % len(conflicts))
            if conflicts else "升级完成，没有冲突。"}


def cmd_doctor(args) -> dict:
    ws = resolve_workspace(args.workspace)
    py_ok = sys.version_info >= REQUIRED_PY
    deps = {}
    for mod in PY_DEPS:
        spec = importlib.util.find_spec(mod)
        if spec is None:
            deps[mod] = None
            continue
        try:
            m = __import__(mod)
            deps[mod] = getattr(m, "__version__", "installed")
        except Exception as exc:  # noqa: BLE001
            deps[mod] = f"import error: {exc}"
    missing = [k for k, v in deps.items() if v is None or str(v).startswith("import error")]
    np_major = None
    if deps.get("numpy") and not str(deps["numpy"]).startswith("import error"):
        try:
            np_major = int(str(deps["numpy"]).split(".")[0])
        except ValueError:
            np_major = None
    warnings = []
    if np_major is not None and np_major >= 2:
        warnings.append("numpy 2.x 未经上游测试（requirements.txt 要求 numpy<2）；结果可能有差异。")
    return {"ok": py_ok and not missing, "python": sys.version.split()[0],
            "python_executable": sys.executable,
            "python_ok": py_ok, "dependencies": deps, "missing": missing,
            "warnings": warnings, "workspace": str(ws),
            "fix": (f"{sys.executable} -m pip install -r {ws / 'requirements.txt'}" if missing else None)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="MaRCo@BIS 工作区管理")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("init", "status", "upgrade", "doctor"):
        p = sub.add_parser(name)
        p.add_argument("--workspace", help="工作区路径（默认 $MARCO_WORKSPACE 或 ~/marco-workspace）")
        if name == "upgrade":
            p.add_argument("--dry-run", action="store_true", help="只列出将要发生的变化")
    args = ap.parse_args(argv)
    result = {"init": cmd_init, "status": cmd_status,
              "upgrade": cmd_upgrade, "doctor": cmd_doctor}[args.cmd](args)
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
