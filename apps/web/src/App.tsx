import { FormEvent, useEffect, useState } from "react";

type Health = { status: string; service: string; environment: string };
type DependencyHealth = {
  name: string; status: "ready" | "unavailable" | "unconfigured"; detail: string;
};
type ServiceHealth = Health & { services: DependencyHealth[] };
type Source = { rank: number; title: string; url: string; snippet: string; engine?: string | null };
type Evidence = {
  url: string; retrieved_at: string; content_type: string; text: string; content_hash: string;
  extraction_method: string;
};
type AuditEvent = { event_type: string; occurred_at: string; details: Record<string, unknown> };
type ResearchRun = {
  id: string; question: string; status: string; sources: Source[]; evidence: Evidence[];
  audit_events: AuditEvent[];
};
type ResearchRunSummary = {
  id: string; question: string; status: string; created_at: string; updated_at: string;
  source_count: number; evidence_count: number;
};
type ResearchRunList = { runs: ResearchRunSummary[] };
type ExtractionAttempt = { url: string; outcome: "failed" | "succeeded"; detail?: string };
type BatchExtractionOutcome = {
  url: string; status: "succeeded" | "failed" | "denied"; reason?: string | null;
};
type BatchExtractResponse = { run_id: string; outcomes: BatchExtractionOutcome[] };
type AuthenticatedUser = {
  id: string; email: string; workspace_id: string; workspace_name: string;
  role: "administrator" | "operator" | "viewer"; authenticated_at: string;
};
type SecurityAuditEvent = {
  id: string; actor_user_id?: string | null; workspace_id?: string | null;
  event_type: string; outcome: "succeeded" | "denied"; occurred_at: string;
  details: Record<string, unknown>;
};
type SecurityAuditEventList = { events: SecurityAuditEvent[] };
type SecretStatus = {
  name: string; configured: boolean; valid: boolean; purpose: string; detail: string;
};
type ToolRegistryEntry = {
  name: string; owner: string; purpose: string; required_permission: string;
  secret_dependencies: string[]; enabled_by_default: boolean; audit_required: boolean;
  output_contract: string;
};
type OperationalSecurityStatus = {
  environment: string;
  identity_persistence: DependencyHealth;
  security_audit_persistence: DependencyHealth;
  secrets: { secrets: SecretStatus[] };
  enterprise_identity: { mode: "disabled" | "invalid" | "ready"; provider_name?: string | null; detail: string };
  tool_registry: { tools: ToolRegistryEntry[] };
};

const apiBaseUrl = import.meta.env.VITE_PLATFORM_API_URL ?? "http://localhost:8000";
const isDeveloperRoute = window.location.pathname === "/developer";
const isAdminRoute = window.location.pathname === "/admin";

async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, { credentials: "include", ...options });
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? "The platform request could not be completed.");
  }
  return (await response.json()) as T;
}

function latestExtractionAttemptFor(run: ResearchRun): ExtractionAttempt | null {
  const event = [...run.audit_events].reverse().find((candidate) => (
    candidate.event_type === "research.extract.failed" ||
    candidate.event_type === "research.evidence.extracted"
  ));
  if (!event) return null;
  const url = event.details.requested_url ?? event.details.url;
  if (typeof url !== "string") return null;
  if (event.event_type === "research.extract.failed") {
    return {
      url,
      outcome: "failed",
      detail: typeof event.details.reason === "string" ? event.details.reason : "Source retrieval failed.",
    };
  }
  return { url, outcome: "succeeded" };
}

function PrimaryNavigation() {
  return (
    <nav className="primary-nav" aria-label="Primary navigation">
      <a className={!isDeveloperRoute && !isAdminRoute ? "active" : ""} href="/">Research workspace</a>
      <a className={isDeveloperRoute ? "active" : ""} href="/developer">Developer hub</a>
      <a className={isAdminRoute ? "active" : ""} href="/admin">Admin</a>
    </nav>
  );
}

function DeveloperHub({
  health,
  serviceHealth,
  onRefresh,
}: {
  health: Health | null;
  serviceHealth: ServiceHealth | null;
  onRefresh: () => void;
}) {
  return (
    <>
      <header>
        <p className="eyebrow">Platform access</p>
        <PrimaryNavigation />
        <h1>Developer hub</h1>
        <p className="lead">One local starting point for the platform console, API contract, documentation, and service health.</p>
      </header>
      <section aria-labelledby="developer-services-heading">
        <div className="section-heading"><div><p className="eyebrow">Local services</p><h2 id="developer-services-heading">Platform health</h2></div><button type="button" className="secondary" onClick={onRefresh}>Refresh status</button></div>
        <p className={`connection ${health && serviceHealth?.status === "ready" ? "online" : "offline"}`}>{health ? `API ${serviceHealth?.status ?? health.status}` : "API unavailable"}</p>
        <div className="health-grid">
          <article className={`service-card ${health ? "ready" : "unavailable"}`}><div><strong>Platform API</strong><span>{health ? "ready" : "unavailable"}</span></div><p>{health ? `Serving ${health.environment} requests.` : "The API readiness probe did not respond."}</p></article>
          {serviceHealth?.services.map((service) => <article className={`service-card ${service.status}`} key={service.name}><div><strong>{service.name}</strong><span>{service.status}</span></div><p>{service.detail}</p></article>)}
        </div>
      </section>
      <section aria-labelledby="developer-access-heading">
        <div className="section-heading"><div><p className="eyebrow">Interfaces</p><h2 id="developer-access-heading">Platform entry points</h2></div><span className="badge">governed access</span></div>
        <div className="developer-grid">
          <a className="developer-card" href="/"><strong>Research workspace</strong><span>Create, reopen, and inspect governed research runs.</span><small>localhost:3000</small></a>
          <a className="developer-card" href={`${apiBaseUrl}/docs`} target="_blank" rel="noreferrer"><strong>API reference</strong><span>Explore and execute the FastAPI OpenAPI contract.</span><small>{apiBaseUrl}/docs</small></a>
          <a className="developer-card" href={`${apiBaseUrl}/openapi.json`} target="_blank" rel="noreferrer"><strong>OpenAPI schema</strong><span>Use the machine-readable API contract for integrations.</span><small>{apiBaseUrl}/openapi.json</small></a>
          <a className="developer-card" href={`${apiBaseUrl}/v1/mcp/tools`} target="_blank" rel="noreferrer"><strong>MCP tool catalog</strong><span>Inspect the only agent-visible, read-only web tools.</span><small>{apiBaseUrl}/v1/mcp/tools</small></a>
          <a className="developer-card" href={`${apiBaseUrl}/v1/mcp/audit`} target="_blank" rel="noreferrer"><strong>MCP execution audit</strong><span>Review bounded, durable outcomes from direct MCP calls.</span><small>{apiBaseUrl}/v1/mcp/audit</small></a>
          <a className="developer-card" href={`${apiBaseUrl}/v1/runtime/runs`} target="_blank" rel="noreferrer"><strong>Agent runtime runs</strong><span>Inspect server-owned roles, capabilities, handoffs, and lifecycle events.</span><small>{apiBaseUrl}/v1/runtime/runs</small></a>
          <a className="developer-card" href="/admin"><strong>Platform administration</strong><span>Sign in locally and inspect your workspace identity and security audit trail.</span><small>localhost:3000/admin</small></a>
          <a className="developer-card" href="http://localhost:8001" target="_blank" rel="noreferrer"><strong>Platform documentation</strong><span>Read architecture, web-research, and prompt-template guides.</span><small>localhost:8001 · included with the web-research stack</small></a>
        </div>
      </section>
      <section aria-labelledby="developer-guidance-heading">
        <h2 id="developer-guidance-heading">Local guidance</h2>
        <p>The documentation site starts with the <code>web-research</code> profile. SearXNG remains internal-only; all web research goes through the governed API.</p>
      </section>
    </>
  );
}

function AdminConsole() {
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [events, setEvents] = useState<SecurityAuditEvent[]>([]);
  const [posture, setPosture] = useState<OperationalSecurityStatus | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [bootstrapSecret, setBootstrapSecret] = useState("");
  const [showBootstrap, setShowBootstrap] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadAdminData() {
    const currentUser = await apiRequest<AuthenticatedUser>("/v1/auth/me");
    setUser(currentUser);
    if (currentUser.role !== "administrator") {
      setEvents([]);
      setPosture(null);
      return;
    }
    const [audit, securityPosture] = await Promise.all([
      apiRequest<SecurityAuditEventList>("/v1/audit/security"),
      apiRequest<OperationalSecurityStatus>("/v1/operations/security-status"),
    ]);
    setEvents(audit.events);
    setPosture(securityPosture);
  }

  useEffect(() => {
    void loadAdminData().catch((reason) => {
      setUser(null);
      setEvents([]);
      setPosture(null);
      if (reason instanceof Error && reason.message !== "Authentication is required.") {
        setError(reason.message);
      }
    });
  }, []);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiRequest<AuthenticatedUser>("/v1/auth/sign-in", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      setPassword("");
      await loadAdminData();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to sign in.");
    } finally {
      setBusy(false);
    }
  }

  async function bootstrap(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiRequest<AuthenticatedUser>("/v1/auth/bootstrap", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bootstrap_secret: bootstrapSecret, email, password }),
      });
      setBootstrapSecret("");
      setPassword("");
      setShowBootstrap(false);
      await loadAdminData();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to initialize the administrator.");
    } finally {
      setBusy(false);
    }
  }

  async function signOut() {
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`${apiBaseUrl}/v1/auth/sign-out`, {
        method: "POST",
        credentials: "include",
      });
      if (!response.ok) throw new Error("Unable to sign out.");
      setUser(null);
      setEvents([]);
      setPosture(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to sign out.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <header>
        <p className="eyebrow">Platform control plane</p>
        <PrimaryNavigation />
        <h1>Administration</h1>
        <p className="lead">Inspect the identity and security decisions that the server enforces for this workspace.</p>
      </header>
      {error && <p className="error" role="alert">{error}</p>}
      {!user && <section aria-labelledby="admin-sign-in-heading">
        <h2 id="admin-sign-in-heading">Sign in</h2>
        <p className="hint">Use the local administrator account created during deployment bootstrap.</p>
        <form className="auth-form" onSubmit={signIn}>
          <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
          <label>Password<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
          <button type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
        </form>
        <button type="button" className="link-button" onClick={() => setShowBootstrap((visible) => !visible)}>
          {showBootstrap ? "Hide first-time setup" : "First-time setup"}
        </button>
        {showBootstrap && <form className="auth-form bootstrap-form" onSubmit={bootstrap}>
          <p className="hint">Use this once with the deployment-controlled bootstrap secret. It is unavailable after the first administrator is created.</p>
          <label>Bootstrap secret<input type="password" value={bootstrapSecret} onChange={(event) => setBootstrapSecret(event.target.value)} required /></label>
          <label>Email<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
          <label>Password<input type="password" minLength={14} value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
          <button type="submit" disabled={busy}>{busy ? "Initializing…" : "Create administrator"}</button>
        </form>}
      </section>}
      {user && <>
        <section aria-labelledby="identity-heading">
          <div className="section-heading"><div><p className="eyebrow">Authenticated session</p><h2 id="identity-heading">Current identity</h2></div><button type="button" className="secondary" onClick={() => void signOut()} disabled={busy}>Sign out</button></div>
          <dl className="identity-grid"><div><dt>Email</dt><dd>{user.email}</dd></div><div><dt>Role</dt><dd><span className={`role ${user.role}`}>{user.role}</span></dd></div><div><dt>Workspace</dt><dd>{user.workspace_name}</dd></div><div><dt>Session established</dt><dd>{new Date(user.authenticated_at).toLocaleString()}</dd></div></dl>
        </section>
        {user.role === "administrator" && posture && <section aria-labelledby="security-posture-heading">
          <div className="section-heading"><div><p className="eyebrow">Deployment controls</p><h2 id="security-posture-heading">Security posture</h2></div><button type="button" className="secondary" onClick={() => void loadAdminData()} disabled={busy}>Refresh</button></div>
          <p className="hint">Safe configuration and dependency status for this deployment. Secret values are never displayed.</p>
          <div className="posture-grid">
            {[posture.identity_persistence, posture.security_audit_persistence].map((item) => <article className={"service-card " + item.status} key={item.name}><div><strong>{item.name}</strong><span>{item.status}</span></div><p>{item.detail}</p></article>)}
            <article className={"service-card " + (posture.enterprise_identity.mode === "invalid" ? "unavailable" : posture.enterprise_identity.mode === "ready" ? "ready" : "unconfigured")}><div><strong>Enterprise identity</strong><span>{posture.enterprise_identity.mode}</span></div><p>{posture.enterprise_identity.detail}</p></article>
          </div>
          <div className="posture-details">
            <article><h3>Deployment secrets</h3><ul>{posture.secrets.secrets.map((secret) => <li key={secret.name}><strong>{secret.name}</strong><span className={secret.configured && secret.valid ? "ready-text" : "warning-text"}>{secret.detail}</span><small>{secret.purpose}</small></li>)}</ul></article>
            <article><h3>Governed tools</h3><ul>{posture.tool_registry.tools.map((tool) => <li key={tool.name}><strong>{tool.name}</strong><span>{tool.required_permission} · {tool.audit_required ? "audited" : "not audited"}</span><small>{tool.purpose}</small></li>)}</ul></article>
          </div>
        </section>}
        {user.role === "administrator" ? <section aria-labelledby="security-audit-heading">
          <div className="section-heading"><div><p className="eyebrow">Append-only record</p><h2 id="security-audit-heading">Security audit</h2></div><button type="button" className="secondary" onClick={() => void loadAdminData()} disabled={busy}>Refresh</button></div>
          <p className="hint">Authentication and authorization decisions only. Secrets and raw session tokens are never shown or stored.</p>
          {events.length ? <ol className="security-audit">{events.map((item) => <li key={item.id} className={item.outcome}><div><strong>{item.event_type}</strong><span>{item.outcome}</span></div><time>{new Date(item.occurred_at).toLocaleString()}</time>{Object.keys(item.details).length > 0 && <pre>{JSON.stringify(item.details, null, 2)}</pre>}</li>)}</ol> : <p>No workspace security events have been recorded yet.</p>}
        </section> : <section><h2>Administrator access required</h2><p>Your role can use its permitted workspace capabilities, but only an administrator may view the security audit trail.</p></section>}
      </>}
    </main>
  );
}

export function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [serviceHealth, setServiceHealth] = useState<ServiceHealth | null>(null);
  const [question, setQuestion] = useState("What is agentic web intelligence?");
  const [run, setRun] = useState<ResearchRun | null>(null);
  const [runLibrary, setRunLibrary] = useState<ResearchRunSummary[]>([]);
  const [selectedAuditIndex, setSelectedAuditIndex] = useState<number | null>(null);
  const [selectedSourceUrls, setSelectedSourceUrls] = useState<string[]>([]);
  const [batchOutcomes, setBatchOutcomes] = useState<BatchExtractionOutcome[]>([]);
  const [lastExtractionAttempt, setLastExtractionAttempt] = useState<ExtractionAttempt | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function refreshServiceHealth() {
    try {
      const response = await apiRequest<ServiceHealth>("/health/services");
      setHealth(response);
      setServiceHealth(response);
    } catch {
      setHealth(null);
      setServiceHealth(null);
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${apiBaseUrl}/health/ready`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("API unavailable");
        return (await response.json()) as Health;
      })
      .then(setHealth)
      .catch(() => setHealth(null));
    void refreshServiceHealth();
    return () => controller.abort();
  }, []);

  async function refreshRunLibrary() {
    try {
      const response = await apiRequest<ResearchRunList>("/v1/research/runs");
      setRunLibrary(response.runs);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to load saved research runs.");
    }
  }

  useEffect(() => {
    if (health && !isDeveloperRoute && !isAdminRoute) void refreshRunLibrary();
  }, [health]);

  async function reopenRun(runId: string) {
    setBusy(true);
    setError(null);
    try {
      const reopened = await apiRequest<ResearchRun>(`/v1/research/runs/${runId}`);
      setRun(reopened);
      setSelectedAuditIndex(null);
      setLastExtractionAttempt(latestExtractionAttemptFor(reopened));
      setQuestion(reopened.question);
      setSelectedSourceUrls(reopened.sources.map((source) => source.url));
      setBatchOutcomes([]);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to reopen the research run.");
    } finally {
      setBusy(false);
    }
  }

  async function createRun(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const created = await apiRequest<ResearchRun>("/v1/research/runs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, max_results: 5 }),
      });
      setRun(created);
      setSelectedAuditIndex(null);
      setLastExtractionAttempt(null);
      setSelectedSourceUrls(created.sources.map((source) => source.url));
      setBatchOutcomes([]);
      await refreshRunLibrary();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create a research run.");
    } finally {
      setBusy(false);
    }
  }

  function toggleSource(url: string) {
    setSelectedSourceUrls((selected) => (
      selected.includes(url) ? selected.filter((item) => item !== url) : [...selected, url]
    ));
  }

  async function extractSelectedSources(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!run || !selectedSourceUrls.length) return;
    setBusy(true);
    setError(null);
    setBatchOutcomes([]);
    try {
      const batch = await apiRequest<BatchExtractResponse>(`/v1/research/runs/${run.id}/extract-batch`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ urls: selectedSourceUrls }),
      });
      const refreshedRun = await apiRequest<ResearchRun>(`/v1/research/runs/${run.id}`);
      setRun(refreshedRun);
      setLastExtractionAttempt(latestExtractionAttemptFor(refreshedRun));
      setBatchOutcomes(batch.outcomes);
      await refreshRunLibrary();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to extract selected source data.");
      try {
        const refreshedRun = await apiRequest<ResearchRun>(`/v1/research/runs/${run.id}`);
        setRun(refreshedRun);
        setLastExtractionAttempt(latestExtractionAttemptFor(refreshedRun));
        await refreshRunLibrary();
      } catch {
        // The source failure remains visible even if the post-failure refresh is unavailable.
      }
    } finally {
      setBusy(false);
    }
  }

  if (isAdminRoute) return <AdminConsole />;

  if (isDeveloperRoute) {
    return <main><DeveloperHub health={health} serviceHealth={serviceHealth} onRefresh={() => void refreshServiceHealth()} /></main>;
  }

  return (
    <main>
      <header>
        <p className="eyebrow">Agentic Web Intelligence</p>
        <PrimaryNavigation />
        <h1>Research with a durable evidence trail.</h1>
        <p className="lead">Discover public sources, extract bounded source data, and keep an inspectable record of every platform decision.</p>
        <p className={`connection ${health ? "online" : "offline"}`}>{health ? `API ${health.status}` : "API unavailable"}</p>
      </header>

      <section aria-labelledby="run-heading">
        <h2 id="run-heading">1. Start a research run</h2>
        <form onSubmit={createRun} className="form-row">
          <label>Research question
            <input value={question} onChange={(event) => setQuestion(event.target.value)} required />
          </label>
          <button type="submit" disabled={busy || !health}>{busy ? "Working…" : "Discover sources"}</button>
        </form>
      </section>

      {error && <p className="error" role="alert">{error}</p>}

      <section aria-labelledby="library-heading">
        <div className="section-heading"><div><p className="eyebrow">Persistent resources</p><h2 id="library-heading">Research run library</h2></div><button type="button" className="secondary" onClick={() => void refreshRunLibrary()} disabled={busy || !health}>Refresh</button></div>
        {runLibrary.length ? <ol className="run-library">{runLibrary.map((item) => (
          <li key={item.id}><button type="button" className="run-card" onClick={() => void reopenRun(item.id)} disabled={busy}>
            <span><strong>{item.question}</strong><small>Run {item.id.slice(0, 8)} · {new Date(item.updated_at).toLocaleString()}</small></span>
            <span className="run-counts">{item.source_count} sources · {item.evidence_count} evidence</span>
          </button></li>
        ))}</ol> : <p>No saved research runs yet. Start one above to create a durable resource.</p>}
      </section>

      {run && <>
        <section aria-labelledby="sources-heading">
          <div className="section-heading"><div><p className="eyebrow">Run {run.id.slice(0, 8)}</p><h2 id="sources-heading">2. Select source candidates</h2></div><span className="badge">{selectedSourceUrls.length} selected</span></div>
          {run.sources.length ? <ol className="sources">{run.sources.map((source) => (
            <li key={`${source.rank}-${source.url}`}><label className="source">
              <input type="checkbox" checked={selectedSourceUrls.includes(source.url)} onChange={() => toggleSource(source.url)} disabled={busy} />
              <span className="rank">{source.rank}</span><span><strong>{source.title}</strong><small>{source.url}</small>{source.snippet && <span>{source.snippet}</span>}</span>
            </label></li>
          ))}</ol> : <p>No public source candidates were returned for this question.</p>}
        </section>

        <section aria-labelledby="extract-heading">
          <h2 id="extract-heading">3. Extract governed source data</h2>
          <form onSubmit={extractSelectedSources} className="form-row">
            <p className="selection-summary">{selectedSourceUrls.length} of {run.sources.length} candidates selected. Sources are extracted sequentially and each outcome is recorded.</p>
            <button type="submit" disabled={busy || !selectedSourceUrls.length}>{busy ? "Extracting selected sources…" : `Extract ${selectedSourceUrls.length} selected source${selectedSourceUrls.length === 1 ? "" : "s"}`}</button>
          </form>
          <p className="hint">Only public HTML or plain-text pages are allowed. Downloads, private URLs, and browser interaction remain blocked.</p>
          {batchOutcomes.length > 0 && <ol className="batch-outcomes" aria-label="Batch extraction results">{batchOutcomes.map((outcome) => (
            <li className={outcome.status} key={outcome.url}><strong>{outcome.status}</strong><span>{outcome.url}</span>{outcome.reason && <small>{outcome.reason}</small>}</li>
          ))}</ol>}
        </section>

        <section aria-labelledby="evidence-heading">
          <h2 id="evidence-heading">Stored extracted source data</h2>
          {lastExtractionAttempt?.outcome === "failed" && <aside className="extraction-status failure" role="alert">
            <strong>Latest extraction failed</strong>
            <p>{lastExtractionAttempt.url}</p>
            <span>{lastExtractionAttempt.detail}</span>
            <small>Previously stored source data is retained below and does not represent this failed request.</small>
          </aside>}
          {lastExtractionAttempt?.outcome === "succeeded" && <aside className="extraction-status success">
            <strong>Latest extraction succeeded</strong>
            <p>{lastExtractionAttempt.url}</p>
          </aside>}
          {run.evidence.length ? run.evidence.map((item) => (
            <article className="evidence" key={`${item.url}-${item.retrieved_at}`}>
              <div className="metadata"><a href={item.url} target="_blank" rel="noreferrer">{item.url}</a><span>{item.extraction_method}</span></div><p>{item.text}</p>
            </article>
          )) : <p>No source data has been extracted for this run yet.</p>}
        </section>

        <section aria-labelledby="audit-heading">
          <h2 id="audit-heading">Audit trail</h2>
          <p className="hint">Select an event to inspect its recorded metadata.</p>
          <ol className="audit">{run.audit_events.map((event, index) => {
            const selected = selectedAuditIndex === index;
            return <li className={selected ? "selected" : ""} key={`${event.event_type}-${event.occurred_at}`}>
              <button className="audit-event" type="button" onClick={() => setSelectedAuditIndex(selected ? null : index)}>
                <span><strong>{event.event_type}</strong><small>{selected ? "Hide metadata" : "View metadata"}</small></span>
                <span>{new Date(event.occurred_at).toLocaleString()}</span>
              </button>
              {selected && <pre className="audit-details">{JSON.stringify(event.details, null, 2)}</pre>}
            </li>;
          })}</ol>
        </section>
      </>}
    </main>
  );
}
