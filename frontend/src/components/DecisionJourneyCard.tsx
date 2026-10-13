import {
  ArrowRight,
  BrainCircuit,
  MapPin,
  SearchCheck,
  ShieldAlert,
  ShoppingCart,
} from "lucide-react";

type CustomerIntent = {
  requested_product: string;
  product_category: string | null;
  budget_amount: number | null;
  budget_currency: string | null;
  delivery_location: string | null;
  missing_information: string[];
  clarification_questions: string[];
  compatibility_needs_verification: boolean;
};

interface Props {
  intent: CustomerIntent | null;
  isCurrent: boolean;
  onDiscover: () => void;
  onEvidenceLab: () => void;
  onOptimizerLab: () => void;
}

export default function DecisionJourneyCard({
  intent,
  isCurrent,
  onDiscover,
  onEvidenceLab,
  onOptimizerLab,
}: Props) {
  const ready = intent !== null && isCurrent;

  const steps = [
    {
      label: "Understand",
      icon: BrainCircuit,
      detail: ready ? "Gemini interpreted" : "Awaiting analysis",
      complete: ready,
    },
    {
      label: "Discover",
      icon: MapPin,
      detail: "Find real stores",
      complete: false,
    },
    {
      label: "Investigate",
      icon: SearchCheck,
      detail: "Collect evidence",
      complete: false,
    },
    {
      label: "Decide",
      icon: ShoppingCart,
      detail: "Compare viable offers",
      complete: false,
    },
  ];

  return (
    <section
      aria-label="Customer decision journey"
      className="rounded-xl border border-[#30415B] bg-[#0D1523] p-3.5"
    >
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="text-sm font-semibold text-slate-100">
            Customer decision journey
          </h3>
          <p className="mt-1 text-[11px] text-slate-400">
            From customer intent to an evidence-backed decision
          </p>
        </div>
        <BrainCircuit size={19} className="shrink-0 text-sky-400" />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 xl:grid-cols-4">
        {steps.map((step, index) => {
          const Icon = step.icon;

          return (
            <div
              key={step.label}
              className={
                "rounded-lg border p-2.5 " +
                (step.complete
                  ? "border-sky-500/30 bg-sky-500/10"
                  : "border-slate-700 bg-[#080D17]")
              }
            >
              <div className="flex items-center gap-1.5">
                <Icon
                  size={13}
                  className={step.complete ? "text-sky-400" : "text-slate-500"}
                />
                <span className="text-[11px] font-medium">
                  {index + 1}. {step.label}
                </span>
              </div>

              <p className="mt-1.5 text-[10px] leading-4 text-slate-500">
                {step.detail}
              </p>
            </div>
          );
        })}
      </div>

      {!intent ? (
        <p className="mt-4 text-xs leading-5 text-slate-400">
          Submit your shopping request to Gemini first. NeedProof will use its
          extracted requirements to guide the next steps.
        </p>
      ) : !isCurrent ? (
        <div className="mt-4 rounded-lg border border-amber-500/20 bg-amber-500/5 p-3">
          <p className="text-xs text-amber-300">
            The customer request has changed. Re-run Gemini analysis before
            continuing.
          </p>
        </div>
      ) : (
        <>
          <div className="mt-4 rounded-lg border border-sky-500/20 bg-sky-500/5 p-3">
            <p className="text-[10px] font-semibold uppercase tracking-wide text-sky-400">
              Next recommended action
            </p>

            <p className="mt-1.5 text-sm font-semibold">
              Discover candidate merchants
            </p>

            <p className="mt-1.5 text-xs leading-5 text-slate-400">
              Product: {intent.requested_product}
            </p>

            <p className="mt-1 text-xs text-slate-400">
              Location:{" "}
              {intent.delivery_location ??
                "Not specified — choose an area in discovery"}
            </p>

            {intent.budget_amount !== null && (
              <p className="mt-1 text-xs text-slate-400">
                Budget: {intent.budget_currency ?? "INR"}{" "}
                {intent.budget_amount.toLocaleString("en-IN")}
              </p>
            )}
          </div>

          {intent.missing_information.length > 0 && (
            <div className="mt-3 flex items-start gap-2">
              <ShieldAlert
                size={15}
                className="mt-0.5 shrink-0 text-amber-400"
              />

              <div>
                <p className="text-xs font-medium text-amber-300">
                  Missing customer information
                </p>

                <p className="mt-1 text-xs leading-5 text-slate-400">
                  {intent.missing_information.slice(0, 2).join(" · ")}
                </p>
              </div>
            </div>
          )}
        </>
      )}

      <button
        type="button"
        disabled={!ready}
        onClick={onDiscover}
        className="mt-4 flex w-full items-center justify-center gap-2 rounded-lg bg-sky-500 px-3 py-2.5 text-xs font-semibold text-slate-950 hover:bg-sky-400 disabled:cursor-not-allowed disabled:opacity-40"
      >
        Discover real stores
        <ArrowRight size={15} />
      </button>

      <div className="mt-2 grid grid-cols-2 gap-2">
        <button
          type="button"
          onClick={onEvidenceLab}
          className="rounded-lg border border-slate-700 px-2 py-2 text-[11px] text-slate-300 hover:bg-slate-800"
        >
          EVSI simulation
        </button>

        <button
          type="button"
          onClick={onOptimizerLab}
          className="rounded-lg border border-slate-700 px-2 py-2 text-[11px] text-slate-300 hover:bg-slate-800"
        >
          Optimizer simulation
        </button>
      </div>

      <p className="mt-3 text-[10px] leading-4 text-slate-500">
        Real merchant evidence is not yet attached to this customer journey.
        Simulation results must not be presented as verified offers.
      </p>
    </section>
  );
}
