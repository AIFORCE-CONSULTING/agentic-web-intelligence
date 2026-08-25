import { FormEvent, useEffect, useState } from "react";

type Health = { status: string; service: string; environment: string };
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

function PrimaryNavigation() {
  return (
    <nav className="primary-nav" aria-label="Primary navigation">
      <a className={!isDeveloperRoute ? "active" : ""} href="/">Research workspace</a>
      <a className={isDeveloperRoute ? "active" : ""} href="/developer">Developer hub</a>
    </nav>
  );
}

function DeveloperHub({ health }: { health: Health | null }) {
  return (
    <>
      <header>
        <p className="eyebrow">Platform access</p>
        <PrimaryNavigation />
        <h1>Developer hub</h1>
        <p className="lead">One local starting point for the platform console, API contract, documentation, and service health.</p>
      </header>
      <section aria-labelledby="developer-services-heading">
        <div className="section-heading"><div><p className="eyebrow">Local services</p><h2 id="developer-services-heading">Platform entry points</h2></div><span className={`connection ${health ? "online" : "offline"}`}>{health ? "API ready" : "API unavailable"}</span></div>
        <div className="developer-grid">
          <a className="developer-card" href="/"><strong>Research workspace</strong><span>Create, reopen, and inspect governed research runs.</span><small>localhost:3000</small></a>
          <a className="developer-card" href={`${apiBaseUrl}/docs`} target="_blank" rel="noreferrer"><strong>API reference</strong><span>Explore and execute the FastAPI OpenAPI contract.</span><small>{apiBaseUrl}/docs</small></a>
          <a className="developer-card" href={`${apiBaseUrl}/openapi.json`} target="_blank" rel="noreferrer"><strong>OpenAPI schema</strong><span>Use the machine-readable API contract for integrations.</span><small>{apiBaseUrl}/openapi.json</small></a>
          <a className="developer-card" href="http://localhost:8001" target="_blank" rel="noreferrer"><strong>Platform documentation</strong><span>Read architecture, web-research, and prompt-template guides.</span><small>localhost:8001 · start the documentation profile</small></a>
        </div>
      </section>
      <section aria-labelledby="developer-guidance-heading">
        <h2 id="developer-guidance-heading">Local guidance</h2>
        <p>Run <code>docker compose --profile documentation up --build</code> to make the documentation site available. SearXNG remains internal-only; all web research goes through the governed API.</p>
      </section>
    </>
  );
}

export function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [question, setQuestion] = useState("What is agentic web intelligence?");
  const [url, setUrl] = useState("");
  const [run, setRun] = useState<ResearchRun | null>(null);
  const [runLibrary, setRunLibrary] = useState<ResearchRunSummary[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`${apiBaseUrl}/health/ready`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("API unavailable");
        return (await response.json()) as Health;
      })
      .then(setHealth)
      .catch(() => setHealth(null));
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
      setQuestion(reopened.question);
      setUrl(reopened.sources[0]?.url ?? "");
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
      setUrl(created.sources[0]?.url ?? "");
      await refreshRunLibrary();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create a research run.");
    } finally {
      setBusy(false);
    }
  }

  async function extractEvidence(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!run) return;
    setBusy(true);
    setError(null);
    try {
      await apiRequest<Evidence>(`/v1/research/runs/${run.id}/extract`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      setRun(await apiRequest<ResearchRun>(`/v1/research/runs/${run.id}`));
      await refreshRunLibrary();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to extract evidence.");
    } finally {
      setBusy(false);
    }
  }

  if (isDeveloperRoute) {
    return <main><DeveloperHub health={health} /></main>;
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
          <div className="section-heading"><div><p className="eyebrow">Run {run.id.slice(0, 8)}</p><h2 id="sources-heading">2. Review source candidates</h2></div><span className="badge">{run.status}</span></div>
          {run.sources.length ? <ol className="sources">{run.sources.map((source) => (
            <li key={`${source.rank}-${source.url}`}><button className="source" type="button" onClick={() => setUrl(source.url)}>
              <span className="rank">{source.rank}</span><span><strong>{source.title}</strong><small>{source.url}</small>{source.snippet && <span>{source.snippet}</span>}</span>
            </button></li>
          ))}</ol> : <p>No public source candidates were returned for this question.</p>}
        </section>

        <section aria-labelledby="extract-heading">
          <h2 id="extract-heading">3. Extract governed evidence</h2>
          <form onSubmit={extractEvidence} className="form-row">
            <label>Public source URL
              <input type="url" value={url} onChange={(event) => setUrl(event.target.value)} required />
            </label>
            <button type="submit" disabled={busy || !url}>{busy ? "Extracting…" : "Extract"}</button>
          </form>
          <p className="hint">Only public HTML or plain-text pages are allowed. Downloads, private URLs, and browser interaction remain blocked.</p>
        </section>

          <section aria-labelledby="evidence-heading">
            <h2 id="evidence-heading">Extracted source data</h2>
          {run.evidence.length ? run.evidence.map((item) => (
            <article className="evidence" key={`${item.url}-${item.retrieved_at}`}>
              <div className="metadata"><a href={item.url} target="_blank" rel="noreferrer">{item.url}</a><span>{item.extraction_method}</span></div><p>{item.text}</p>
            </article>
          )) : <p>No source data has been extracted for this run yet.</p>}
        </section>

        <section aria-labelledby="audit-heading"><h2 id="audit-heading">Audit trail</h2><ol className="audit">{run.audit_events.map((event) => (
          <li key={`${event.event_type}-${event.occurred_at}`}><strong>{event.event_type}</strong><span>{new Date(event.occurred_at).toLocaleString()}</span></li>
        ))}</ol></section>
      </>}
    </main>
  );
}
