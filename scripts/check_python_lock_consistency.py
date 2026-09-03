"""Verify that direct Python dependency declarations match committed lockfiles."""

from __future__ import annotations

import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PIN_PATTERN = re.compile(r"^\s*([A-Za-z0-9_.-]+)(?:\[[^]]+\])?\s*==\s*([^\s;]+)")
LOCK_PATTERN = re.compile(r"^([A-Za-z0-9_.-]+)(?:\[[^]]+\])?==([^\s\\]+)")


@dataclass(frozen=True)
class LockCheck:
    source: Path
    lock: Path
    dependencies: tuple[str, ...]


def canonicalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_pinned_dependencies(lines: list[str], source: Path) -> dict[str, str]:
    dependencies: dict[str, str] = {}
    for dependency in lines:
        match = PIN_PATTERN.match(dependency)
        if not match:
            raise ValueError(
                f"{source}: direct dependencies must use exact == pins; found {dependency!r}."
            )
        dependencies[canonicalize(match.group(1))] = match.group(2)
    return dependencies


def parse_lock(path: Path) -> dict[str, str]:
    packages: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = LOCK_PATTERN.match(line)
        if match:
            packages[canonicalize(match.group(1))] = match.group(2)
    return packages


def api_dependencies() -> tuple[dict[str, str], dict[str, str]]:
    pyproject_path = ROOT / "apps" / "api" / "pyproject.toml"
    pyproject = tomllib.loads(pyproject_path.read_text(encoding="utf-8"))
    project = pyproject["project"]
    runtime = parse_pinned_dependencies(project["dependencies"], pyproject_path)
    development = parse_pinned_dependencies(
        project["optional-dependencies"]["dev"], pyproject_path
    )
    return runtime, development


def docs_dependencies() -> dict[str, str]:
    source_path = ROOT / "docs" / "requirements.in"
    lines = [
        line
        for line in source_path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return parse_pinned_dependencies(lines, source_path)


def validate(check: LockCheck, dependencies: dict[str, str]) -> list[str]:
    locked = parse_lock(check.lock)
    errors: list[str] = []
    for dependency in check.dependencies:
        name = canonicalize(dependency)
        declared_version = dependencies[name]
        locked_version = locked.get(name)
        if locked_version is None:
            errors.append(
                f"{check.lock}: missing direct dependency {dependency}=={declared_version} "
                f"declared in {check.source}."
            )
        elif locked_version != declared_version:
            errors.append(
                f"{check.lock}: has {dependency}=={locked_version}, but {check.source} "
                f"declares {dependency}=={declared_version}."
            )
    return errors


def main() -> int:
    api_runtime, api_development = api_dependencies()
    api_all = api_runtime | api_development
    docs = docs_dependencies()
    checks = (
        LockCheck(
            ROOT / "apps" / "api" / "pyproject.toml",
            ROOT / "apps" / "api" / "requirements.lock",
            tuple(api_runtime.keys()),
        ),
        LockCheck(
            ROOT / "apps" / "api" / "pyproject.toml",
            ROOT / "apps" / "api" / "requirements-dev.lock",
            tuple(api_all.keys()),
        ),
        LockCheck(
            ROOT / "docs" / "requirements.in",
            ROOT / "docs" / "requirements.lock",
            tuple(docs.keys()),
        ),
    )

    errors = [
        error
        for check in checks
        for error in validate(
            check, api_all if check.source.name == "pyproject.toml" else docs
        )
    ]
    if errors:
        print("Python lockfile consistency check failed:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        print(
            "\nRegenerate locks with: .\\scripts\\update-python-locks.ps1",
            file=sys.stderr,
        )
        return 1

    print("Python direct dependency pins match all committed lockfiles.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
