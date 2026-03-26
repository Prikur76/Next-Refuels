from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def load_dependencies(pyproject_path: Path) -> list[str]:
    try:
        import tomllib  # Python 3.11+
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError(
            "tomllib недоступен. Используйте Python 3.11+."
        ) from exc

    data = tomllib.loads(pyproject_path.read_bytes().decode("utf-8"))
    return list(data["project"]["dependencies"])


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Install Python dependencies from pyproject.toml"
    )
    parser.add_argument(
        "--upgrade-pip",
        action="store_true",
        help="Upgrade pip/setuptools/wheel before installing deps.",
    )
    parser.add_argument(
        "--no-cache-dir",
        action="store_true",
        help="Pass --no-cache-dir to pip.",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    pyproject_path = repo_root / "pyproject.toml"
    if not pyproject_path.exists():
        raise FileNotFoundError(
            f"pyproject.toml not found: {pyproject_path}"
        )

    deps = load_dependencies(pyproject_path)

    pip_base = [sys.executable, "-m", "pip"]
    if args.upgrade_pip:
        subprocess.check_call(pip_base + ["install", "--upgrade", "pip"])
        subprocess.check_call(
            pip_base + ["install", "--upgrade", "setuptools", "wheel"]
        )

    pip_cmd = pip_base + ["install"]
    if args.no_cache_dir:
        pip_cmd.append("--no-cache-dir")
    pip_cmd.extend(deps)

    subprocess.check_call(pip_cmd)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

