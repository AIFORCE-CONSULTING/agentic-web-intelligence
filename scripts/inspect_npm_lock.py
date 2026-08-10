"""Report review-relevant facts from an npm package lockfile."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    lockfile = Path("apps/web/package-lock.json")
    lock = json.loads(lockfile.read_text(encoding="utf-8"))
    entries = [(name, value) for name, value in lock.get("packages", {}).items() if name]
    scripted = [name for name, value in entries if value.get("hasInstallScript")]
    missing_integrity = [
        name for name, value in entries if value.get("resolved") and not value.get("integrity")
    ]
    registries = sorted(
        {
            value["resolved"].split("/")[2]
            for _, value in entries
            if value.get("resolved", "").startswith("https://")
        }
    )
    root = lock["packages"][""]

    print(f"lockfileVersion={lock.get('lockfileVersion')}")
    print(f"packages={len(entries)}")
    print(f"install_scripts={','.join(scripted)}")
    print(f"missing_integrity={','.join(missing_integrity)}")
    print(f"registries={','.join(registries)}")
    print(f"direct_dependencies={','.join(sorted(root.get('dependencies', {})))}")
    print(f"direct_dev_dependencies={','.join(sorted(root.get('devDependencies', {})))}")


if __name__ == "__main__":
    main()
