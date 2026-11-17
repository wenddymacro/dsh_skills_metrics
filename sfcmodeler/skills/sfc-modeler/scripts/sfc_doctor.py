#!/usr/bin/env python3
"""检查运行 SFCmodeler 所需的 Python 环境，缺什么就打印安装命令（不会自动安装）。

退出码：0 = 一切就绪；1 = 缺依赖；2 = Python 版本过低。
"""

import importlib
import sys
from pathlib import Path

VENDOR = Path(__file__).resolve().parent.parent / "vendor"
# 导入名 -> pip 包名
REQUIRED = {
    "numpy": "numpy",
    "pandas": "pandas",
    "sympy": "sympy",
    "scipy": "scipy",
    "matplotlib": "matplotlib",
    "tqdm": "tqdm",
    "tabulate": "tabulate",
}


def main() -> int:
    print(f"Python：{sys.executable}（{sys.version.split()[0]}）")
    if sys.version_info < (3, 10):
        print("需要 Python 3.10 及以上（上游 SFCmodeler 用了 `X | Y` 类型写法）。")
        return 2

    missing = []
    for mod, pkg in REQUIRED.items():
        try:
            m = importlib.import_module(mod)
            print(f"  ✓ {mod} {getattr(m, '__version__', '')}")
        except ImportError:
            print(f"  ✗ {mod}")
            missing.append(pkg)

    if missing:
        print("\n缺少依赖。征得用户同意后运行：\n")
        print(f"  {sys.executable} -m pip install {' '.join(missing)}\n")
        print("如果 pip 提示 externally-managed-environment，改用虚拟环境：\n")
        print(f"  {sys.executable} -m venv ~/.sfc-venv && ~/.sfc-venv/bin/pip install {' '.join(REQUIRED.values())}")
        print("  之后用 ~/.sfc-venv/bin/python 运行本 skill 的脚本。")
        return 1

    sys.path.insert(0, str(VENDOR))
    import SFCmodeler  # noqa: E402

    print(f"  ✓ SFCmodeler {SFCmodeler.__version__}（随插件附带：{VENDOR / 'SFCmodeler'}）")
    print("\n环境就绪。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
