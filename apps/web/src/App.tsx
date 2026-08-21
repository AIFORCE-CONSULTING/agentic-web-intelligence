import { useEffect, useState } from "react";

type Health = {
  status: string;
  service: string;
  environment: string;
};

const apiBaseUrl = import.meta.env.VITE_PLATFORM_API_URL ?? "http://localhost:8000";

export function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();

    fetch(`${apiBaseUrl}/health/ready`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error("Agentic Web Intelligence API is unavailable.");
        return (await response.json()) as Health;
      })
      .then(setHealth)
      .catch((reason: unknown) => {
        if (reason instanceof DOMException && reason.name === "AbortError") return;
        setError("Waiting for the Agentic Web Intelligence API.");
      });

    return () => controller.abort();
  }, []);

  return (
    <main>
      <p className="eyebrow">Agentic Web Intelligence</p>
      <h1>Forward-deployed engineering, made repeatable.</h1>
      <p className="lead">
        A governed workspace for web discovery, content extraction, agent workflows, and
        evidence-backed delivery.
      </p>

      <section aria-labelledby="platform-heading">
        <h2 id="platform-heading">Platform foundation</h2>
        <ul>
          <li>React operator console and FastAPI platform boundary</li>
          <li>Docker-first local environment and continuous validation</li>
          <li>Versioned architecture, decisions, and delivery documentation</li>
        </ul>
      </section>

      <section className="status" aria-live="polite">
        <h2>Agentic Web Intelligence API</h2>
        {health ? (
          <p>
            <strong>{health.status}</strong> - {health.service} ({health.environment})
          </p>
        ) : (
          <p>{error ?? "Checking readiness..."}</p>
        )}
      </section>
    </main>
  );
}
