import { useEffect, useState } from "react";
import {
  ArrowUpRight,
  Database,
  LoaderCircle,
  RefreshCw,
  X,
} from "lucide-react";

interface EvidenceSummary {
  claim_type: string;
  status: string;
  source: string;
}

interface CatalogProduct {
  id: number;
  merchant_name: string;
  merchant_area: string;
  is_demo: boolean;
  sku: string;
  name: string;
  price_minor: number;
  currency: string;
  stock_available: number;
  stock_freshness: string;
  specifications: Record<string, unknown>;
  evidence: EvidenceSummary[];
}

interface Props {
  onClose: () => void;
}

export default function CatalogModal({ onClose }: Props) {
  const [products, setProducts] = useState<CatalogProduct[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadCatalog(signal?: AbortSignal) {
    setLoading(true);
    setError("");

    try {
      const response = await fetch("/api/catalog/products?category=charger", {
        signal,
      });

      if (!response.ok) {
        throw new Error(`Catalog API returned ${response.status}`);
      }

      const data: CatalogProduct[] = await response.json();
      setProducts(data);
    } catch (err) {
      if (signal?.aborted) return;

      setError(err instanceof Error ? err.message : "Catalog unavailable");
    } finally {
      if (!signal?.aborted) setLoading(false);
    }
  }

  useEffect(() => {
    const controller = new AbortController();

    void loadCatalog(controller.signal);

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }

    document.addEventListener("keydown", handleEscape);

    return () => {
      controller.abort();
      document.removeEventListener("keydown", handleEscape);
    };
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 p-4 backdrop-blur-sm">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="catalog-title"
        className="flex max-h-[88dvh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-slate-700 bg-[#101827] shadow-2xl"
      >
        <header className="flex shrink-0 items-center justify-between border-b border-slate-800 p-5">
          <div>
            <div className="flex items-center gap-2">
              <Database className="text-sky-400" size={20} />

              <h2 id="catalog-title" className="text-lg font-semibold">
                Merchant Intelligence Network
              </h2>
            </div>

            <p className="mt-1 text-xs text-slate-400">
              Simulated retail network · Fictional merchants and inventory
            </p>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void loadCatalog()}
              aria-label="Refresh catalog"
              className="rounded-lg border border-slate-700 p-2 text-slate-300 hover:bg-slate-800"
            >
              <RefreshCw size={17} />
            </button>

            <button
              type="button"
              onClick={onClose}
              aria-label="Close catalog"
              className="rounded-lg border border-slate-700 p-2 text-slate-300 hover:bg-slate-800"
            >
              <X size={17} />
            </button>
          </div>
        </header>

        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          {loading && (
            <div className="flex items-center justify-center gap-3 py-16 text-sm text-slate-400">
              <LoaderCircle size={20} className="animate-spin text-sky-400" />
              Loading merchant records...
            </div>
          )}

          {error && (
            <div className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300">
              {error}
            </div>
          )}

          {!loading && !error && products.length === 0 && (
            <p className="py-16 text-center text-sm text-slate-400">
              No products found. Check the database seed script.
            </p>
          )}

          {!loading && !error && products.length > 0 && (
            <div className="grid gap-4 md:grid-cols-3">
              {products.map((product) => (
                <article
                  key={product.id}
                  className="rounded-xl border border-slate-700 bg-[#0B111C] p-5"
                >
                  <p className="text-xs font-medium text-sky-400">
                    {product.merchant_name}
                  </p>

                  <p className="mt-1 text-xs text-slate-500">
                    {product.merchant_area} · {product.sku}
                  </p>

                  <h3 className="mt-4 min-h-12 text-sm font-semibold leading-6">
                    {product.name}
                  </h3>

                  <p className="mt-2 text-2xl font-semibold text-slate-100">
                    {new Intl.NumberFormat("en-IN", {
                      style: "currency",
                      currency: product.currency,
                    }).format(product.price_minor / 100)}
                  </p>

                  <div className="mt-4 flex flex-wrap gap-2">
                    <span className="rounded-lg bg-slate-800 px-2 py-1 text-xs text-slate-300">
                      Recorded: {product.stock_available} units
                    </span>

                    <span
                      className={`rounded-lg px-2 py-1 text-xs ${
                        product.stock_freshness === "STALE"
                          ? "bg-amber-500/10 text-amber-300"
                          : "bg-sky-500/10 text-sky-300"
                      }`}
                    >
                      {product.stock_freshness === "RECENTLY_CHECKED"
                        ? "RECENT DEMO RECORD"
                        : product.stock_freshness === "STALE"
                          ? "STALE DEMO RECORD"
                          : "NOT CHECKED"}
                    </span>
                  </div>

                  <div className="mt-5 border-t border-slate-800 pt-4">
                    <p className="mb-3 text-xs font-semibold text-slate-300">
                      Evidence records
                    </p>

                    <div className="space-y-2">
                      {product.evidence.map((item, index) => (
                        <div
                          key={`${item.claim_type}-${index}`}
                          className="flex items-center justify-between gap-2 text-xs"
                        >
                          <span className="text-slate-500">
                            {item.claim_type.replaceAll("_", " ")}
                          </span>

                          <span
                            className={
                              item.status === "VERIFIED"
                                ? "text-emerald-400"
                                : item.status === "STALE"
                                  ? "text-amber-300"
                                  : "text-slate-300"
                            }
                          >
                            {item.status === "VERIFIED"
                              ? "VERIFIED IN SIMULATION"
                              : item.status}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="mt-4 flex items-center gap-1 text-[11px] text-slate-500">
                    <ArrowUpRight size={12} />
                    No compatibility or purchase guarantee
                  </div>
                </article>
              ))}
            </div>
          )}
        </div>

        <footer className="shrink-0 border-t border-slate-800 px-5 py-3 text-xs text-slate-500">
          All merchant records are fictional. Stock observations and catalog
          claims are not live merchant guarantees.
        </footer>
      </section>
    </div>
  );
}
