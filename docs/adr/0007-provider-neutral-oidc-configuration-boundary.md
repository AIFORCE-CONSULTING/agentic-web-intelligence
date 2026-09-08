# ADR 0007: Establish a provider-neutral OIDC configuration boundary

- Status: Accepted
- Date: 2026-09-03

## Context

The platform must be simple and secure to run locally while allowing an
organization to connect its existing identity provider later. A provider
integration should not be implied by a UI switch, partial environment values,
or a browser-supplied issuer URL.

## Decision

The API owns a server-only OpenID Connect configuration boundary. It accepts
configuration exclusively through deployment environment variables and requires
the issuer URL, client ID, client secret, and redirect URI as one complete set.
Issuer and redirect URLs must be HTTPS except for explicit localhost development.

The current boundary reports a credential-free status endpoint only. It does
not redirect users, perform discovery, exchange authorization codes, validate
tokens, provision users, map groups, or call an external provider. Local
authentication remains available when OIDC is absent or invalid.

A later confidential-client adapter must use this validated configuration and
must verify the discovery document and ID tokens server-side, including issuer,
audience, signature, nonce, expiry, and authorization-code flow state. It will
map an immutable issuer-and-subject pair to a platform identity and then create
the existing platform session. The platform remains the authority for workspace
membership and roles.

## Consequences

Deployments can prepare Entra, Okta, Auth0, Keycloak, or another compliant
provider without adding a vendor SDK or storing secrets in browser code. The
status endpoint gives operators a safe diagnostic surface without exposing
credentials or generating outbound traffic.

SSO is not available until the token-validating adapter is built and tested.
There is intentionally no fallback that treats an unverified claim, browser
request, or agent instruction as an authenticated identity.
