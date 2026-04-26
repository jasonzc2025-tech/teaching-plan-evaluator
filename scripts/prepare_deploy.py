"""
部署前准备：清理 __pycache__ / .pyc，并重新生成软著交存文本。
在项目根目录执行: python scripts/prepare_deploy.py
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIR_NAMES = {".venv", ".git", "instance", "artifacts"}


def remove_caches() -> tuple[int, int]:
    removed_dirs = 0
    removed_files = 0
    for path in ROOT.rglob("*"):
        try:
            rel = path.relative_to(ROOT)
        except ValueError:
            continue
        if any(p in SKIP_DIR_NAMES for p in rel.parts):
            continue
        if path.is_dir() and path.name == "__pycache__":
            shutil.rmtree(path, ignore_errors=True)
            removed_dirs += 1
        elif path.is_file() and path.suffix == ".pyc":
            path.unlink(missing_ok=True)
            removed_files += 1
    return removed_dirs, removed_files


def main() -> int:
    d, f = remove_caches()
    print(f"已删除 __pycache__ 目录: {d}，.pyc 文件: {f}")
    script = ROOT / "scripts" / "build_source_submission.py"
    r = subprocess.run([sys.executable, str(script)], cwd=str(ROOT))
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
