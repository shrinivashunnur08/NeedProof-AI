import { useEffect, useState, type FormEvent } from "react";
import {
  ClipboardCheck,
  History,
  RefreshCw,
  ShieldAlert,
  X,
} from "lucide-react";
import TechnicalReviewPanel from "./TechnicalReviewPanel";
type CheckType = "IDENTITY" | "STOCK" | "PRICE";

type SourceType = "DIRECTORY_CALLBACK" | "AUTHORIZED_POS_EXPORT";

type Finding = "CORROBORATES" | "CONTRADICTS" | "INCONCLUSIVE";

interface Observation {
  id: number;
  check_type: CheckType;
  source_type: SourceType;
  finding: Finding;
  reviewer_note: string;
  recorded_at: string;
}

interface AssuranceResult {
  mode: "OPERATOR_ASSURANCE_REVIEW";
  case_id: number;
  request_id: number;
  place_id: string;
  product_query: string;
  reported_product: string;
  report_age_minutes: number;
  report_freshness: string;
  status: string;
  field_status: Record<string, string>;
  observations: Observation[];
  recommended_next_action: {
    code: string;
    label: string;
  };
  purchase_allowed: false;
  independently_authenticated_merchant: false;
  notice: string;
}

function readable(value: string) {
  return value.replaceAll("_", " ");
}

export default function AssuranceDeskModal({
  onClose,
}: {
  onClose: () => void;
}) {
  const [link, setLink] = useState("");
  const [operatorKey, setOperatorKey] = useState("");

  const [caseData, setCaseData] = useState<AssuranceResult | null>(null);

  const [checkType, setCheckType] = useState<CheckType>("IDENTITY");

  const [sourceType, setSourceType] =
    useState<SourceType>("DIRECTORY_CALLBACK");

  const [finding, setFinding] = useState<Finding>("INCONCLUSIVE");

  const [note, setNote] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }

    window.addEventListener("keydown", onKeyDown);

    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  function parseInvitation() {
    const url = new URL(link.trim());

    if (url.origin !== window.location.origin) {
      throw new Error(
        "Use an invitation link from this local NeedProof application.",
      );
    }

    const match = url.pathname.match(/^\/verify\/(\d+)\/?$/);
    const token = decodeURIComponent(url.hash.slice(1));

    if (!match || token.length < 20) {
      throw new Error("Invalid verification invitation link.");
    }

    return {
      request_id: Number(match[1]),
      invitation_token: token,
    };
  }

  async function readJson(response: Response) {
    const raw = await response.text();

    if (!response.ok) {
      let message = `Request failed (HTTP ${response.status})`;

      try {
        const body = JSON.parse(raw);

        if (typeof body.detail === "string") {
          message = body.detail;
        }
      } catch {
        // Keep the safe HTTP error message.
      }

      throw new Error(message);
    }

    if (!raw.trim()) {
      throw new Error("The assurance API returned no data.");
    }

    return JSON.parse(raw) as AssuranceResult;
  }

  async function openCase(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setCaseData(null);

    try {
      if (!operatorKey.trim()) {
        throw new Error("Enter your local assurance operator key.");
      }

      const reference = parseInvitation();

      const response = await fetch("/api/assurance/cases", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Assurance-Key": operatorKey,
        },
        cache: "no-store",
        body: JSON.stringify(reference),
      });

      const data = await readJson(response);

      if (data.mode !== "OPERATOR_ASSURANCE_REVIEW") {
        throw new Error("Unexpected assurance API response.");
      }

      setCaseData(data);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to open assurance case.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function refreshCase(caseId: number) {
    setLoading(true);
    setError("");

    try {
      const response = await fetch(`/api/assurance/cases/${caseId}`, {
        headers: {
          "X-Assurance-Key": operatorKey,
        },
        cache: "no-store",
      });

      setCaseData(await readJson(response));
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to refresh assurance case.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function saveObservation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!caseData) return;

    setLoading(true);
    setError("");

    try {
      const response = await fetch(
        `/api/assurance/cases/${caseData.case_id}/observations`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Assurance-Key": operatorKey,
          },
          cache: "no-store",
          body: JSON.stringify({
            check_type: checkType,
            source_type: sourceType,
            finding,
            reviewer_note: note.trim(),
          }),
        },
      );

      const data = await readJson(response);

      setCaseData(data);
      setNote("");
      setFinding("INCONCLUSIVE");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to record observation.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/85 p-3 text-slate-100 backdrop-blur-sm">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="assurance-title"
        className="flex max-h-[92dvh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-[#304058] bg-[#111827] shadow-2xl"
      >
        <header className="flex shrink-0 items-center justify-between border-b border-slate-800 px-5 py-4">
          <div className="flex items-center gap-3">
            <ClipboardCheck size={23} className="text-sky-400" />

            <div>
              <h2 id="assurance-title" className="text-lg font-semibold">
                Merchant Assurance Desk
              </h2>

              <p className="text-xs text-slate-400">
                Local operator attestations · Evidence audit history
              </p>
            </div>
          </div>

          <button
            type="button"
            aria-label="Close Assurance Desk"
            onClick={onClose}
            className="rounded-lg border border-slate-700 p-2 hover:bg-slate-800"
          >
            <X size={18} />
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          <form
            onSubmit={openCase}
            className="grid gap-3 rounded-xl border border-slate-700 bg-[#0A101B] p-4 md:grid-cols-[1fr_220px_auto]"
          >
            <label className="min-w-0 text-xs text-slate-400">
              Private merchant invitation link
              <input
                type="text"
                required
                value={link}
                onChange={(event) => setLink(event.target.value)}
                placeholder="http://localhost:5173/verify/..."
                className="mt-2 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-xs text-white"
              />
            </label>

            <label className="text-xs text-slate-400">
              Local operator key
              <input
                type="password"
                required
                value={operatorKey}
                onChange={(event) => setOperatorKey(event.target.value)}
                autoComplete="off"
                className="mt-2 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-xs text-white"
              />
            </label>

            <button
              type="submit"
              disabled={loading}
              className="self-end rounded-lg bg-sky-500 px-4 py-2.5 text-sm font-semibold text-slate-950 disabled:opacity-50"
            >
              {loading ? "Loading..." : "Open Case"}
            </button>
          </form>

          {error && (
            <div
              role="alert"
              className="mt-4 rounded-xl border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-300"
            >
              {error}
            </div>
          )}

          {!caseData && !error && (
            <div className="py-12 text-center text-sm text-slate-400">
              Open an existing verification submission to begin an operator
              assurance review.
            </div>
          )}

          {caseData && (
            <div className="mt-5 grid gap-5 lg:grid-cols-[1fr_1fr]">
              <div className="lg:col-span-2">
                <TechnicalReviewPanel
                  caseId={caseData.case_id}
                  operatorKey={operatorKey}
                  hasConflict={caseData.status === "CONFLICT_RECORDED"}
                />
              </div>
              <div className="space-y-4">
                <div className="rounded-xl border border-sky-500/25 bg-sky-500/5 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="text-sm font-semibold">
                      Assurance case #{caseData.case_id}
                    </h3>

                    <button
                      type="button"
                      disabled={loading}
                      onClick={() => void refreshCase(caseData.case_id)}
                      className="rounded-lg border border-slate-700 p-2 hover:bg-slate-800"
                      aria-label="Refresh assurance case"
                    >
                      <RefreshCw size={15} />
                    </button>
                  </div>

                  <p className="mt-2 text-xs text-slate-400">
                    {caseData.product_query}
                  </p>

                  <p className="mt-2 text-xs text-slate-400">
                    Status:{" "}
                    <span className="font-semibold text-amber-300">
                      {readable(caseData.status)}
                    </span>
                  </p>

                  <p className="mt-1 text-xs text-slate-500">
                    Report age: {caseData.report_age_minutes} min
                  </p>
                </div>

                <div className="rounded-xl border border-slate-700 bg-[#0A101B] p-4">
                  <h3 className="text-sm font-semibold">Evidence assessment</h3>

                  <div className="mt-3 space-y-3">
                    {Object.entries(caseData.field_status).map(
                      ([field, status]) => (
                        <div
                          key={field}
                          className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-2 text-xs"
                        >
                          <span className="text-slate-400">
                            {readable(field)}
                          </span>

                          <span className="font-semibold text-amber-300">
                            {readable(status)}
                          </span>
                        </div>
                      ),
                    )}
                  </div>
                </div>

                <div className="rounded-xl border border-sky-500/20 bg-sky-500/5 p-4">
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-sky-400">
                    Recommended next action
                  </p>

                  <p className="mt-2 text-sm font-medium">
                    {caseData.recommended_next_action.label}
                  </p>
                </div>

                <div className="flex items-start gap-2 rounded-xl border border-amber-500/20 bg-amber-500/5 p-4 text-xs leading-5 text-amber-200">
                  <ShieldAlert size={17} className="shrink-0" />

                  <div>
                    <p className="font-semibold">Purchase not authorized</p>

                    <p className="mt-1 text-slate-400">
                      Operator attestations are not independently authenticated
                      merchant evidence. Compatibility and delivery still
                      require verification.
                    </p>
                  </div>
                </div>
              </div>

              <div className="space-y-4">
                <form
                  onSubmit={saveObservation}
                  className="space-y-4 rounded-xl border border-slate-700 bg-[#0A101B] p-4"
                >
                  <h3 className="text-sm font-semibold">
                    Record a review observation
                  </h3>

                  <label className="block text-xs text-slate-400">
                    What was checked?
                    <select
                      value={checkType}
                      onChange={(event) => {
                        const next = event.target.value as CheckType;

                        setCheckType(next);

                        setSourceType("DIRECTORY_CALLBACK");
                      }}
                      className="mt-2 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"
                    >
                      <option value="IDENTITY">Merchant identity</option>
                      <option value="STOCK">Stock quantity</option>
                      <option value="PRICE">Selling price</option>
                    </select>
                  </label>

                  <label className="block text-xs text-slate-400">
                    Evidence channel
                    <select
                      value={sourceType}
                      onChange={(event) =>
                        setSourceType(event.target.value as SourceType)
                      }
                      className="mt-2 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"
                    >
                      <option value="DIRECTORY_CALLBACK">
                        Independently sourced callback
                      </option>

                      {checkType !== "IDENTITY" && (
                        <option value="AUTHORIZED_POS_EXPORT">
                          Authorized POS export
                        </option>
                      )}
                    </select>
                  </label>

                  <label className="block text-xs text-slate-400">
                    Observation
                    <select
                      value={finding}
                      onChange={(event) =>
                        setFinding(event.target.value as Finding)
                      }
                      className="mt-2 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"
                    >
                      <option value="INCONCLUSIVE">Inconclusive</option>
                      <option value="CORROBORATES">
                        Supports the submitted claim
                      </option>
                      <option value="CONTRADICTS">
                        Contradicts the submitted claim
                      </option>
                    </select>
                  </label>

                  <label className="block text-xs text-slate-400">
                    Review note
                    <textarea
                      required
                      minLength={12}
                      maxLength={600}
                      rows={3}
                      value={note}
                      onChange={(event) => setNote(event.target.value)}
                      placeholder="Record what was checked. Don't include personal contact details or secrets."
                      className="mt-2 w-full resize-none rounded-lg border border-slate-700 bg-[#080D17] p-3 text-sm"
                    />
                  </label>

                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full rounded-lg bg-sky-500 px-4 py-3 text-sm font-semibold text-slate-950 disabled:opacity-50"
                  >
                    {loading ? "Recording..." : "Record Observation"}
                  </button>
                </form>

                <div className="rounded-xl border border-slate-700 bg-[#0A101B] p-4">
                  <h3 className="flex items-center gap-2 text-sm font-semibold">
                    <History size={16} className="text-sky-400" />
                    Review history
                  </h3>

                  {caseData.observations.length === 0 ? (
                    <p className="mt-3 text-xs text-slate-500">
                      No review observations recorded.
                    </p>
                  ) : (
                    <div className="mt-3 space-y-3">
                      {caseData.observations.map((observation) => (
                        <article
                          key={observation.id}
                          className="rounded-lg border border-slate-800 p-3"
                        >
                          <p className="text-xs font-semibold">
                            {readable(observation.check_type)}
                            {" · "}
                            {readable(observation.finding)}
                          </p>

                          <p className="mt-1 text-xs text-slate-400">
                            {readable(observation.source_type)}
                          </p>

                          <p className="mt-2 text-xs leading-5 text-slate-300">
                            {observation.reviewer_note}
                          </p>

                          <p className="mt-2 text-[11px] text-slate-500">
                            {new Date(observation.recorded_at).toLocaleString()}
                          </p>
                        </article>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>

        <footer className="shrink-0 border-t border-slate-800 px-5 py-3 text-[11px] text-slate-500">
          NeedProof AI · Local operator review · No purchase, payment or stock
          reservation
        </footer>
      </section>
    </div>
  );
}
