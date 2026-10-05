# Data Model: Database Bootstrap Before Runtime

## Database Bootstrap Readiness

Represents whether the platform database has been prepared for the application
version before API routes or durable worker activities accept runtime work.

| Field | Meaning |
| --- | --- |
| `bootstrap_name` | Stable name for the bootstrap group, such as platform application schema |
| `schema_version` | Version or marker for the schema set the app expects |
| `status` | `not_run`, `initializing`, `ready`, `failed`, or `incompatible` |
| `started_at` | When the latest bootstrap attempt began |
| `completed_at` | When the latest bootstrap attempt reached a terminal result |
| `failure_reason` | Safe explanation when status is `failed` or `incompatible` |

### State Transitions

```text
not_run -> initializing
initializing -> ready
initializing -> failed
ready -> initializing       # when a newer compatible bootstrap is applied
ready -> incompatible       # when app expects a schema that has not been applied
failed -> initializing
incompatible -> initializing
```

Bootstrap readiness is operational state. It does not change research runs,
evidence, summaries, reports, trust decisions, or audit history.

## Runtime Readiness Gate

Represents the API or worker process decision that runtime work may proceed.
This is derived from the dedicated bootstrap status record and required
infrastructure checks.

| Field | Meaning |
| --- | --- |
| `process_kind` | `api` or `durable_worker` |
| `database_bootstrap_ready` | Whether bootstrap readiness allows work |
| `dependency_ready` | Whether other required dependencies for that process are usable |
| `status` | `ready`, `not_ready`, or `unavailable` |
| `detail` | Safe operator-facing explanation |

### State Transitions

```text
not_ready -> ready
not_ready -> unavailable
ready -> unavailable        # on startup/restart check failure
unavailable -> ready        # after dependency/bootstrap readiness is restored
```

This can be represented in process memory and health responses. It is not a
business record.

## UI Platform Readiness Indicator

Represents the operator-facing display that the local platform is ready for
research.

| Field | Meaning |
| --- | --- |
| `status` | `loading`, `ready`, or `not_ready` |
| `database_bootstrap_status` | Safe summary of database bootstrap readiness |
| `dependency_statuses` | Safe summaries of required runtime dependencies |
| `detail` | Operator-facing explanation |

The UI indicator is derived from API health/readiness responses. It does not
infer readiness from research-run status.

## Store Schema Fragment

Represents existing schema definitions currently colocated with each store.
The first implementation may continue reusing these fragments as bootstrap
inputs. The Docker-started bootstrap command is the only runtime path allowed
to execute them.

| Field | Meaning |
| --- | --- |
| `store_name` | Owning store, such as `ResearchStore` or `EvidenceSummaryStore` |
| `schema_fragment` | The existing table/index/constraint setup statements |
| `business_owner` | The store that owns resulting business records |

The fragment is not an authority boundary by itself. Only the bootstrap
boundary may execute schema setup.

## Business Records

Existing records remain unchanged:

- `research_runs` and transition/audit records
- runtime assignments and authorization decisions
- web trust evaluations and human review decisions
- evidence summary executions, attempts, artifacts, keywords
- agentic topics, relevance decisions, coverage, reports, report attempts
- identity and security audit records
- local model provider configuration

Business records are not deleted, rewritten, or reclassified by database
bootstrap readiness.
