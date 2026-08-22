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

const apiBaseUrl = import.meta.env.VITE_PLATFORM_API_URL ?? "http://localhost:8000";

async function apiRequest<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${apiBaseUrl}${path}`, options);
  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { detail?: string } | null;
    throw new Error(payload?.detail ?? "The platform request could not be completed.");
  }
  return (await response.json()) as T;
}

export function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [question, setQuestion] = useState("What is agentic web intelligence?");
  const [url, setUrl] = useState("");
  const [run, setRun] = useState<ResearchRun | null>(null);
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
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to extract evidence.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <header>
        <p className="eyebrow">Agentic Web Intelligence</p>
        <h1>Research with a durable evidence trail.</h1>
        <p className="lead">Discover public sources, extract bounded evidence, and keep an inspectable record of every platform decision.</p>
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
          <h2 id="evidence-heading">Stored evidence</h2>
          {run.evidence.length ? run.evidence.map((item) => (
            <article className="evidence" key={`${item.url}-${item.retrieved_at}`}>
              <div className="metadata"><a href={item.url} target="_blank" rel="noreferrer">{item.url}</a><span>{item.extraction_method}</span></div><p>{item.text}</p>
            </article>
          )) : <p>No evidence has been extracted for this run yet.</p>}
        </section>

        <section aria-labelledby="audit-heading"><h2 id="audit-heading">Audit trail</h2><ol className="audit">{run.audit_events.map((event) => (
          <li key={`${event.event_type}-${event.occurred_at}`}><strong>{event.event_type}</strong><span>{new Date(event.occurred_at).toLocaleString()}</span></li>
        ))}</ol></section>
      </>}
    </main>
  );
}
