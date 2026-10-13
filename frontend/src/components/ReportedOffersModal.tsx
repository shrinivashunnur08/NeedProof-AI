import { useEffect, useState, type FormEvent } from "react";
import { BarChart3, Plus, ShieldAlert, Trash2, X } from "lucide-react";

interface InvitationRef {
  request_id: number;
  invitation_token: string;
}

interface ReportedOffer {
  request_id: number;
  place_id: string;
  product_name: string | null;
  price_minor: number | null;
  stock_quantity: number | null;
  report_age_minutes: number | null;
  delivery_available: boolean | null;
  warnings: string[];
  purchase_eligible: false;
  reported_item_subtotal_minor?: number;
}

interface ExcludedOffer extends ReportedOffer {
  reasons: string[];
}

interface AdvisoryResult {
  mode: "REAL_REPORTED_ADVISORY";
  status: string;
  target_product: string;
  purchase_allowed: false;
  selected: ReportedOffer | null;
  alternatives: ReportedOffer[];
  excluded: ExcludedOffer[];
  budget_minor: number;
  quantity: number;
  total_including_fees_minor: null;
  notice: string;
}

interface Props {
  onClose: () => void;
  initialInvitations?: InvitationRef[];
  merchantLabels?: Record<string, string>;
}

function money(minor: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
  }).format(minor / 100);
}

function readable(value: string) {
  return value.replaceAll("_", " ").toLowerCase();
}

export default function ReportedOffersModal({
  onClose,
  initialInvitations = [],
  merchantLabels = {},
}: Props) {
  const [invitations, setInvitations] = useState<InvitationRef[]>(() => [
    ...initialInvitations,
  ]);

  const [linkInput, setLinkInput] = useState("");
  const [budget, setBudget] = useState(1000);
  const [quantity, setQuantity] = useState(1);
  const [deliveryRequired, setDeliveryRequired] = useState(true);

  const [result, setResult] = useState<AdvisoryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    function onEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }

    window.addEventListener("keydown", onEscape);
    return () => window.removeEventListener("keydown", onEscape);
  }, [onClose]);

  function merchantName(placeId: string) {
    return merchantLabels[placeId] || `Place ID: ${placeId}`;
  }

  function addInvitation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    try {
      const url = new URL(linkInput.trim());

      // Local development invitations only.
      if (
        !["localhost", "127.0.0.1"].includes(url.hostname) ||
        url.port !== window.location.port
      ) {
        throw new Error(
          "Paste a NeedProof invitation link from your local app.",
        );
      }

      const match = url.pathname.match(/^\/verify\/(\d+)\/?$/);
      const token = decodeURIComponent(url.hash.slice(1));

      if (!match || token.length < 20) {
        throw new Error("Invalid verification invitation link.");
      }

      const requestId = Number(match[1]);

      if (invitations.some((item) => item.request_id === requestId)) {
        throw new Error("This invitation is already added.");
      }

      if (invitations.length >= 12) {
        throw new Error("Maximum 12 invitations per analysis.");
      }

      setInvitations((previous) => [
        ...previous,
        {
          request_id: requestId,
          invitation_token: token,
        },
      ]);

      setLinkInput("");
      setResult(null);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not read invitation link.",
      );
    }
  }

  async function compare(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setResult(null);

    if (!invitations.length) {
      setError("Add at least one invitation.");
      return;
    }

    setLoading(true);

    try {
      const response = await fetch("/api/optimization/reported-offers", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        cache: "no-store",
        body: JSON.stringify({
          budget_inr: budget,
          quantity,
          delivery_required: deliveryRequired,
          invitations,
        }),
      });

      const raw = await response.text();

      if (!response.ok) {
        throw new Error(
          `Advisory API returned HTTP ${response.status}: ` + raw.slice(0, 160),
        );
      }

      if (!raw.trim()) {
        throw new Error("Advisory API returned an empty response.");
      }

      const data = JSON.parse(raw) as AdvisoryResult;

      if (data.mode !== "REAL_REPORTED_ADVISORY") {
        throw new Error("Unexpected advisory response.");
      }

      setResult(data);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not compare reported offers.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/85 p-3 text-slate-100 backdrop-blur-sm">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="advisory-title"
        className="flex max-h-[91dvh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-[#304058] bg-[#111827]"
      >
        <header className="flex shrink-0 items-center justify-between border-b border-slate-800 px-5 py-4">
          <div className="flex items-center gap-3">
            <BarChart3 size={22} className="text-sky-400" />
            <div>
              <h2 id="advisory-title" className="font-semibold">
                Compare Reported Offers
              </h2>
              <p className="text-xs text-slate-400">
                Real database submissions · Advisory only
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            aria-label="Close advisory"
            className="rounded-lg border border-slate-700 p-2"
          >
            <X size={18} />
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          <div className="grid gap-5 lg:grid-cols-[310px_minmax(0,1fr)]">
            <div className="space-y-5">
              <div className="rounded-xl border border-slate-700 bg-[#0A101B] p-4">
                <h3 className="text-sm font-semibold">
                  Private verification invitations
                </h3>

                <p className="mt-2 text-xs leading-5 text-slate-400">
                  Compare submissions created for the same product request.
                  Invitation links remain in browser memory during this session.
                </p>

                <form onSubmit={addInvitation} className="mt-4 space-y-2">
                  <label className="block text-xs text-slate-400">
                    Paste an existing invitation link
                  </label>

                  <input
                    type="text"
                    value={linkInput}
                    onChange={(event) => setLinkInput(event.target.value)}
                    placeholder="http://localhost:5173/verify/..."
                    className="w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-xs outline-none focus:border-sky-500"
                  />

                  <button
                    type="submit"
                    className="flex items-center gap-2 rounded-lg border border-sky-500/30 px-3 py-2 text-xs text-sky-300"
                  >
                    <Plus size={14} />
                    Add invitation
                  </button>
                </form>

                <div className="mt-4 space-y-2">
                  {invitations.map((invitation) => (
                    <div
                      key={invitation.request_id}
                      className="flex items-center justify-between rounded-lg border border-slate-800 p-2 text-xs"
                    >
                      <span>Request #{invitation.request_id}</span>

                      <button
                        type="button"
                        aria-label={`Remove request ${invitation.request_id}`}
                        onClick={() => {
                          setInvitations((previous) =>
                            previous.filter(
                              (item) =>
                                item.request_id !== invitation.request_id,
                            ),
                          );
                          setResult(null);
                        }}
                        className="text-slate-400 hover:text-rose-300"
                      >
                        <Trash2 size={15} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>

              <form
                onSubmit={compare}
                className="space-y-4 rounded-xl border border-slate-700 bg-[#0A101B] p-4"
              >
                <h3 className="text-sm font-semibold">Advisory constraints</h3>

                <label className="block text-xs text-slate-400">
                  Budget (₹)
                  <input
                    type="number"
                    min={1}
                    max={1000000}
                    required
                    value={budget}
                    onChange={(e) => setBudget(Number(e.target.value))}
                    className="mt-2 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"
                  />
                </label>

                <label className="block text-xs text-slate-400">
                  Required quantity
                  <input
                    type="number"
                    min={1}
                    max={100}
                    required
                    value={quantity}
                    onChange={(e) => setQuantity(Number(e.target.value))}
                    className="mt-2 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"
                  />
                </label>

                <label className="flex items-center gap-2 text-xs text-slate-300">
                  <input
                    type="checkbox"
                    checked={deliveryRequired}
                    onChange={(e) => setDeliveryRequired(e.target.checked)}
                  />
                  Delivery required
                </label>

                <button
                  type="submit"
                  disabled={loading || invitations.length === 0}
                  className="w-full rounded-lg bg-sky-500 px-4 py-3 text-sm font-semibold text-slate-950 disabled:opacity-40"
                >
                  {loading ? "Comparing reports..." : "Compare Reported Offers"}
                </button>
              </form>
            </div>

            <div className="min-w-0 space-y-4">
              {error && (
                <div
                  role="alert"
                  className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300"
                >
                  {error}
                </div>
              )}

              {!result && !error && (
                <div className="flex min-h-52 items-center justify-center rounded-xl border border-slate-800 bg-[#0A101B] p-5 text-center text-sm text-slate-400">
                  Add invitation links and run the advisory comparison. Only
                  submitted merchant claims are considered.
                </div>
              )}

              {result && (
                <>
                  <div className="rounded-xl border border-sky-500/25 bg-sky-500/5 p-4">
                    <p className="text-[11px] font-semibold uppercase text-sky-400">
                      Advisory result
                    </p>

                    <h3 className="mt-2 text-lg font-semibold">
                      {result.selected
                        ? "Lowest comparable reported item price"
                        : "No comparable reported offer"}
                    </h3>

                    <p className="mt-1 text-xs text-slate-400">
                      Requested: {result.target_product}
                    </p>

                    {result.selected && (
                      <div className="mt-4">
                        <p className="text-sm font-semibold">
                          {merchantName(result.selected.place_id)}
                        </p>

                        <p className="mt-2 text-2xl font-semibold text-sky-300">
                          {money(
                            result.selected.reported_item_subtotal_minor ??
                              result.selected.price_minor ??
                              0,
                          )}
                        </p>

                        <p className="mt-1 text-xs text-slate-400">
                          Reported item subtotal for {result.quantity} unit(s),
                          excluding unknown additional charges
                        </p>

                        <p className="mt-3 text-xs text-amber-300">
                          Unverified merchant report — not purchase eligible
                        </p>
                      </div>
                    )}
                  </div>

                  {result.selected && (
                    <div className="rounded-xl border border-slate-700 bg-[#0A101B] p-4">
                      <h3 className="text-sm font-semibold">
                        What still needs verification?
                      </h3>

                      <div className="mt-3 space-y-2">
                        {result.selected.warnings.map((warning) => (
                          <p
                            key={warning}
                            className="text-xs leading-5 text-amber-300"
                          >
                            • {readable(warning)}
                          </p>
                        ))}
                      </div>
                    </div>
                  )}

                  <div className="rounded-xl border border-slate-700 bg-[#0A101B] p-4">
                    <h3 className="text-sm font-semibold">
                      Other comparable reports
                    </h3>

                    {result.alternatives.length === 0 ? (
                      <p className="mt-2 text-xs text-slate-500">
                        No additional comparable reports.
                      </p>
                    ) : (
                      <div className="mt-3 space-y-3">
                        {result.alternatives.map((offer) => (
                          <div
                            key={offer.request_id}
                            className="flex items-start justify-between gap-3 border-b border-slate-800 pb-3 text-xs"
                          >
                            <span>{merchantName(offer.place_id)}</span>
                            <span className="font-semibold">
                              {offer.price_minor !== null
                                ? money(offer.price_minor * result.quantity)
                                : "No price"}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {result.excluded.length > 0 && (
                    <div className="rounded-xl border border-slate-700 bg-[#0A101B] p-4">
                      <h3 className="text-sm font-semibold">
                        Excluded reports
                      </h3>

                      {result.excluded.map((offer) => (
                        <div
                          key={offer.request_id}
                          className="mt-3 border-t border-slate-800 pt-3"
                        >
                          <p className="text-xs font-medium">
                            {merchantName(offer.place_id)}
                          </p>

                          <p className="mt-1 text-xs leading-5 text-amber-300">
                            {offer.reasons.map(readable).join(", ")}
                          </p>
                        </div>
                      ))}
                    </div>
                  )}

                  <div className="rounded-xl border border-amber-500/25 bg-amber-500/5 p-4">
                    <p className="flex items-center gap-2 text-xs font-semibold text-amber-300">
                      <ShieldAlert size={15} />
                      Not authorized for purchase
                    </p>

                    <p className="mt-2 text-xs leading-5 text-slate-400">
                      {result.notice}
                    </p>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
