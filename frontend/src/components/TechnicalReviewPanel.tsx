import { useEffect, useState, type FormEvent } from "react";
import { AlertTriangle, Cable, ClipboardList, ShieldAlert } from "lucide-react";

interface CompatibilityResult {
  id: number;
  status: string;
  reasons: string[];
  recorded_at: string;
  purchase_allowed: false;
}

interface ConflictInvestigation {
  id: number;
  check_type: string;
  investigation_note: string;
  evidence_reference: string;
  status: string;
  recorded_at: string;
}

interface TechnicalSnapshot {
  case_id: number;
  latest_compatibility: CompatibilityResult | null;
  conflict_investigations: ConflictInvestigation[];
  purchase_allowed: false;
  notice: string;
}

interface Props {
  caseId: number;
  operatorKey: string;
  hasConflict: boolean;
}

function readable(value: string) {
  return value.replaceAll("_", " ");
}

function boolInput(value: string): boolean | null {
  if (value === "yes") return true;
  if (value === "no") return false;
  return null;
}

async function apiJson(response: Response) {
  const raw = await response.text();

  if (!response.ok) {
    let message = `API failed (HTTP ${response.status})`;

    try {
      const parsed = JSON.parse(raw);
      if (typeof parsed.detail === "string") {
        message = parsed.detail;
      }
    } catch {
      // Preserve HTTP status message.
    }

    throw new Error(message);
  }

  if (!raw.trim()) {
    throw new Error("The API returned an empty response.");
  }

  return JSON.parse(raw);
}

export default function TechnicalReviewPanel({
  caseId,
  operatorKey,
  hasConflict,
}: Props) {
  const [snapshot, setSnapshot] = useState<TechnicalSnapshot | null>(null);

  const [deviceModel, setDeviceModel] = useState("TEST-LAPTOP-65W");

  const [devicePd, setDevicePd] = useState("yes");
  const [chargerPd, setChargerPd] = useState("yes");

  const [requiredPower, setRequiredPower] = useState(65);
  const [requiredVoltage, setRequiredVoltage] = useState(20);

  const [outputVoltage, setOutputVoltage] = useState(20);
  const [outputCurrent, setOutputCurrent] = useState(3250);

  const [cableRating, setCableRating] = useState("5");

  const [conflictType, setConflictType] = useState("STOCK");
  const [investigationNote, setInvestigationNote] = useState("");
  const [evidenceReference, setEvidenceReference] = useState("");

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  async function refresh() {
    const response = await fetch(`/api/technical/cases/${caseId}`, {
      headers: {
        "X-Assurance-Key": operatorKey,
      },
      cache: "no-store",
    });

    const result = (await apiJson(response)) as TechnicalSnapshot;

    setSnapshot(result);
  }

  useEffect(() => {
    let active = true;
    const controller = new AbortController();

    async function initialLoad() {
      try {
        const response = await fetch(`/api/technical/cases/${caseId}`, {
          headers: {
            "X-Assurance-Key": operatorKey,
          },
          signal: controller.signal,
          cache: "no-store",
        });

        const result = (await apiJson(response)) as TechnicalSnapshot;

        if (active) setSnapshot(result);
      } catch (err) {
        if (active) {
          setError(
            err instanceof Error
              ? err.message
              : "Could not load technical review.",
          );
        }
      }
    }

    void initialLoad();

    return () => {
      active = false;
      controller.abort();
    };
  }, [caseId, operatorKey]);

  async function checkCompatibility(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setMessage("");

    try {
      const response = await fetch(
        `/api/technical/cases/${caseId}/compatibility`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Assurance-Key": operatorKey,
          },
          body: JSON.stringify({
            device_model: deviceModel,
            device_supports_usb_pd: boolInput(devicePd),
            device_required_power_w: requiredPower,
            device_required_voltage_v: requiredVoltage,
            charger_supports_usb_pd: boolInput(chargerPd),
            charger_profiles: [
              {
                voltage_v: outputVoltage,
                current_ma: outputCurrent,
              },
            ],
            cable_current_rating_a:
              cableRating === "unknown" ? null : Number(cableRating),
          }),
        },
      );

      const result = await apiJson(response);
      setMessage(`Assessment saved: ${readable(result.status)}`);

      await refresh();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Compatibility review failed.",
      );
    } finally {
      setLoading(false);
    }
  }

  async function recordInvestigation(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setMessage("");

    try {
      const response = await fetch(
        `/api/technical/cases/${caseId}/conflict-investigations`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Assurance-Key": operatorKey,
          },
          body: JSON.stringify({
            check_type: conflictType,
            investigation_note: investigationNote.trim(),
            evidence_reference: evidenceReference.trim(),
          }),
        },
      );

      await apiJson(response);
      setMessage("Investigation recorded. The conflict remains unresolved.");

      setInvestigationNote("");
      setEvidenceReference("");

      await refresh();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not record investigation.",
      );
    } finally {
      setLoading(false);
    }
  }

  const latest = snapshot?.latest_compatibility;

  return (
    <section className="space-y-4">
      <div className="flex items-center gap-2">
        <ClipboardList size={18} className="text-sky-400" />
        <h3 className="text-sm font-semibold">Technical Verification Gate</h3>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Compatibility inputs */}
        <form
          onSubmit={checkCompatibility}
          className="space-y-3 rounded-xl border border-slate-700 bg-[#0A101B] p-4"
        >
          <div className="flex items-center gap-2">
            <Cable size={18} className="text-sky-400" />
            <h4 className="text-sm font-semibold">
              Charger Compatibility Check
            </h4>
          </div>

          <p className="text-xs leading-5 text-slate-400">
            Enter stated specifications from a test fixture or an actual
            documented product. These inputs are not independently
            authenticated.
          </p>

          <label className="block text-xs text-slate-400">
            Laptop model
            <input
              required
              minLength={2}
              maxLength={120}
              value={deviceModel}
              onChange={(e) => setDeviceModel(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"
            />
          </label>

          <div className="grid grid-cols-2 gap-3">
            <label className="text-xs text-slate-400">
              Laptop power (W)
              <input
                type="number"
                min={1}
                max={240}
                required
                value={requiredPower}
                onChange={(e) => setRequiredPower(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"
              />
            </label>

            <label className="text-xs text-slate-400">
              Required voltage (V)
              <input
                type="number"
                min={5}
                max={48}
                required
                value={requiredVoltage}
                onChange={(e) => setRequiredVoltage(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"
              />
            </label>

            <label className="text-xs text-slate-400">
              Laptop USB-C PD
              <select
                value={devicePd}
                onChange={(e) => setDevicePd(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"
              >
                <option value="yes">Supported</option>
                <option value="no">Not supported</option>
                <option value="unknown">Unknown</option>
              </select>
            </label>

            <label className="text-xs text-slate-400">
              Charger USB-C PD
              <select
                value={chargerPd}
                onChange={(e) => setChargerPd(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"
              >
                <option value="yes">Supported</option>
                <option value="no">Not supported</option>
                <option value="unknown">Unknown</option>
              </select>
            </label>

            <label className="text-xs text-slate-400">
              Charger output (V)
              <input
                type="number"
                min={5}
                max={48}
                required
                value={outputVoltage}
                onChange={(e) => setOutputVoltage(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"
              />
            </label>

            <label className="text-xs text-slate-400">
              Charger current (mA)
              <input
                type="number"
                min={100}
                max={5000}
                required
                value={outputCurrent}
                onChange={(e) => setOutputCurrent(Number(e.target.value))}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"
              />
            </label>
          </div>

          <label className="block text-xs text-slate-400">
            USB-C cable rating
            <select
              value={cableRating}
              onChange={(e) => setCableRating(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"
            >
              <option value="unknown">Unknown</option>
              <option value="3">3 A-rated cable</option>
              <option value="5">5 A-rated cable</option>
            </select>
          </label>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-sky-500 px-4 py-3 text-sm font-semibold text-slate-950 disabled:opacity-50"
          >
            {loading ? "Evaluating..." : "Check Technical Compatibility"}
          </button>
        </form>

        {/* Results */}
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-700 bg-[#0A101B] p-4">
            <h4 className="text-sm font-semibold">
              Latest technical assessment
            </h4>

            {!latest ? (
              <p className="mt-3 text-xs text-slate-500">
                No compatibility assessment has been saved yet.
              </p>
            ) : (
              <>
                <p className="mt-3 text-sm font-semibold text-sky-300">
                  {readable(latest.status)}
                </p>

                <div className="mt-3 space-y-2">
                  {latest.reasons.map((reason, index) => (
                    <p key={index} className="text-xs leading-5 text-slate-400">
                      {reason}
                    </p>
                  ))}
                </div>

                <p className="mt-3 text-[11px] text-slate-500">
                  Recorded {new Date(latest.recorded_at).toLocaleString()}
                </p>
              </>
            )}
          </div>

          <div className="rounded-xl border border-amber-500/25 bg-amber-500/5 p-4">
            <p className="flex items-center gap-2 text-xs font-semibold text-amber-300">
              <ShieldAlert size={16} />
              Purchase eligibility remains blocked
            </p>

            <p className="mt-2 text-xs leading-5 text-slate-400">
              This check evaluates entered technical claims. Merchant
              authentication, genuine product evidence, stock reliability and
              deadline fulfillment still need independent confirmation.
            </p>
          </div>
        </div>
      </div>

      {hasConflict && (
        <div className="grid gap-4 lg:grid-cols-2">
          <form
            onSubmit={recordInvestigation}
            className="space-y-3 rounded-xl border border-amber-500/25 bg-[#0A101B] p-4"
          >
            <h4 className="flex items-center gap-2 text-sm font-semibold text-amber-300">
              <AlertTriangle size={16} />
              Conflict Investigation
            </h4>

            <p className="text-xs leading-5 text-slate-400">
              Record a follow-up investigation. This does not automatically
              clear the original contradiction.
            </p>

            <label className="block text-xs text-slate-400">
              Contradicted claim
              <select
                value={conflictType}
                onChange={(e) => setConflictType(e.target.value)}
                className="mt-1 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"
              >
                <option value="STOCK">Stock</option>
                <option value="PRICE">Price</option>
                <option value="IDENTITY">Identity</option>
              </select>
            </label>

            <label className="block text-xs text-slate-400">
              Evidence reference
              <input
                required
                minLength={5}
                maxLength={300}
                value={evidenceReference}
                onChange={(e) => setEvidenceReference(e.target.value)}
                placeholder="e.g. TEST-REF-001"
                className="mt-1 w-full rounded-lg border border-slate-700 bg-[#080D17] p-2.5 text-sm"
              />
            </label>

            <label className="block text-xs text-slate-400">
              Investigation note
              <textarea
                required
                minLength={12}
                maxLength={1000}
                rows={3}
                value={investigationNote}
                onChange={(e) => setInvestigationNote(e.target.value)}
                placeholder="Describe what was examined..."
                className="mt-1 w-full resize-none rounded-lg border border-slate-700 bg-[#080D17] p-3 text-sm"
              />
            </label>

            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg border border-amber-500/30 bg-amber-500/10 px-4 py-3 text-xs font-semibold text-amber-300 disabled:opacity-50"
            >
              Record Investigation
            </button>
          </form>

          <div className="rounded-xl border border-slate-700 bg-[#0A101B] p-4">
            <h4 className="text-sm font-semibold">
              Conflict investigation history
            </h4>

            {snapshot?.conflict_investigations.length ? (
              <div className="mt-3 space-y-3">
                {snapshot.conflict_investigations.map((item) => (
                  <div
                    key={item.id}
                    className="rounded-lg border border-slate-800 p-3"
                  >
                    <p className="text-xs font-semibold text-amber-300">
                      {readable(item.status)}
                    </p>

                    <p className="mt-1 text-xs text-slate-400">
                      {item.check_type} · {item.evidence_reference}
                    </p>

                    <p className="mt-2 text-xs leading-5">
                      {item.investigation_note}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-3 text-xs text-slate-500">
                No follow-up investigations recorded.
              </p>
            )}
          </div>
        </div>
      )}

      {message && (
        <p role="status" className="text-xs text-emerald-400">
          {message}
        </p>
      )}

      {error && (
        <p
          role="alert"
          className="rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300"
        >
          {error}
        </p>
      )}
    </section>
  );
}
