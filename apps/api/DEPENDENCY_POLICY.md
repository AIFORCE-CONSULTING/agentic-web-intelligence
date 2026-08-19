# API Dependency Policy

## Runtime baseline

The API targets Python 3.12 in local containers and production. Its initial runtime dependencies use exact, mature versions:

- `fastapi` 0.136.3
- `pydantic` 2.13.4
- `pydantic-settings` 2.14.2
- `uvicorn` 0.47.0

Test and lint tooling is pinned separately in the `dev` optional dependency group.

## Resolution and installation policy

The complete Python dependency tree is generated for Python 3.12 with hashes:

- `requirements.lock` contains the deployable runtime tree.
- `requirements-dev.lock` adds the pinned test and lint tooling.

Installation uses only the appropriate reviewed lockfile with `--require-hashes` and binary wheels where available.

Before a dependency change is accepted:

1. Pin the direct requirement exactly in `pyproject.toml`.
2. Run scripts/update-python-locks.ps1 -Target api to resolve new Python 3.12
   lockfiles.
3. Review all added packages, versions, hashes, and source indexes.
4. Run a vulnerability audit without applying automatic fixes.
5. Install only from the approved lockfile and run the API test suite.

The repository CI check verifies that every direct pin in pyproject.toml matches
the appropriate committed lockfile. See docs/dependency-management.md for the
full workflow.
