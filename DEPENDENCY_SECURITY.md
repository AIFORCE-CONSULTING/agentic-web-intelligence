# Dependency security

Every dependency change is reviewed at repository scope, regardless of whether
it is Python, JavaScript, documentation tooling, or a GitHub Action.

Before changing a manifest or lockfile: review the package's provenance,
maintainer, license, release history, and known advisories. Then pin it exactly,
regenerate the lockfile, run the ecosystem audit, and include evidence in the
pull request. Never commit a dependency merely because installation succeeds.

CI enforces GitHub dependency review on pull requests, `pip-audit` for Python
lockfiles, and `npm audit --package-lock-only` for the web lockfile. Dependabot
opens update pull requests for all supported manifests and GitHub Actions.

Repository rules for `main` must require these checks, block direct pushes, and
require review; workflow files are themselves supply-chain-sensitive code.
