import { useEffect, useState, type FormEvent } from "react";
import { CheckCircle2, ShieldAlert, Store } from "lucide-react";

interface Props {
  requestId: number;
  token: string;
}

interface RequestInfo {
  product_query: string;
  status: string;
  expires_at: string;
  notice: string;
}

export default function MerchantVerificationPage({ requestId, token }: Props) {
  const [info, setInfo] = useState<RequestInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [completed, setCompleted] = useState(false);
  const [error, setError] = useState("");

  const [productName, setProductName] = useState("");
  const [stock, setStock] = useState("0");
  const [price, setPrice] = useState("");
  const [specifications, setSpecifications] = useState("");
  const [delivery, setDelivery] = useState("unknown");
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    async function loadRequest() {
      try {
        if (!token) {
          throw new Error("Invitation token is missing.");
        }

        const response = await fetch(
          `/api/verification/requests/${requestId}`,
          {
            headers: { "X-Verification-Token": token },
            signal: controller.signal,
            cache: "no-store",
          },
        );

        const data = await response.json();

        if (!response.ok) {
          throw new Error(data.detail ?? "Invalid invitation");
        }

        setInfo(data);

        if (data.status !== "AWAITING_RESPONSE") {
          setError(
            data.status === "EXPIRED"
              ? "This invitation has expired."
              : "This invitation is no longer accepting responses.",
          );
        }
      } catch (err) {
        if (!controller.signal.aborted) {
          setError(
            err instanceof Error ? err.message : "Unable to load request",
          );
        }
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }

    void loadRequest();

    return () => controller.abort();
  }, [requestId, token]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    setError("");

    const stockNumber = Number(stock);

    if (!Number.isInteger(stockNumber) || stockNumber < 0) {
      setError("Enter a valid nonnegative stock quantity.");
      return;
    }

    const amount = price.trim();

    if (amount && !/^\d+(\.\d{1,2})?$/.test(amount)) {
      setError("Enter a valid price with at most two decimal places.");
      return;
    }

    const [whole, fraction = ""] = amount.split(".");

    const priceMinor = amount
      ? Number(whole) * 100 + Number(fraction.padEnd(2, "0"))
      : null;

    if (stockNumber > 0 && (!priceMinor || priceMinor <= 0)) {
      setError("Enter a selling price for available stock.");
      return;
    }

    setSaving(true);

    try {
      const response = await fetch(
        `/api/verification/requests/${requestId}/respond`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Verification-Token": token,
          },
          body: JSON.stringify({
            product_name: productName.trim(),
            stock_quantity: stockNumber,
            price_minor: priceMinor,
            specification_notes: specifications || null,
            delivery_available:
              delivery === "yes" ? true : delivery === "no" ? false : null,
            authorized_to_respond: authorized,
          }),
        },
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Submission failed. Please check the entered information.",
        );
      }

      setCompleted(true);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to submit evidence",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <main className="flex min-h-dvh items-center justify-center bg-[#080B12] p-4 text-slate-100">
      <section className="w-full max-w-2xl rounded-2xl border border-slate-700 bg-[#111827] p-5 shadow-2xl md:p-7">
        <div className="mb-5 flex items-center gap-3">
          <div className="rounded-xl bg-sky-500/10 p-3 text-sky-400">
            <Store size={24} />
          </div>
          <div>
            <h1 className="text-xl font-semibold">NeedProof AI</h1>
            <p className="text-xs text-slate-400">
              Merchant product verification
            </p>
          </div>
        </div>

        {loading ? (
          <p className="text-sm text-slate-400">
            Loading your verification invitation...
          </p>
        ) : completed ? (
          <div className="rounded-xl border border-emerald-500/25 bg-emerald-500/10 p-5">
            <CheckCircle2 size={28} className="mb-3 text-emerald-400" />
            <h2 className="font-semibold">Product information submitted</h2>
            <p className="mt-2 text-sm leading-6 text-slate-300">
              Your information has been recorded. NeedProof will treat it as
              merchant-reported evidence, not independently verified inventory.
            </p>
          </div>
        ) : (
          <>
            {info && (
              <div className="mb-5 rounded-xl border border-slate-700 bg-[#080D17] p-4">
                <p className="text-xs text-slate-500">Requested product</p>
                <p className="mt-1 text-sm font-semibold">
                  {info.product_query}
                </p>
                <p className="mt-2 text-xs text-slate-400">
                  Request #{requestId}
                </p>
              </div>
            )}

            {error && (
              <div
                role="alert"
                className="mb-4 rounded-lg border border-rose-500/25 bg-rose-500/10 p-3 text-sm text-rose-300"
              >
                {error}
              </div>
            )}

            {info?.status === "AWAITING_RESPONSE" && (
              <form onSubmit={submit} className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <label className="sm:col-span-2">
                    <span className="mb-2 block text-xs text-slate-400">
                      Product name or availability response
                    </span>
                    <input
                      required
                      minLength={2}
                      maxLength={200}
                      value={productName}
                      onChange={(e) => setProductName(e.target.value)}
                      placeholder="e.g. 65W USB-C PD Charger"
                      className="w-full rounded-lg border border-slate-700 bg-[#080D17] p-3 text-sm outline-none focus:border-sky-500"
                    />
                  </label>

                  <label>
                    <span className="mb-2 block text-xs text-slate-400">
                      Available units
                    </span>
                    <input
                      required
                      type="number"
                      min="0"
                      step="1"
                      value={stock}
                      onChange={(e) => setStock(e.target.value)}
                      className="w-full rounded-lg border border-slate-700 bg-[#080D17] p-3 text-sm outline-none focus:border-sky-500"
                    />
                  </label>

                  <label>
                    <span className="mb-2 block text-xs text-slate-400">
                      Selling price (₹)
                    </span>
                    <input
                      type="number"
                      min="0.01"
                      step="0.01"
                      value={price}
                      onChange={(e) => setPrice(e.target.value)}
                      placeholder="899.00"
                      className="w-full rounded-lg border border-slate-700 bg-[#080D17] p-3 text-sm outline-none focus:border-sky-500"
                    />
                  </label>
                </div>

                <label className="block">
                  <span className="mb-2 block text-xs text-slate-400">
                    Product specifications
                  </span>
                  <textarea
                    rows={2}
                    maxLength={2000}
                    value={specifications}
                    onChange={(e) => setSpecifications(e.target.value)}
                    placeholder="e.g. USB-C PD, 65W, supported voltage profiles"
                    className="w-full resize-none rounded-lg border border-slate-700 bg-[#080D17] p-3 text-sm outline-none focus:border-sky-500"
                  />
                </label>

                <label className="block">
                  <span className="mb-2 block text-xs text-slate-400">
                    Can you fulfill the customer's deadline?
                  </span>
                  <select
                    value={delivery}
                    onChange={(e) => setDelivery(e.target.value)}
                    className="w-full rounded-lg border border-slate-700 bg-[#080D17] p-3 text-sm"
                  >
                    <option value="unknown">Not confirmed</option>
                    <option value="yes">Yes, subject to terms</option>
                    <option value="no">No</option>
                  </select>
                </label>

                <label className="flex items-start gap-3 text-xs leading-5 text-slate-300">
                  <input
                    type="checkbox"
                    required
                    checked={authorized}
                    onChange={(e) => setAuthorized(e.target.checked)}
                    className="mt-1"
                  />
                  I confirm that I am authorized to provide this product and
                  inventory information on behalf of the participating business.
                </label>

                <button
                  type="submit"
                  disabled={saving || !authorized}
                  className="w-full rounded-xl bg-sky-500 p-3 text-sm font-semibold text-slate-950 hover:bg-sky-400 disabled:opacity-40"
                >
                  {saving
                    ? "Submitting information..."
                    : "Submit Product Information"}
                </button>
              </form>
            )}
          </>
        )}

        <div className="mt-5 flex items-start gap-2 border-t border-slate-800 pt-4 text-xs leading-5 text-slate-500">
          <ShieldAlert size={16} className="mt-0.5 shrink-0" />
          Only respond if you represent the business and have permission to
          share these details. Submitted information does not automatically
          become independently verified.
        </div>
      </section>
    </main>
  );
}
