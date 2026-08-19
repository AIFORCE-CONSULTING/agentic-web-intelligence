# Dependency management

The project uses exact direct dependency pins and hash-locked transitive
dependency trees. Docker and CI install only from committed *.lock files.

## Python and documentation dependency updates

- apps/api/pyproject.toml is the API dependency source.
- docs/requirements.in is the documentation dependency source.
- apps/api/requirements.lock, apps/api/requirements-dev.lock, and
  docs/requirements.lock are generated review artifacts.

Do not edit a lockfile by hand.

## Regenerate locks

Docker Desktop must be running. From the repository root:

~~~powershell
.\scripts\update-python-locks.ps1
~~~

Use -Target api or -Target docs to regenerate only one area. The command runs
the pinned pip-tools compiler inside Python 3.12 so its output matches the
platform runtime instead of a contributor's local Python version.

After regeneration, review every changed package and hash, then run:

~~~powershell
python scripts/check_python_lock_consistency.py
~~~

CI runs the same consistency check as part of the required API quality check.

## Dependabot policy

Dependabot can propose changes to a Python/docs source manifest. A manifest-only
proposal is not mergeable: the corresponding lockfile changes must be generated,
reviewed, and included in the same pull request. Do not grant automation
permission to generate and push lockfile commits.
