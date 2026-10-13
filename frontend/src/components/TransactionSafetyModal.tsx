import { useEffect, useState } from "react";
import {
  Clock3,
  PackageCheck,
  RefreshCw,
  RotateCcw,
  ShieldCheck,
  X,
} from "lucide-react";

interface Scenario {
  budget_inr: number;
  deadline_minutes: number;
  max_merchants: number;
  ttl_seconds: number;
}

interface StockItem {
  sku: string;
  initial_quantity: number;
  available_quantity: number;
}

interface OrderEvent {
  id: number;
  type: string;
  recorded_at: string;
}

interface SimulatedOrder {
  mode: "SYNTHETIC_TRANSACTION";
  order_id: number;
  status: string;
  created_at: string;
  expires_at: string;
  plan: {
    selected_offers: {
      sku: string;
      item_name: string;
      merchant: string;
      quantity: number;
      line_total_minor: number;
    }[];
    totals: {
      total_minor: number;
      remaining_minor: number;
    };
  };
  events: OrderEvent[];
  payment_executed: false;
  real_merchant_inventory_reserved: false;
  notice: string;
}

const NORMAL: Scenario = {
  budget_inr: 1800,
  deadline_minutes: 60,
  max_merchants: 2,
  ttl_seconds: 120,
};

const API = "/api/transactions/simulation";

function rupees(minor: number) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
  }).format(minor / 100);
}

async function readApi(response: Response) {
  const raw = await response.text();

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;

    try {
      const parsed = JSON.parse(raw);
      if (typeof parsed.detail === "string") {
        detail = parsed.detail;
      }
    } catch {
      // Keep the HTTP error.
    }

    throw new Error(detail);
  }

  if (!raw.trim()) {
    throw new Error("The transaction API returned no data.");
  }

  return JSON.parse(raw);
}

export default function TransactionSafetyModal({
  onClose,
}: {
  onClose: () => void;
}) {
  const [scenario, setScenario] = useState<Scenario>(NORMAL);

  const [idempotencyKey, setIdempotencyKey] = useState(() =>
    crypto.randomUUID(),
  );

  const [order, setOrder] = useState<SimulatedOrder | null>(null);

  const [inventory, setInventory] = useState<StockItem[]>([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  const active = order?.status === "RESERVED";

  async function refreshInventory() {
    const data = await readApi(
      await fetch(`${API}/inventory`, {
        cache: "no-store",
      }),
    );

    setInventory(data.items as StockItem[]);
  }

  useEffect(() => {
    void refreshInventory().catch((err) => {
      setError(
        err instanceof Error ? err.message : "Could not load demo inventory.",
      );
    });
  }, []);

  function newScenario(next: Scenario = NORMAL) {
    if (active) {
      setError(
        "Commit or cancel the current reservation before " +
          "starting another scenario.",
      );
      return;
    }

    setScenario({ ...next });
    setOrder(null);
    setIdempotencyKey(crypto.randomUUID());
    setError("");
    setMessage("");
  }

  async function reserve() {
    setLoading(true);
    setError("");
    setMessage("");

    try {
      const data = await readApi(
        await fetch(`${API}/reserve`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": idempotencyKey,
          },
          body: JSON.stringify(scenario),
        }),
      );

      setOrder(data as SimulatedOrder);
      setMessage(
        "Reservation accepted. Retrying with the same " +
          "idempotency key returns the same order.",
      );

      await refreshInventory();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Reservation failed.");
    } finally {
      setLoading(false);
    }
  }

  async function transition(action: "commit" | "cancel") {
    if (!order) return;

    setLoading(true);
    setError("");
    setMessage("");

    try {
      const data = await readApi(
        await fetch(`${API}/orders/${order.order_id}/${action}`, {
          method: "POST",
        }),
      );

      setOrder(data as SimulatedOrder);
      setMessage(
        action === "commit"
          ? "Transaction committed in simulation only."
          : "Reservation cancelled; synthetic stock returned.",
      );

      await refreshInventory();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Transaction operation failed.",
      );

      // Read the persisted state in case the operation
      // actually completed or the reservation expired.
      await refreshOrder();
    } finally {
      setLoading(false);
    }
  }

  async function refreshOrder() {
    try {
      if (order) {
        const data = await readApi(
          await fetch(`${API}/orders/${order.order_id}`, {
            cache: "no-store",
          }),
        );
        setOrder(data as SimulatedOrder);
      }

      await refreshInventory();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not refresh transaction state.",
      );
    }
  }

  const terminal = Boolean(order && order.status !== "RESERVED");

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/85 p-3 text-slate-100 backdrop-blur-sm">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="transaction-title"
        className="flex max-h-[92dvh] w-full max-w-6xl flex-col overflow-hidden rounded-2xl border border-slate-700 bg-[#111827] shadow-2xl"
      >
        <header className="flex shrink-0 items-center justify-between border-b border-slate-800 p-4">
          <div className="flex items-center gap-3">
            <ShieldCheck size={23} className="text-sky-400" />
            <div>
              <h2 id="transaction-title" className="font-semibold">
                Transaction Safety Lab
              </h2>
              <p className="text-xs text-slate-400">
                Atomic inventory · Idempotency · Recovery
              </p>
            </div>
          </div>

          <button
            type="button"
            aria-label="Close Transaction Safety Lab"
            onClick={onClose}
            className="rounded-lg border border-slate-700 p-2"
          >
            <X size={18} />
          </button>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto p-4">
          <div className="grid gap-4 lg:grid-cols-[310px_minmax(0,1fr)]">
            <div className="space-y-4">
              <div className="space-y-3 rounded-xl border border-slate-700 bg-[#0A101B] p-4">
                <h3 className="text-sm font-semibold">
                  Reservation constraints
                </h3>

                <p className="text-xs text-slate-500">
                  Only synthetic offers from Chunk 5A are used.
                </p>

                <label className="block text-xs text-slate-400">
                  Budget (₹)
                  <input
                    type="number"
                    min={100}
                    max={100000}
                    disabled={active}
                    value={scenario.budget_inr}
                    onChange={(e) =>
                      newScenario({
                        ...scenario,
                        budget_inr: Number(e.target.value),
                      })
                    }
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5"
                  />
                </label>

                <label className="block text-xs text-slate-400">
                  Delivery deadline (minutes)
                  <input
                    type="number"
                    min={0}
                    max={240}
                    disabled={active}
                    value={scenario.deadline_minutes}
                    onChange={(e) =>
                      setScenario({
                        ...scenario,
                        deadline_minutes: Number(e.target.value),
                      })
                    }
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5"
                  />
                </label>

                <label className="block text-xs text-slate-400">
                  Maximum merchants
                  <select
                    disabled={active}
                    value={scenario.max_merchants}
                    onChange={(e) =>
                      setScenario({
                        ...scenario,
                        max_merchants: Number(e.target.value),
                      })
                    }
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5"
                  >
                    <option value={1}>1 merchant</option>
                    <option value={2}>2 merchants</option>
                    <option value={3}>3 merchants</option>
                  </select>
                </label>

                <label className="block text-xs text-slate-400">
                  Reservation time-to-live
                  <select
                    disabled={active}
                    value={scenario.ttl_seconds}
                    onChange={(e) =>
                      setScenario({
                        ...scenario,
                        ttl_seconds: Number(e.target.value),
                      })
                    }
                    className="mt-1 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5"
                  >
                    <option value={10}>10 seconds — expiry test</option>
                    <option value={60}>60 seconds</option>
                    <option value={120}>120 seconds</option>
                    <option value={300}>300 seconds</option>
                  </select>
                </label>

                <button
                  type="button"
                  disabled={loading || terminal}
                  onClick={() => void reserve()}
                  className="w-full rounded-lg bg-sky-500 px-4 py-3 text-sm font-semibold text-slate-950 disabled:opacity-40"
                >
                  {loading
                    ? "Processing..."
                    : order
                      ? "Retry Same Reservation"
                      : "Reserve Basket"}
                </button>

                <button
                  type="button"
                  disabled={loading || active}
                  onClick={() => newScenario()}
                  className="w-full rounded-lg border border-slate-700 px-4 py-2.5 text-xs text-slate-300 disabled:opacity-40"
                >
                  New Scenario / New Idempotency Key
                </button>

                <p className="text-[11px] leading-5 text-slate-500">
                  Repeated reservations use the same idempotency key. A new
                  scenario generates a new key.
                </p>
              </div>

              <div className="rounded-xl border border-slate-700 bg-[#0A101B] p-4">
                <h3 className="text-sm font-semibold">Quick experiments</h3>

                <div className="mt-3 grid grid-cols-2 gap-2">
                  {[
                    { label: "Normal", value: NORMAL },
                    {
                      label: "Short expiry",
                      value: { ...NORMAL, ttl_seconds: 10 },
                    },
                    {
                      label: "Low budget",
                      value: { ...NORMAL, budget_inr: 1559 },
                    },
                    {
                      label: "Urgent",
                      value: {
                        ...NORMAL,
                        deadline_minutes: 10,
                      },
                    },
                  ].map((experiment) => (
                    <button
                      key={experiment.label}
                      type="button"
                      disabled={loading || active}
                      onClick={() => newScenario(experiment.value)}
                      className="rounded-lg border border-slate-700 px-2 py-2 text-xs text-slate-300 hover:bg-slate-800 disabled:opacity-40"
                    >
                      {experiment.label}
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="min-w-0 space-y-4">
              <div className="rounded-xl border border-slate-700 bg-[#0A101B] p-4">
                <div className="flex items-center justify-between gap-2">
                  <h3 className="text-sm font-semibold">Current transaction</h3>

                  <button
                    type="button"
                    disabled={loading}
                    onClick={() => void refreshOrder()}
                    aria-label="Refresh transaction"
                    className="rounded-lg border border-slate-700 p-2"
                  >
                    <RefreshCw size={15} />
                  </button>
                </div>

                {!order ? (
                  <p className="mt-4 text-xs text-slate-400">
                    Reserve a basket to begin the transaction.
                  </p>
                ) : (
                  <>
                    <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-xs text-slate-500">
                          Simulation order #{order.order_id}
                        </p>
                        <p className="mt-1 text-lg font-semibold text-sky-300">
                          {order.status.replaceAll("_", " ")}
                        </p>
                      </div>

                      <p className="text-xl font-semibold">
                        {rupees(order.plan.totals.total_minor)}
                      </p>
                    </div>

                    <div className="mt-4 space-y-2">
                      {order.plan.selected_offers.map((offer) => (
                        <div
                          key={offer.sku}
                          className="flex justify-between gap-3 border-b border-slate-800 pb-2 text-xs"
                        >
                          <span className="text-slate-400">
                            {offer.item_name} · {offer.merchant}
                          </span>
                          <span>{rupees(offer.line_total_minor)}</span>
                        </div>
                      ))}
                    </div>

                    {order.status === "RESERVED" && (
                      <div className="mt-4 grid grid-cols-2 gap-2">
                        <button
                          type="button"
                          disabled={loading}
                          onClick={() => void transition("commit")}
                          className="rounded-lg bg-emerald-500 px-3 py-3 text-xs font-semibold text-slate-950 disabled:opacity-40"
                        >
                          <PackageCheck size={15} className="mr-1 inline" />
                          Simulate Commit
                        </button>

                        <button
                          type="button"
                          disabled={loading}
                          onClick={() => void transition("cancel")}
                          className="rounded-lg border border-amber-500/30 px-3 py-3 text-xs text-amber-300 disabled:opacity-40"
                        >
                          <RotateCcw size={15} className="mr-1 inline" />
                          Cancel Reservation
                        </button>
                      </div>
                    )}

                    <p className="mt-3 flex items-center gap-2 text-xs text-slate-500">
                      <Clock3 size={14} />
                      Expires: {new Date(order.expires_at).toLocaleString()}
                    </p>
                  </>
                )}
              </div>

              <div className="rounded-xl border border-slate-700 bg-[#0A101B] p-4">
                <h3 className="text-sm font-semibold">Synthetic inventory</h3>

                <div className="mt-3 grid grid-cols-3 gap-2">
                  {inventory.map((item) => (
                    <div
                      key={item.sku}
                      className="rounded-lg border border-slate-800 p-2 text-center"
                    >
                      <p className="text-[11px] text-slate-500">{item.sku}</p>
                      <p className="mt-1 text-sm font-semibold">
                        {item.available_quantity}
                        <span className="text-slate-500">
                          /{item.initial_quantity}
                        </span>
                      </p>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-xl border border-slate-700 bg-[#0A101B] p-4">
                <h3 className="text-sm font-semibold">
                  Transaction audit trail
                </h3>

                {!order?.events.length ? (
                  <p className="mt-3 text-xs text-slate-500">
                    No transaction events yet.
                  </p>
                ) : (
                  <div className="mt-3 space-y-2">
                    {order.events.map((event) => (
                      <div
                        key={event.id}
                        className="flex items-center justify-between gap-3 border-b border-slate-800 pb-2 text-xs"
                      >
                        <span>{event.type.replaceAll("_", " ")}</span>
                        <span className="text-slate-500">
                          {new Date(event.recorded_at).toLocaleString()}
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              <div className="rounded-lg border border-amber-500/20 bg-amber-500/5 p-3 text-xs leading-5 text-amber-200">
                No real payment, purchase or merchant inventory reservation
                occurs in this lab.
              </div>
            </div>
          </div>

          {message && (
            <p role="status" className="mt-4 text-sm text-emerald-400">
              {message}
            </p>
          )}

          {error && (
            <p
              role="alert"
              className="mt-4 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-300"
            >
              {error}
            </p>
          )}
        </div>
      </section>
    </div>
  );
}
