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

const apiBaseUrl = import.meta.env.VITE_PLATFORM_API_URL ?? "http://localhost:8000";
const isDeveloperRoute = window.location.pathname === "/developer";

async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, options);
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
      <a className={!isDeveloperRoute ? "active" : ""} href="/">Research workspace</a>
      <a className={isDeveloperRoute ? "active" : ""} href="/developer">Developer hub</a>
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
    if (health) void refreshRunLibrary();
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
