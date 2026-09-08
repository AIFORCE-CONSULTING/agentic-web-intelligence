# Phase 4 operations and security runbook

## Safe deployment configuration

The API refuses to start when a deployment specifies an unsupported environment,
a bootstrap secret shorter than 32 characters, a partial OIDC configuration, or
a non-HTTPS web origin in production. Development and test environments may use
localhost HTTP origins.

Keep real values in the deployment environment or an uncommitted .env file.
Do not place secrets in Compose files, source code, documentation, browser
configuration, prompts, or durable records.

## Administrator posture check

After signing in as an administrator, inspect GET
/v1/operations/security-status. It reports:

- identity and security-audit persistence readiness;
- configured, missing, or invalid names from the fixed secret registry;
- enterprise identity configuration status; and
- the complete safe tool-governance registry.

It returns no secret values and uses no-store browser caching.

## Local end-to-end validation

With Docker Desktop running, start the local stack using the web-research and
stateful-services profiles. Then validate this sequence:

1. Open the administrator console and bootstrap or sign in as an administrator.
2. Confirm the security status endpoint reports ready identity and audit persistence.
3. Create a least-privilege service identity, record its token outside the platform,
   and use it only for its permitted workspace operation.
4. Confirm the same token is denied from service-identity management and security audit.
5. Revoke the identity and confirm its token can no longer access the API.
6. Inspect the tool registry, invoke an approved web tool, and verify the MCP audit.

Run the locked API checks before merging:

~~~powershell
docker run --rm -v "$($PWD):/workspace" -w /workspace/apps/api python:3.12-slim sh -lc "pip install --require-hashes --only-binary=:all: -r requirements-dev.lock >/dev/null && ruff check . && PYTHONPATH=/workspace/apps/api pytest -q"
~~~

## Browser response protections

The API adds no-sniff, deny-frame, no-referrer, and restrictive
permissions-policy headers to every response. Authentication, secret,
service-identity, and operational-status responses also use no-store. In
production, the API adds strict transport security.
