"""Parse GitHub workflow and issue-template YAML files without executing them."""

from pathlib import Path

import yaml


def main() -> None:
    files = sorted(Path(".github").rglob("*.y*ml"))
    if not files:
        raise SystemExit("No GitHub YAML files found.")

    for path in files:
        yaml.safe_load(path.read_text(encoding="utf-8"))

    print(f"Parsed {len(files)} GitHub YAML files successfully.")


if __name__ == "__main__":
    main()
