import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  ArrowRight,
  BrainCircuit,
  CheckCircle2,
  CircleAlert,
  Database,
  RefreshCw,
  SearchCheck,
  ShieldCheck,
  Store,
} from "lucide-react";

type Health = "checking" | "online" | "offline";

type Preview = {
  status: string;
  customer_text: string;
  message: string;
};

const menu = [
  "Command Center",
  "Demand Studio",
  "Evidence Intelligence",
  "Commerce Optimizer",
  "Merchant Network",
  "Scenario Lab",
  "Business Intelligence",
];

export default function App() {
  const [health, setHealth] = useState<Health>("checking");
  const [request, setRequest] = useState(
    "I need a 65W USB-C PD laptop charger under ₹1000 before 6 PM.",
  );
  const [preview, setPreview] = useState<Preview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function checkHealth() {
    setHealth("checking");

    try {
      const response = await fetch("/api/health", {
        cache: "no-store",
      });

      if (!response.ok) throw new Error("API unavailable");

      const data = await response.json();
      setHealth(data.status === "ok" ? "online" : "offline");
    } catch {
      setHealth("offline");
    }
  }

  useEffect(() => {
    void checkHealth();
  }, []);

  async function submitRequest(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setPreview(null);

    try {
      const response = await fetch("/api/requests/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: request.trim() }),
      });

      if (!response.ok) {
        throw new Error(`Request failed: ${response.status}`);
      }

      const data: Preview = await response.json();
      setPreview(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#080B12] text-slate-100 lg:flex">
      <aside className="border-b border-slate-800/80 bg-[#0D121C] p-6 lg:min-h-screen lg:w-64 lg:shrink-0 lg:border-b-0 lg:border-r">
        <div className="flex items-center gap-3">
          <div className="rounded-xl border border-sky-500/30 bg-sky-500/10 p-2.5 text-sky-400">
            <ShieldCheck size={25} />
          </div>

          <div>
            <h1 className="text-lg font-bold tracking-tight">
              NeedProof<span className="text-sky-400"> AI</span>
            </h1>
            <p className="text-[11px] tracking-wide text-slate-500">
              COMMERCE INTELLIGENCE
            </p>
          </div>
        </div>

        <div className="mt-10 hidden lg:block">
          <p className="mb-4 text-xs font-semibold tracking-wider text-slate-500 uppercase">
            Workspace
          </p>

          <nav className="space-y-1.5">
            {menu.map((item, index) => (
              <div
                key={item}
                className={`rounded-xl px-4 py-3 text-sm ${
                  index === 0
                    ? "border border-sky-500/20 bg-sky-500/10 font-medium text-sky-300"
                    : "text-slate-500"
                }`}
              >
                {item}
                {index !== 0 && (
                  <span className="ml-2 text-[10px] opacity-60">Soon</span>
                )}
              </div>
            ))}
          </nav>
        </div>

        <div className="mt-8 rounded-xl border border-slate-800 bg-slate-900/60 p-4 lg:mt-12">
          <p className="text-xs font-medium text-slate-400">
            Development phase
          </p>
          <p className="mt-2 text-sm font-semibold">Foundation • Chunk 01</p>
          <p className="mt-2 text-xs leading-5 text-slate-500">
            Core intelligence modules will be connected in upcoming chunks.
          </p>
        </div>
      </aside>

      <main className="w-full min-w-0 flex-1">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800/80 px-6 py-5 lg:px-10">
          <div>
            <p className="text-xs text-slate-500">Workspace / Command Center</p>
            <h2 className="mt-1 text-sm font-medium text-slate-200">
              System Overview
            </h2>
          </div>

          <div className="flex items-center gap-3 rounded-full border border-slate-800 bg-slate-900 px-4 py-2 text-xs">
            <span
              className={`h-2 w-2 rounded-full ${
                health === "online"
                  ? "bg-emerald-400"
                  : health === "checking"
                    ? "bg-amber-400"
                    : "bg-rose-400"
              }`}
            />
            <span className="text-slate-300">API {health}</span>
            <button
              type="button"
              onClick={checkHealth}
              aria-label="Check API again"
              className="ml-1 text-slate-500 hover:text-white"
            >
              <RefreshCw size={14} />
            </button>
          </div>
        </header>

        <div className="mx-auto max-w-6xl space-y-8 px-6 py-10 lg:px-10">
          <section className="space-y-5">
            <div className="inline-flex items-center gap-2 rounded-full border border-sky-500/20 bg-sky-500/10 px-3 py-1.5 text-xs font-medium text-sky-300">
              <BrainCircuit size={14} />
              Evidence-driven commerce
            </div>

            <h1 className="max-w-3xl text-4xl font-semibold tracking-tight md:text-5xl">
              Before AI sells,
              <span className="text-sky-400"> it proves.</span>
            </h1>

            <p className="max-w-2xl text-sm leading-7 text-slate-400 md:text-base">
              A commerce intelligence platform designed to investigate
              uncertainty, verify critical evidence and make more reliable
              customer and business decisions.
            </p>
          </section>

          <section className="grid gap-4 md:grid-cols-3">
            <Feature
              icon={<SearchCheck size={21} />}
              title="Evidence Intelligence"
              description="Determine what information needs to be verified and why."
            />
            <Feature
              icon={<Store size={21} />}
              title="Commerce Optimization"
              description="Evaluate customer requirements and merchant economics."
            />
            <Feature
              icon={<ShieldCheck size={21} />}
              title="Verified Commitments"
              description="Prevent unsupported inventory and purchase promises."
            />
          </section>

          <section className="grid gap-5 xl:grid-cols-[1.5fr_1fr]">
            <div className="rounded-2xl border border-slate-800 bg-[#111827] p-6 md:p-8">
              <div className="mb-6 flex items-center gap-3">
                <BrainCircuit className="text-sky-400" size={22} />
                <div>
                  <h2 className="font-semibold">Customer Request Studio</h2>
                  <p className="text-xs text-slate-500">
                    Foundation API test • Gemini not connected yet
                  </p>
                </div>
              </div>

              <form onSubmit={submitRequest}>
                <label
                  htmlFor="customer-request"
                  className="mb-3 block text-sm text-slate-300"
                >
                  Describe what the customer needs
                </label>

                <textarea
                  id="customer-request"
                  value={request}
                  onChange={(event) => setRequest(event.target.value)}
                  rows={5}
                  minLength={8}
                  maxLength={2000}
                  className="w-full resize-y rounded-xl border border-slate-700 bg-[#080B12] p-4 text-sm leading-6 text-slate-200 outline-none focus:border-sky-500"
                  placeholder="Enter a customer shopping request..."
                  required
                />

                <button
                  type="submit"
                  disabled={loading || health !== "online"}
                  className="mt-4 inline-flex items-center gap-2 rounded-xl bg-sky-500 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-sky-400 disabled:opacity-40"
                >
                  {loading ? "Submitting..." : "Send to Python API"}
                  <ArrowRight size={16} />
                </button>
              </form>

              {error && (
                <div className="mt-5 flex items-center gap-2 rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
                  <CircleAlert size={18} />
                  {error}
                </div>
              )}

              {preview && (
                <div className="mt-6 rounded-xl border border-emerald-500/25 bg-emerald-500/5 p-5">
                  <div className="flex items-center gap-2 text-sm font-semibold text-emerald-400">
                    <CheckCircle2 size={18} />
                    Request received successfully
                  </div>

                  <p className="mt-3 text-sm text-slate-300">
                    {preview.customer_text}
                  </p>

                  <p className="mt-3 text-xs leading-5 text-slate-500">
                    {preview.message}
                  </p>
                </div>
              )}
            </div>

            <div className="rounded-2xl border border-slate-800 bg-[#111827] p-6">
              <div className="flex items-center gap-3">
                <Database className="text-sky-400" size={21} />
                <h2 className="font-semibold">System Readiness</h2>
              </div>

              <div className="mt-7 space-y-5">
                <Status
                  title="React frontend"
                  detail="Vite development application"
                  ready
                />
                <Status
                  title="Python API"
                  detail="FastAPI service connectivity"
                  ready={health === "online"}
                />
                <Status
                  title="Gemini on Vertex AI"
                  detail="Scheduled for Chunk 02"
                />
                <Status
                  title="Cloud database"
                  detail="Scheduled for Chunk 03"
                />
                <Status
                  title="Evidence decision engine"
                  detail="Scheduled for Chunk 04"
                />
              </div>

              <div className="mt-8 rounded-xl border border-slate-700/70 bg-slate-900/60 p-4">
                <p className="text-xs leading-5 text-slate-400">
                  Only verified, implemented components are shown as ready.
                  Business analytics will be added after persistent data and
                  decision engines are connected.
                </p>
              </div>
            </div>
          </section>

          <footer className="pt-2 text-center text-xs text-slate-600">
            NeedProof AI • Retail & Commerce • Development Foundation
          </footer>
        </div>
      </main>
    </div>
  );
}

function Feature({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-800 bg-[#111827] p-6">
      <div className="mb-5 inline-flex rounded-xl bg-sky-500/10 p-3 text-sky-400">
        {icon}
      </div>
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="mt-2 text-sm leading-6 text-slate-400">{description}</p>
    </div>
  );
}

function Status({
  title,
  detail,
  ready = false,
}: {
  title: string;
  detail: string;
  ready?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div>
        <p className="text-sm font-medium text-slate-200">{title}</p>
        <p className="mt-1 text-xs text-slate-500">{detail}</p>
      </div>

      {ready ? (
        <CheckCircle2 className="shrink-0 text-emerald-400" size={18} />
      ) : (
        <span className="shrink-0 rounded-full bg-slate-800 px-2 py-1 text-[10px] text-slate-400">
          Pending
        </span>
      )}
    </div>
  );
}
