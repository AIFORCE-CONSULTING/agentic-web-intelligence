import { FormEvent, MouseEvent, useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

type Health = { status: string; service: string; environment: string };
type DiscoverySourceCount = 50 | 40 | 30 | 20 | 10 | 5;
type DependencyHealth = {
  name: string; status: "ready" | "degraded" | "unavailable" | "unconfigured"; detail: string;
};
type ServiceHealth = Health & { services: DependencyHealth[] };
type Source = {
  rank: number; title: string; url: string; snippet: string; engine?: string | null;
  preflight_status: "pending" | "checking" | "ready_to_extract" | "review_required" | "blocked" | "unreachable";
  preflight_reason?: string | null; preflight_checked_at?: string | null;
  preflight_content_type?: string | null; preflight_content_hash?: string | null;
  preflight_final_url?: string | null;
  preflight_redirect_result?: "no_redirect" | "redirected" | "redirect_limit_exceeded" | "unsafe_destination_blocked" | null;
  preflight_trust_disposition?: string | null;
};
type Evidence = {
  url: string; retrieved_at: string; content_type: string; text: string; content_hash: string;
  extraction_method: string; requested_url?: string | null;
  redirect_result?: "no_redirect" | "redirected" | "redirect_limit_exceeded" | "unsafe_destination_blocked" | null;
};
type EvidenceTrustEvaluation = {
  id: string; source_url: string; content_hash: string; policy_version: string;
  disposition: "eligible" | "eligible_with_notice" | "review_required" | "blocked";
  base_disposition: "eligible" | "eligible_with_notice" | "review_required" | "blocked";
  rule_outcomes: TrustRuleOutcome[]; component_version: string; created_at: string;
  override_outcome?: "accepted" | "rejected" | null;
  override_actor_user_id?: string | null;
  override_reason?: string | null; override_expires_at?: string | null;
  override_created_at?: string | null;
};
type TrustRuleOutcome = {
  rule: string; outcome: "passed" | "notice" | "review_required" | "blocked"; detail: string;
};
type EvidenceTrustEvaluationList = { evaluations: EvidenceTrustEvaluation[] };
type ReviewFormState = { evidence: Evidence; evaluation: EvidenceTrustEvaluation };
type EffectiveWebTrustPolicy = {
  version: string;
  rules: Record<string, string | number | string[]>;
};
type AuditEvent = { event_type: string; occurred_at: string; details: Record<string, unknown> };
type ResearchRun = {
  id: string; question: string; status: string; sources: Source[]; evidence: Evidence[];
  audit_events: AuditEvent[]; failed_stage?: string | null; failure_code?: string | null;
  failure_explanation?: string | null; retryable: boolean; failed_at?: string | null;
};
type ResearchRunSummary = {
  id: string; question: string; status: string; created_at: string; updated_at: string;
  source_count: number; evidence_count: number; failed_stage?: string | null;
  failure_code?: string | null; failure_explanation?: string | null; retryable: boolean;
};
type ResearchRunList = { runs: ResearchRunSummary[] };
type EvidenceSummaryBatch = {
  id: string; workSetId?: string; route: "undetermined" | "direct" | "durable"; status: string;
  sources: {
    content_hash?: string | null; url: string; chunk_count?: number | null; status: string;
    summary?: string | null; keywords?: string[] | null;
    keyword_coverage?: Record<string, string> | null; prompt_version?: string | null;
    evidence_sufficient?: boolean | null;
    artifact_reused?: boolean;
    failure_reason?: string | null;
    failure_category?: string | null;
    summary_attempt_count?: number;
    model_version?: string | null;
  }[];
};
type EvidenceSummaryWorkSet = {
  id: string; status: "created" | "waiting" | "completed" | "failed"; execution_ids: string[];
};
type ResearchReport = {
  id?: string | null; run_id: string; markdown: string; model_name?: string | null;
  prompt_version: string; contract_version: string; quality_grade: "PASS" | "FAIL";
  quality_reasons: { code: string; message: string }[];
  report_origin: "model_pass" | "model_fail" | "fallback"; current: boolean;
  supporting_sources: { source_ref: string; topic_id: string; title: string; url: string }[];
  exclusions: { title: string; url: string; topic_ids: string[]; reason_code: string; reason: string }[];
  created_at: string;
};
type WorkspaceSummaryArtifact = {
  run_id: string; url: string; title: string; chunk_count?: number | null;
  summary: string; keywords: string[]; keyword_coverage?: Record<string, string> | null;
  prompt_version?: string | null; evidence_sufficient: boolean;
};
type WorkspaceSummaryArtifactList = { artifacts: WorkspaceSummaryArtifact[] };
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
  github_projects: GitHubProjectStatus;
};
type GitHubProjectStatus = {
  mode: "disabled" | "invalid" | "ready"; owner?: string | null;
  project_number?: number | null; project_url?: string | null; detail: string;
};
type GitHubProjectInfo = {
  title: string; owner: string; project_number: number; project_url: string; priority_options: string[];
};
type GitHubDraftItem = { id: string; title: string; priority?: string | null };
type GitHubDraftItemList = { items: GitHubDraftItem[] };
type LocalModelProviderConfiguration = {
  workspace_id: string; endpoint_url: string; model_name: string; updated_at: string;
};
type LocalModelProviderReadiness = {
  mode: "unconfigured" | "ready" | "unavailable" | "invalid";
  provider: "ollama"; endpoint_url?: string | null; model_name?: string | null; detail: string;
};
type ResearchDurableOperation = {
  id: string; operation_type: "candidate_preflight" | "evidence_summary";
  route: "direct" | "temporal"; status: string; updated_at: string;
  failure_code?: string | null; failure_explanation?: string | null;
};
type ResearchDurableWork = {
  research_run_id: string; question: string; research_status: string; updated_at: string;
  operations: ResearchDurableOperation[];
};
type ResearchDurableWorkList = { items: ResearchDurableWork[] };

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
          <a className="developer-card" href="/admin"><strong>Durable research work</strong><span>Inspect direct and Temporal-backed research operations from their stored platform records.</span><small>localhost:3000/admin</small></a>
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
  const [githubStatus, setGithubStatus] = useState<GitHubProjectStatus | null>(null);
  const [localModel, setLocalModel] = useState<LocalModelProviderConfiguration | null>(null);
  const [localModelReadiness, setLocalModelReadiness] = useState<LocalModelProviderReadiness | null>(null);
  const [localModelEndpoint, setLocalModelEndpoint] = useState("http://host.docker.internal:11434");
  const [localModelName, setLocalModelName] = useState("qwen3:1.7b");
  const [githubProject, setGithubProject] = useState<GitHubProjectInfo | null>(null);
  const [draftItems, setDraftItems] = useState<GitHubDraftItem[]>([]);
  const [roadmapError, setRoadmapError] = useState<string | null>(null);
  const [draftTitle, setDraftTitle] = useState("");
  const [draftBody, setDraftBody] = useState("");
  const [draftPriority, setDraftPriority] = useState("");
  const [durableWork, setDurableWork] = useState<ResearchDurableWork[]>([]);
  const [selectedDurableWork, setSelectedDurableWork] = useState<ResearchDurableWork | null>(null);
  const [durableWorkError, setDurableWorkError] = useState<string | null>(null);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [bootstrapSecret, setBootstrapSecret] = useState("");
  const [showBootstrap, setShowBootstrap] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadAdminData() {
    const currentUser = await apiRequest<AuthenticatedUser>("/v1/auth/me");
    setUser(currentUser);
    setRoadmapError(null);
    if (currentUser.role === "administrator" || currentUser.role === "operator") {
      try {
        const work = await apiRequest<ResearchDurableWorkList>("/v1/research/durable-work");
        setDurableWork(work.items);
        setDurableWorkError(null);
      } catch (reason) {
        setDurableWork([]);
        setSelectedDurableWork(null);
        setDurableWorkError(reason instanceof Error ? reason.message : "Unable to load durable work.");
      }
      const status = await apiRequest<GitHubProjectStatus>("/v1/github/projects/status");
      setGithubStatus(status);
      if (status.mode === "ready") {
        try {
          const [project, items] = await Promise.all([
            apiRequest<GitHubProjectInfo>("/v1/github/projects/roadmap"),
            apiRequest<GitHubDraftItemList>("/v1/github/projects/draft-items"),
          ]);
          setGithubProject(project);
          setDraftItems(items.items);
        } catch (reason) {
          setGithubProject(null);
          setDraftItems([]);
          setRoadmapError(
            reason instanceof Error ? reason.message : "Unable to load the GitHub roadmap."
          );
        }
      } else {
        setGithubProject(null);
        setDraftItems([]);
      }
    } else {
      setGithubStatus(null);
      setGithubProject(null);
      setDraftItems([]);
      setDurableWork([]);
      setSelectedDurableWork(null);
      setDurableWorkError(null);
    }
    if (currentUser.role !== "administrator") {
      setEvents([]);
      setPosture(null);
      return;
    }
    const [audit, securityPosture] = await Promise.all([
      apiRequest<SecurityAuditEventList>("/v1/audit/security"),
      apiRequest<OperationalSecurityStatus>("/v1/operations/security-status"),
    ]);
    const provider = await apiRequest<LocalModelProviderConfiguration | null>("/v1/local-model/provider");
    setLocalModel(provider);
    if (provider) {
      setLocalModelEndpoint(provider.endpoint_url);
      setLocalModelName(provider.model_name);
    }
    setEvents(audit.events);
    setPosture(securityPosture);
  }

  async function saveLocalModel(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const saved = await apiRequest<LocalModelProviderConfiguration>("/v1/local-model/provider", {
        method: "PUT", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ endpoint_url: localModelEndpoint, model_name: localModelName }),
      });
      setLocalModel(saved);
      setLocalModelReadiness(null);
      await loadAdminData();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to save local model configuration.");
    } finally { setBusy(false); }
  }

  async function checkLocalModelReadiness() {
    setBusy(true);
    setError(null);
    try {
      setLocalModelReadiness(await apiRequest<LocalModelProviderReadiness>("/v1/local-model/provider/readiness", { method: "POST" }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to check local model readiness.");
    } finally { setBusy(false); }
  }

  async function createDraftItem(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await apiRequest<GitHubDraftItem>("/v1/github/projects/draft-items", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: draftTitle,
          body: draftBody || undefined,
          priority: draftPriority || undefined,
        }),
      });
      setDraftTitle("");
      setDraftBody("");
      setDraftPriority("");
      await loadAdminData();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create the roadmap item.");
    } finally {
      setBusy(false);
    }
  }

  async function updateDraftPriority(itemId: string, priority: string) {
    setBusy(true);
    setError(null);
    try {
      await apiRequest<GitHubDraftItem>(`/v1/github/projects/draft-items/${encodeURIComponent(itemId)}/priority`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ priority }),
      });
      await loadAdminData();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to update Priority.");
    } finally {
      setBusy(false);
    }
  }

  async function inspectDurableWork(runId: string) {
    setBusy(true);
    setError(null);
    try {
      setSelectedDurableWork(await apiRequest<ResearchDurableWork>(`/v1/research/runs/${encodeURIComponent(runId)}/durable-work`));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to inspect durable work.");
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    void loadAdminData().catch((reason) => {
      setUser(null);
      setEvents([]);
      setPosture(null);
      setDurableWork([]);
      setSelectedDurableWork(null);
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
        {(user.role === "administrator" || user.role === "operator") && githubStatus && <section aria-labelledby="roadmap-heading">
          <div className="section-heading"><div><p className="eyebrow">GitHub Projects</p><h2 id="roadmap-heading">Roadmap</h2></div><button type="button" className="secondary" onClick={() => void loadAdminData()} disabled={busy}>Refresh</button></div>
          {githubStatus.mode !== "ready" && <p className="hint">{githubStatus.detail}</p>}
          {roadmapError && <p className="error" role="alert">{roadmapError}</p>}
          {githubProject && <>
            <p className="hint">Managing draft-only cards in <a href={githubProject.project_url} target="_blank" rel="noreferrer">{githubProject.title}</a>. No repository Issues are created.</p>
            <form className="auth-form roadmap-form" onSubmit={createDraftItem}>
              <label>Task title<input value={draftTitle} onChange={(event) => setDraftTitle(event.target.value)} maxLength={256} required /></label>
              <label>Notes<textarea value={draftBody} onChange={(event) => setDraftBody(event.target.value)} maxLength={65536} /></label>
              <label>Priority<select value={draftPriority} onChange={(event) => setDraftPriority(event.target.value)}><option value="">Not set</option>{githubProject.priority_options.map((priority) => <option key={priority} value={priority}>{priority}</option>)}</select></label>
              <button type="submit" disabled={busy}>{busy ? "Saving…" : "Create draft task"}</button>
            </form>
            {draftItems.length ? <ol className="roadmap-items">{draftItems.map((item) => <li key={item.id}><div><strong>{item.title}</strong><small>Draft item</small></div><label>Priority<select value={item.priority ?? ""} onChange={(event) => { if (event.target.value) void updateDraftPriority(item.id, event.target.value); }} disabled={busy}><option value="" disabled>Not set</option>{githubProject.priority_options.map((priority) => <option key={priority} value={priority}>{priority}</option>)}</select></label></li>)}</ol> : <p>No draft tasks yet.</p>}
          </>}
        </section>}
        {(user.role === "administrator" || user.role === "operator") && <section aria-labelledby="durable-work-heading">
          <div className="section-heading"><div><p className="eyebrow">Human-operated workflow</p><h2 id="durable-work-heading">Durable work</h2></div><button type="button" className="secondary" onClick={() => void loadAdminData()} disabled={busy}>Refresh</button></div>
          <p className="hint">Read-only research operations composed from their owning platform records. Temporal execution history is not used as business status.</p>
          {durableWorkError && <p className="error" role="alert">{durableWorkError}</p>}
          {durableWork.length ? <ol className="runtime-runs">{durableWork.map((work) => <li key={work.research_run_id}><button type="button" className="runtime-run" onClick={() => void inspectDurableWork(work.research_run_id)} disabled={busy}><span><strong>{work.question}</strong><small>Updated {new Date(work.updated_at).toLocaleString()} · {work.operations.length} operations</small></span><span className={`runtime-status ${work.research_status}`}>{work.research_status.replaceAll("_", " ")}</span></button></li>)}</ol> : !durableWorkError && <p>No durable research work has been recorded for this workspace.</p>}
          {selectedDurableWork && <DurableResearchDetail work={selectedDurableWork} />}
        </section>}
        {user.role === "administrator" && posture && <section aria-labelledby="security-posture-heading">
          <div className="section-heading"><div><p className="eyebrow">Deployment controls</p><h2 id="security-posture-heading">Security posture</h2></div><button type="button" className="secondary" onClick={() => void loadAdminData()} disabled={busy}>Refresh</button></div>
          <p className="hint">Safe configuration and dependency status for this deployment. Secret values are never displayed.</p>
          <div className="posture-grid">
            {[posture.identity_persistence, posture.security_audit_persistence].map((item) => <article className={"service-card " + item.status} key={item.name}><div><strong>{item.name}</strong><span>{item.status}</span></div><p>{item.detail}</p></article>)}
            <article className={"service-card " + (posture.enterprise_identity.mode === "invalid" ? "unavailable" : posture.enterprise_identity.mode === "ready" ? "ready" : "unconfigured")}><div><strong>Enterprise identity</strong><span>{posture.enterprise_identity.mode}</span></div><p>{posture.enterprise_identity.detail}</p></article>
            <article className={"service-card " + (posture.github_projects.mode === "invalid" ? "unavailable" : posture.github_projects.mode === "ready" ? "ready" : "unconfigured")}><div><strong>GitHub Projects</strong><span>{posture.github_projects.mode}</span></div><p>{posture.github_projects.detail}</p></article>
          </div>
          <div className="posture-details">
            <article><h3>Deployment secrets</h3><ul>{posture.secrets.secrets.map((secret) => <li key={secret.name}><strong>{secret.name}</strong><span className={secret.configured && secret.valid ? "ready-text" : "warning-text"}>{secret.detail}</span><small>{secret.purpose}</small></li>)}</ul></article>
            <article><h3>Governed tools</h3><ul>{posture.tool_registry.tools.map((tool) => <li key={tool.name}><strong>{tool.name}</strong><span>{tool.required_permission} · {tool.audit_required ? "audited" : "not audited"}</span><small>{tool.purpose}</small></li>)}</ul></article>
          </div>
        </section>}
        {user.role === "administrator" && <section aria-labelledby="local-model-heading">
          <div className="section-heading"><div><p className="eyebrow">Phase 6 boundary</p><h2 id="local-model-heading">Local model provider</h2></div><button type="button" className="secondary" onClick={() => void checkLocalModelReadiness()} disabled={busy || !localModel}>Check readiness</button></div>
          <p className="hint">Configure an already-running local Ollama service. Saving this does not install Ollama, download a model, or perform inference.</p>
          <form className="roadmap-form" onSubmit={saveLocalModel}>
            <label>Ollama endpoint<input value={localModelEndpoint} onChange={(event) => setLocalModelEndpoint(event.target.value)} required /></label>
            <label>Installed model<input value={localModelName} onChange={(event) => setLocalModelName(event.target.value)} required /></label>
            <button type="submit" disabled={busy}>Save provider</button>
          </form>
          {localModel && <p className="hint">Configured for this workspace: <code>{localModel.endpoint_url}</code> · <code>{localModel.model_name}</code></p>}
          {localModelReadiness && <p className={localModelReadiness.mode === "ready" ? "ready-text" : "warning-text"}>{localModelReadiness.mode}: {localModelReadiness.detail}</p>}
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

function DurableResearchDetail({ work }: { work: ResearchDurableWork }) {
  return <article className="runtime-detail" aria-label="Selected durable research work">
    <div className="section-heading"><div><p className="eyebrow">Selected research</p><h3>{work.question}</h3></div><span className={`runtime-status ${work.research_status}`}>{work.research_status.replaceAll("_", " ")}</span></div>
    <p className="hint">The research status comes from the canonical research record. Each operation below comes from the application store that owns it.</p>
    <div className="runtime-detail-grid">
      <article><h4>Operations</h4><ul>{work.operations.map((operation) => <li key={operation.id}><strong>{operation.operation_type.replaceAll("_", " ")}</strong><span>{operation.status.replaceAll("_", " ")} · {operation.route}</span><small>Updated {new Date(operation.updated_at).toLocaleString()}</small>{operation.failure_explanation && <small className="warning-text">{operation.failure_code ? `${operation.failure_code}: ` : ""}{operation.failure_explanation}</small>}</li>)}</ul></article>
    </div>
  </article>;
}

export function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [serviceHealth, setServiceHealth] = useState<ServiceHealth | null>(null);
  const [question, setQuestion] = useState("What is agentic web intelligence?");
  const [discoverySourceCount, setDiscoverySourceCount] = useState<DiscoverySourceCount>(50);
  const [run, setRun] = useState<ResearchRun | null>(null);
  const [runLibrary, setRunLibrary] = useState<ResearchRunSummary[]>([]);
  const [selectedAuditIndex, setSelectedAuditIndex] = useState<number | null>(null);
  const [summaryBatch, setSummaryBatch] = useState<EvidenceSummaryBatch | null>(null);
  const [workspaceSummaries, setWorkspaceSummaries] = useState<WorkspaceSummaryArtifact[]>([]);
  const [report, setReport] = useState<ResearchReport | null>(null);
  const [trustEvaluations, setTrustEvaluations] = useState<EvidenceTrustEvaluation[]>([]);
  const [trustPolicy, setTrustPolicy] = useState<EffectiveWebTrustPolicy | null>(null);
  const [reviewForm, setReviewForm] = useState<ReviewFormState | null>(null);
  const [reviewReason, setReviewReason] = useState("");
  const [reviewExpiresAt, setReviewExpiresAt] = useState("");
  const [candidateStatusFilter, setCandidateStatusFilter] = useState<Source["preflight_status"] | "all">("all");
  const [selectedSummaryUrl, setSelectedSummaryUrl] = useState<string | null>(null);
  const sourceSummaryPanelRef = useRef<HTMLDivElement | null>(null);
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
    if (health && !isDeveloperRoute && !isAdminRoute) {
      void refreshRunLibrary();
      void loadWorkspaceSummaries();
      void loadTrustPolicy();
    }
  }, [health]);

  useEffect(() => {
    if (!summaryBatch || !["awaiting_execution", "summarizing"].includes(summaryBatch.status)) return;
    const timer = window.setInterval(() => {
      const update = summaryBatch.workSetId && run
        ? loadSummaryBatch(run.id)
        : apiRequest<EvidenceSummaryBatch>(`/v1/evidence-summary-executions/${summaryBatch.id}`)
          .then((updated) => {
            setSummaryBatch(updated);
            if (updated.status === "completed") {
              void loadWorkspaceSummaries();
              if (run) void loadReport(run.id);
            }
          });
      void update.catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [summaryBatch]);

  useEffect(() => {
    if (!run || ["completed", "failed", "awaiting_review"].includes(run.status)) return;
    const timer = window.setInterval(() => {
      void apiRequest<ResearchRun>(`/v1/research/runs/${run.id}`).then((refreshed) => {
        setRun(refreshed);
        if (["completed", "failed", "awaiting_review"].includes(refreshed.status)) {
          void refreshRunLibrary();
          void loadSummaryBatch(refreshed.id);
          void loadReport(refreshed.id);
        }
      }).catch(() => undefined);
    }, 2000);
    return () => window.clearInterval(timer);
  }, [run?.id, run?.status]);

  async function reopenRun(runId: string) {
    setBusy(true);
    setError(null);
    try {
      const reopened = await apiRequest<ResearchRun>(`/v1/research/runs/${runId}`);
      setRun(reopened);
      await refreshTrustEvaluations(reopened.id);
      setSelectedAuditIndex(null);
      setSelectedSummaryUrl(null);
      setReviewForm(null);
      setCandidateStatusFilter("all");
      setQuestion(reopened.question);
      await loadSummaryBatch(reopened.id);
      await loadWorkspaceSummaries();
      await loadReport(reopened.id);
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
        body: JSON.stringify({
          question,
          max_results: discoverySourceCount,
        }),
      });
      setRun(created);
      setTrustEvaluations([]);
      setSelectedAuditIndex(null);
      setSelectedSummaryUrl(null);
      setReviewForm(null);
      setCandidateStatusFilter("all");
      setSummaryBatch(null);
      setReport(null);
      await loadSummaryBatch(created.id);
      await loadWorkspaceSummaries();
      await loadReport(created.id);
      await refreshRunLibrary();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to create a research run.");
    } finally {
      setBusy(false);
    }
  }

  async function loadSummaryBatch(runId: string) {
    try {
      const workSet = await apiRequest<EvidenceSummaryWorkSet>(
        `/v1/research/runs/${runId}/evidence-summary-work-set`,
      );
      const executions = await Promise.all(
        workSet.execution_ids.map((id) => apiRequest<EvidenceSummaryBatch>(`/v1/evidence-summary-executions/${id}`)),
      );
      setSummaryBatch({
        id: workSet.id,
        workSetId: workSet.id,
        route: "durable",
        status: workSet.status === "waiting" || workSet.status === "created" ? "summarizing" : workSet.status,
        sources: executions.flatMap((execution) => execution.sources),
      });
    } catch {
      setSummaryBatch(null);
    }
  }

  async function loadWorkspaceSummaries() {
    try {
      const response = await apiRequest<WorkspaceSummaryArtifactList>(
        "/v1/evidence-summary-artifacts",
      );
      setWorkspaceSummaries(response.artifacts);
    } catch {
      setWorkspaceSummaries([]);
    }
  }

  async function loadReport(runId: string) {
    try {
      setReport(await apiRequest<ResearchReport>(`/v1/research/runs/${runId}/report`));
    } catch {
      setReport(null);
    }
  }

  async function refreshTrustEvaluations(runId: string) {
    const response = await apiRequest<EvidenceTrustEvaluationList>(
      `/v1/research/runs/${runId}/evidence-trust`,
    );
    setTrustEvaluations(response.evaluations);
    return response.evaluations;
  }

  async function loadTrustPolicy() {
    try {
      setTrustPolicy(await apiRequest<EffectiveWebTrustPolicy>("/v1/web-trust-policy"));
    } catch {
      setTrustPolicy(null);
    }
  }

  function openStoredSummary(url: string, event?: MouseEvent<HTMLAnchorElement>) {
    event?.preventDefault();
    setSelectedSummaryUrl(url);
    window.requestAnimationFrame(() => {
      window.requestAnimationFrame(() => {
        sourceSummaryPanelRef.current?.scrollIntoView({ block: "start", behavior: "smooth" });
        sourceSummaryPanelRef.current?.focus({ preventScroll: true });
      });
    });
  }

  function openEvidenceReview(evidence: Evidence, evaluation: EvidenceTrustEvaluation) {
    setReviewForm({ evidence, evaluation });
    setReviewReason("");
    setReviewExpiresAt("");
  }

  function closeEvidenceReview() {
    setReviewForm(null);
    setReviewReason("");
    setReviewExpiresAt("");
  }

  async function acceptEvidenceForReview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!run || !reviewForm || !reviewReason.trim()) return;
    const expiresAt = reviewExpiresAt ? new Date(reviewExpiresAt) : null;
    if (expiresAt && (Number.isNaN(expiresAt.valueOf()) || expiresAt <= new Date())) {
      setError("Acceptance expiry must be in the future.");
      return;
    }
    if (!window.confirm("Accept this exact captured evidence version for automated use and start its summary?")) return;
    setBusy(true);
    setError(null);
    try {
      await apiRequest<EvidenceTrustEvaluation>(
        `/v1/research/runs/${run.id}/evidence-trust/accept`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source_url: reviewForm.evidence.url,
            content_hash: reviewForm.evidence.content_hash,
            reason: reviewReason.trim(),
            ...(expiresAt ? { expires_at: expiresAt.toISOString() } : {}),
          }),
        },
      );
      await refreshTrustEvaluations(run.id);
      await loadSummaryBatch(run.id);
      closeEvidenceReview();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Unable to accept the evidence.");
    } finally {
      setBusy(false);
    }
  }

  async function rejectEvidenceForReview() {
    if (!run || !reviewForm) return;
    if (!window.confirm("Reject this exact captured evidence version and continue without it?")) return;
    setBusy(true);
    setError(null);
    try {
      await apiRequest<EvidenceTrustEvaluation>(
        `/v1/research/runs/${run.id}/evidence-trust/reject`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            source_url: reviewForm.evidence.url,
            content_hash: reviewForm.evidence.content_hash,
            ...(reviewReason.trim() ? { reason: reviewReason.trim() } : {}),
          }),
        },
      );
      await refreshTrustEvaluations(run.id);
      await loadSummaryBatch(run.id);
      closeEvidenceReview();
    } catch (reason) {
      const message = reason instanceof Error ? reason.message : "Unable to reject the evidence.";
      try {
        const evaluations = await refreshTrustEvaluations(run.id);
        await loadSummaryBatch(run.id);
        const updated = evaluations.find((candidate) =>
          candidate.source_url === reviewForm.evidence.url
          && candidate.content_hash === reviewForm.evidence.content_hash
        );
        if (updated?.override_outcome === "rejected") {
          closeEvidenceReview();
          return;
        }
      } catch {
        // Preserve the original reject error when the follow-up refresh also fails.
      }
      setError(message);
    } finally {
      setBusy(false);
    }
  }

  if (isAdminRoute) return <AdminConsole />;

  if (isDeveloperRoute) {
    return <main><DeveloperHub health={health} serviceHealth={serviceHealth} onRefresh={() => void refreshServiceHealth()} /></main>;
  }

  const keywordGroups = new Map<string, { label: string; sources: WorkspaceSummaryArtifact[] }>();
  for (const source of workspaceSummaries) {
    for (const keyword of source.keywords) {
      const label = keyword.trim().replace(/\s+/g, " ");
      if (!label) continue;
      const key = label.toLocaleLowerCase();
      const group = keywordGroups.get(key) ?? { label, sources: [] as WorkspaceSummaryArtifact[] };
      group.sources.push(source);
      keywordGroups.set(key, group);
    }
  }
  const keywordCards = [...keywordGroups.values()].sort((left, right) => left.label.localeCompare(right.label));
  const candidateStatuses = run
    ? [...new Set(run.sources.map((source) => source.preflight_status))].sort()
    : [];
  const visibleCandidates = run
    ? run.sources.filter((source) => candidateStatusFilter === "all" || source.preflight_status === candidateStatusFilter)
    : [];
  const selectedSummary = workspaceSummaries.find((source) => source.url === selectedSummaryUrl) ?? null;
  const sourceTitle = (source: WorkspaceSummaryArtifact) => source.title || source.url;
  const platformReady = Boolean(health && serviceHealth?.status === "ready");
  const bootstrapStatus = serviceHealth?.services.find((service) => service.name === "Database bootstrap");

  return (
    <main>
      <header>
        <p className="eyebrow">Agentic Web Intelligence</p>
        <PrimaryNavigation />
        <h1>Research with a durable evidence trail.</h1>
        <p className="lead">Discover public sources, extract bounded source data, and keep an inspectable record of every platform decision.</p>
        <p className={`connection ${platformReady ? "online" : "offline"}`}>
          {platformReady ? "Platform ready" : health ? `Platform ${serviceHealth?.status ?? health.status}` : "API unavailable"}
        </p>
        {bootstrapStatus && bootstrapStatus.status !== "ready" && (
          <p className="hint">Database initialization: {bootstrapStatus.detail}</p>
        )}
      </header>

      <section aria-labelledby="run-heading">
        <h2 id="run-heading">Start a research run</h2>
        <form onSubmit={createRun} className="form-row">
          <label>Research question
            <input value={question} onChange={(event) => setQuestion(event.target.value)} required />
          </label>
          <label className="source-count">Sources
            <select
              value={discoverySourceCount}
              onChange={(event) => setDiscoverySourceCount(Number(event.target.value) as DiscoverySourceCount)}
              aria-label="Number of sources to discover"
            >
              {[30, 20, 10, 5].map((count) => <option key={count} value={count}>{count}</option>)}
            </select>
          </label>
          <button type="submit" disabled={busy || !platformReady}>{busy ? "Working…" : "Discover sources"}</button>
        </form>
      </section>

      {error && <p className="error" role="alert">{error}</p>}
      {run?.status === "failed" && <p className="error" role="alert">{run.failure_explanation ?? "Research processing failed."}{run.failed_stage ? ` Failed during ${run.failed_stage.replaceAll("_", " ")}.` : ""}{run.retryable ? " Select Discover sources to retry this research run." : ""}</p>}

      <section aria-labelledby="library-heading">
        <div className="section-heading"><div><p className="eyebrow">Persistent resources</p><h2 id="library-heading">Research run library</h2></div><button type="button" className="secondary" onClick={() => void refreshRunLibrary()} disabled={busy || !health}>Refresh</button></div>
        {runLibrary.length ? <ol className="run-library">{runLibrary.map((item) => (
          <li key={item.id}><button type="button" className="run-card" onClick={() => void reopenRun(item.id)} disabled={busy}>
            <span><strong>{item.question}</strong><small>Run {item.id.slice(0, 8)} · {new Date(item.updated_at).toLocaleString()}</small></span>
            <span className="run-counts">{item.source_count} sources · {item.evidence_count} evidence</span>
          </button></li>
        ))}</ol> : <p>No saved research runs yet. Start one above to create a durable resource.</p>}
      </section>

      {run && <section aria-labelledby="report-heading">
        <div className="section-heading"><div><p className="eyebrow">Grounded stored evidence</p><h2 id="report-heading">Final report</h2></div>{report && <span className="badge">{report.quality_grade} {report.report_origin === "fallback" ? "evidence briefing" : "report"}</span>}</div>
        {report ? <article className="source-summary report-markdown">
          <p className="hint">Generated {new Date(report.created_at).toLocaleString()} from eligible, relevant, evidence-sufficient stored source summaries.{report.model_name ? ` Model: ${report.model_name}.` : ""}</p>
          {!report.current && <aside className="error"><strong>Historical report</strong><p>This report was created from an earlier evidence set and is not the current report for this research run.</p></aside>}
          {report.quality_grade === "FAIL" && <aside className="error"><strong>Report quality: FAIL</strong>{report.quality_reasons.map((reason) => <p key={reason.code}>{reason.message}</p>)}</aside>}
          <ReactMarkdown components={{
            a: ({ href, children }) => {
              const sourceRef = href?.startsWith("#summary:") ? href.slice("#summary:".length) : null;
              const source = sourceRef ? report.supporting_sources.find((item) => item.source_ref === sourceRef) : null;
              return source ? (
                <a
                  href="#source-summary"
                  title={`Open stored summary ${source.source_ref}`}
                  onClick={(event) => openStoredSummary(source.url, event)}
                >
                  {children}
                </a>
              ) : <span title="Unsupported report link">{children}</span>;
            },
          }}>{report.markdown}</ReactMarkdown>
          {report.exclusions.length > 0 && <section className="report-exclusions" aria-label="Sources excluded from report findings">
            <h3>Sources not used for report findings</h3>
            <ul>{report.exclusions.map((source) => {
              const summary = workspaceSummaries.find((item) => item.url === source.url);
              return <li key={`${source.url}-${source.reason_code}`}>
                {summary ? <a href="#source-summary" onClick={(event) => openStoredSummary(summary.url, event)}><strong>{source.title}</strong></a> : <strong>{source.title}</strong>}: {source.reason}
              </li>;
            })}</ul>
          </section>}
        </article> : <p className="hint">A final report will appear here after the research workflow has enough eligible, relevant source summaries.</p>}
      </section>}

      {run && <>
        {trustPolicy && <section aria-labelledby="trust-policy-heading">
          <div className="section-heading"><div><p className="eyebrow">Read-only platform policy</p><h2 id="trust-policy-heading">Web trust policy</h2></div><span className="badge">{trustPolicy.version}</span></div>
          <dl className="trust-policy-details">{Object.entries(trustPolicy.rules).map(([rule, value]) => <div key={rule}><dt>{rule.replaceAll("_", " ")}</dt><dd>{Array.isArray(value) ? value.join(", ") : String(value)}</dd></div>)}</dl>
        </section>}
        <section aria-labelledby="sources-heading">
          <div className="section-heading"><div><p className="eyebrow">Run {run.id.slice(0, 8)}</p><h2 id="sources-heading">Candidate preflight</h2></div><div className="candidate-controls"><label>Status<select value={candidateStatusFilter} onChange={(event) => setCandidateStatusFilter(event.target.value as Source["preflight_status"] | "all")} aria-label="Filter candidate preflight by status"><option value="all">All statuses ({run.sources.length})</option>{candidateStatuses.map((status) => <option key={status} value={status}>{status.replaceAll("_", " ")} ({run.sources.filter((source) => source.preflight_status === status).length})</option>)}</select></label><span className="badge">{run.status.replaceAll("_", " ")}</span></div></div>
          {run.sources.length ? visibleCandidates.length ? <ol className="sources">{visibleCandidates.map((source) => (
            <li className="source-candidate" key={`${source.rank}-${source.url}`}><div className="source">
              <span className="rank">{source.rank}</span><span><strong>{source.title}</strong>{source.snippet && <span>{source.snippet}</span>}<small>Candidate preflight: {source.preflight_status.replaceAll("_", " ")}{source.preflight_trust_disposition ? ` · trust ${source.preflight_trust_disposition.replaceAll("_", " ")}` : ""}{source.preflight_redirect_result ? ` · retrieval ${source.preflight_redirect_result.replaceAll("_", " ")}` : ""}{source.preflight_reason ? ` · ${source.preflight_reason}` : ""}</small>{source.preflight_final_url && source.preflight_final_url !== source.url && <small>Captured from: {source.preflight_final_url}</small>}</span>
            </div><a className="source-link" href={source.url} target="_blank" rel="noreferrer" aria-label={`Open ${source.title} in a new tab`}>{source.url}<span aria-hidden="true"> ↗</span></a>{(() => {
              const evidence = run.evidence.find((item) => item.content_hash === source.preflight_content_hash && (item.requested_url === source.url || item.url === source.preflight_final_url || item.url === source.url));
              const evaluation = evidence && trustEvaluations.find((candidate) => candidate.source_url === evidence.url && candidate.content_hash === evidence.content_hash);
              if (!evidence || evaluation?.disposition !== "review_required") return null;
              if (evaluation.override_outcome === "rejected") {
                return <div className="candidate-review">
                  <span className="badge danger">Rejected after review</span>
                  {evaluation.override_reason && <small>{evaluation.override_reason}</small>}
                </div>;
              }
              const reviewing = reviewForm?.evidence.url === evidence.url
                && reviewForm.evidence.content_hash === evidence.content_hash;
              return <div className="candidate-review">
                <button type="button" className="secondary" onClick={() => reviewing ? closeEvidenceReview() : openEvidenceReview(evidence, evaluation)} disabled={busy}>{reviewing ? "Close review" : "Review evidence"}</button>
                {reviewing && <form className="evidence-review" onSubmit={(event) => void acceptEvidenceForReview(event)}>
                  <div className="section-heading"><div><p className="eyebrow">Human review required</p><h3>Review before automated use</h3></div><span className="badge">{evaluation.policy_version}</span></div>
                  <p className="hint">Acceptance applies only to this captured evidence version. It will start the platform-owned summary workflow after the decision is recorded.</p>
                  <dl className="review-details">
                    <div><dt>Requested URL</dt><dd>{evidence.requested_url ?? source.url}</dd></div>
                    <div><dt>Final evidence URL</dt><dd>{evidence.url}</dd></div>
                    <div><dt>Captured</dt><dd>{new Date(evidence.retrieved_at).toLocaleString()}</dd></div>
                    <div><dt>Evidence version</dt><dd>{evidence.content_hash}</dd></div>
                    <div><dt>Content type</dt><dd>{evidence.content_type}</dd></div>
                    <div><dt>Extracted characters</dt><dd>{evidence.text.length.toLocaleString()}</dd></div>
                  </dl>
                  <div className="review-rules"><strong>Policy evaluation</strong><ul>{evaluation.rule_outcomes.map((rule) => <li key={rule.rule} className={rule.outcome}><span>{rule.rule.replaceAll("_", " ")}</span><small>{rule.detail}</small></li>)}</ul></div>
                  <details className="review-evidence"><summary>Captured evidence</summary><pre>{evidence.text}</pre></details>
                  <label>Acceptance reason<textarea value={reviewReason} onChange={(event) => setReviewReason(event.target.value)} minLength={3} maxLength={500} required /></label>
                  <label>Acceptance expiry <span className="field-note">Optional. Leave blank for no expiry.</span><input type="datetime-local" value={reviewExpiresAt} onChange={(event) => setReviewExpiresAt(event.target.value)} /></label>
                  <div className="review-actions"><button type="submit" disabled={busy || !reviewReason.trim()}>Accept evidence and start summary</button><button type="button" className="danger" onClick={() => void rejectEvidenceForReview()} disabled={busy}>Reject evidence</button><button type="button" className="secondary" onClick={closeEvidenceReview} disabled={busy}>Cancel</button></div>
                </form>}
              </div>;
            })()}</li>
          ))}</ol> : <p className="hint">No candidates have the selected preflight status.</p> : <p>No public source candidates were returned for this question.</p>}
        </section>

        <section aria-labelledby="keywords-heading">
          <div className="section-heading"><div><p className="eyebrow">Workspace source summaries</p><h2 id="keywords-heading">Keywords</h2></div><span className="badge">{keywordCards.length} keyword{keywordCards.length === 1 ? "" : "s"}</span></div>
          {summaryBatch && <aside className={`extraction-status ${summaryBatch.status === "failed" ? "failure" : "success"}`}>
            <strong>{summaryBatch.status === "completed" ? "Evidence summaries complete" : summaryBatch.status === "failed" ? "Evidence summary processing failed" : "Evidence summary processing"}</strong>
            <p>{summaryBatch.status === "awaiting_execution" || summaryBatch.status === "summarizing" ? "The local model is working in the background. This panel refreshes automatically." : `${summaryBatch.sources.filter((source) => source.status === "completed").length} source${summaryBatch.sources.filter((source) => source.status === "completed").length === 1 ? "" : "s"} summarized.`}</p>
            {summaryBatch.sources.filter((source) => source.status === "failed").map((source) => <p key={source.url}><strong>{source.url}</strong>: {source.failure_reason ?? "Summary processing did not complete."} {source.failure_category ? `[${source.failure_category}] ` : ""}{source.summary_attempt_count ? `(${source.summary_attempt_count} attempt${source.summary_attempt_count === 1 ? "" : "s"}${source.model_version ? `, ${source.model_version}` : ""})` : ""}</p>)}
          </aside>}
          {keywordCards.length ? <div className="keyword-grid">{keywordCards.map((keyword) => <article className="keyword-card" key={keyword.label}>
            <h3>{keyword.label}</h3>
            <ol>{keyword.sources.map((source) => <li key={source.url}><a href="#source-summary" onClick={(event) => openStoredSummary(source.url, event)}>{sourceTitle(source)}</a></li>)}</ol>
          </article>)}</div> : <p className="hint">No stored source summaries with keywords are available in this workspace yet.</p>}
          <div id="source-summary" className="source-summary-panel" tabIndex={-1} ref={sourceSummaryPanelRef}>
            {selectedSummary && <article className="source-summary">
              <div className="section-heading"><div><p className="eyebrow">Stored source summary</p><h3>{sourceTitle(selectedSummary)}</h3></div><span className="badge">{selectedSummary.chunk_count ?? 0} chunk{selectedSummary.chunk_count === 1 ? "" : "s"}</span></div>
              <p className="source-address">
                <a href={selectedSummary.url} target="_blank" rel="noreferrer">
                  {selectedSummary.url}
                </a>
              </p>
              {selectedSummary.evidence_sufficient === false && <p className="error">The extracted evidence was insufficient for a confident source summary.</p>}
              {selectedSummary.summary.split(/\n{2,}/).map((paragraph, index) => <p key={index}>{paragraph}</p>)}
              {selectedSummary.keywords.length ? <p className="hint">Keywords: {selectedSummary.keywords.join(", ")}</p> : null}
            </article>}
          </div>
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
