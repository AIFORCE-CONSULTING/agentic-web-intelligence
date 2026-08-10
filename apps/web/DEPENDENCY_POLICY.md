# Frontend Dependency Policy

## Approved baseline

The initial frontend dependency set is intentionally minimal and uses exact versions:

- `react` and `react-dom` 19.2.6
- `vite` 7.3.6
- `@vitejs/plugin-react` 5.0.4
- `typescript` 5.8.3
- matching React type definitions

`package-lock.json` is committed as the authoritative resolved dependency inventory. Do not use version ranges for direct dependencies without an approved dependency review.

## Install-script policy

`.npmrc` disables dependency lifecycle scripts by default.

The only approved exception is `esbuild@0.28.2`'s `postinstall` script. Vite requires this script to activate the version-locked platform binary used for compilation. It is run narrowly with:

```text
npm rebuild esbuild --ignore-scripts=false
```

`fsevents` remains blocked; it is an optional macOS-only dependency and is not required for Windows or Linux builds.

## Required review for changes

Before adding or changing a dependency:

1. Pin the direct version exactly.
2. Regenerate and review `package-lock.json` with scripts disabled.
3. Run `npm audit --package-lock-only --ignore-scripts`.
4. Install with `npm ci --ignore-scripts`.
5. Run `npm audit signatures` and record any required script exception.
