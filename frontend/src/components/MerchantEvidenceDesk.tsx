import { useEffect, useState, type FormEvent } from "react";
import { ClipboardList, ShieldAlert, Store, RefreshCw } from "lucide-react";
import { evidence13bEnabled, type EvidenceInquiry13B } from "../lib/evidence13b";
import {
  merchantAuthInstance, merchantSignIn, merchantSignOut,
  getApprovedMerchantInquiries, submitMerchantReport,
  type MerchantInboxItem13B3,
} from "../lib/merchantEvidence13b3";

type Draft = { qty: string; price: string; notes: string; delivery: "unknown" | "yes" | "no"; confirmed: boolean };
const blankDraft = (): Draft => ({ qty: "", price: "", notes: "", delivery: "unknown", confirmed: false });

/** Protected merchant reporting UI. No automatic verification or contact. */
export default function MerchantEvidenceDesk() {
  const [uid, setUid] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [inquiries, setInquiries] = useState<MerchantInboxItem13B3[]>([]);
  const [selected, setSelected] = useState("");
  const [draft, setDraft] = useState<Draft>(blankDraft);
  const [lastReport, setLastReport] = useState<EvidenceInquiry13B | null>(null);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  useEffect(() => {
    if (!evidence13bEnabled) return;
    const auth = merchantAuthInstance();
    return auth.onAuthStateChanged((user) => {
      setUid(user?.emailVerified ? user.uid : "");
      if (!user) { setInquiries([]); setSelected(""); setLastReport(null); }
    });
  }, []);
  if (!evidence13bEnabled) return null;

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (working) return;
    setWorking(true); setError(""); setNotice("");
    try {
      const user = await merchantSignIn(email, password);
      setUid(user.uid); setPassword("");
      setNotice("Signed in. Business access requires a separate operator-reviewed approval.");
    } catch (exc) { setError(exc instanceof Error ? exc.message : "Sign-in failed."); }
    finally { setWorking(false); }
  }

  async function loadInbox() {
    if (!uid || working) return;
    setWorking(true); setError(""); setNotice("");
    try {
      const inbox = await getApprovedMerchantInquiries();
      setInquiries(inbox.inquiries);
      setNotice(inbox.inquiries.length ? "Approved-place inquiries loaded." : "No inquiries for your approved businesses. A merchant account alone does not grant business access.");
    } catch (exc) { setError(exc instanceof Error ? exc.message : "Could not load inquiries."); }
    finally { setWorking(false); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected || working || !draft.confirmed) return;
    const quantity = Number(draft.qty);
    if (!/^\d+$/.test(draft.qty) || !Number.isSafeInteger(quantity) || quantity > 1_000_000) {
      setError("Enter a whole stock quantity between 0 and 1,000,000."); return;
    }
    const rawPrice = draft.price.trim();
    if (rawPrice && !/^(?:\d{1,7})(?:\.\d{1,2})?$/.test(rawPrice)) {
      setError("Use a valid rupee amount with at most two decimal places."); return;
    }
    const priceMinor = rawPrice ? Math.round(Number(rawPrice) * 100) : null;
    if (priceMinor !== null && (priceMinor <= 0 || priceMinor > 100_000_000)) {
      setError("Reported price must be between ₹0.01 and ₹10,00,000."); return;
    }
    if (quantity > 0 && (!priceMinor || priceMinor <= 0)) {
      setError("Enter the reported price for available stock."); return;
    }
    setWorking(true); setError(""); setNotice("");
    try {
      const result = await submitMerchantReport(selected, {
        authorized_to_report: true, stock_quantity: quantity,
        price_minor: priceMinor, specification_notes: draft.notes.trim() || null,
        delivery_available: draft.delivery === "unknown" ? null : draft.delivery === "yes",
      });
      setLastReport(result); setDraft(blankDraft());
      setNotice("Report saved as merchant-reported, unverified evidence. The decision has been recalculated.");
    } catch (exc) { setError(exc instanceof Error ? exc.message : "Failed to submit evidence."); }
    finally { setWorking(false); }
  }

  return <section id="merchant-evidence-desk" className="scroll-mt-20 rounded-2xl border border-[#30415B] bg-[#111827] p-4 sm:p-5">
    <div className="flex items-center gap-2 text-sky-300"><Store size={18}/><h2 className="font-semibold">Merchant Evidence Desk</h2></div>
    <p className="mt-2 text-xs leading-6 text-slate-400">Authorized merchants can report stock, price, and delivery information for a reviewed business claim. Information remains unverified; it is not an order, reservation, or purchase authorization.</p>
    {!uid ? <form onSubmit={(event) => void signIn(event)} className="mt-4 grid gap-3 sm:max-w-lg">
      <label className="text-xs text-slate-300">Verified merchant email
        <input type="email" required autoComplete="username" value={email} onChange={event => setEmail(event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-700 bg-[#080D17] p-3 text-sm text-white" />
      </label>
      <label className="text-xs text-slate-300">Password
        <input type="password" required autoComplete="current-password" value={password} onChange={event => setPassword(event.target.value)} className="mt-1 block w-full rounded-lg border border-slate-700 bg-[#080D17] p-3 text-sm text-white" />
      </label>
      <button disabled={working} className="min-h-11 rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-40">{working ? "Signing in..." : "Merchant sign in"}</button>
      <p className="text-xs text-slate-500">An operator must separately review proof of business ownership. No self-approval is available.</p>
    </form> : <div className="mt-4 space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs text-slate-400">Signed in (UID: <code className="break-all text-slate-200">{uid}</code>)</span>
        <button type="button" onClick={() => void loadInbox()} disabled={working} className="inline-flex min-h-11 items-center gap-2 rounded-lg border border-sky-500/40 px-3 py-2 text-xs text-sky-200 disabled:opacity-40"><RefreshCw size={14}/> Load approved inquiries</button>
        <button type="button" disabled={working} onClick={() => { void merchantSignOut(); setPassword(""); }} className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300">Sign out</button>
      </div>
      {!!inquiries.length && <div className="grid gap-2">
        <label className="text-xs text-slate-300">Business inquiry
          <select value={selected} onChange={event => { setSelected(event.target.value); setDraft(blankDraft()); setLastReport(null); }} className="mt-1 block w-full rounded-lg border border-slate-700 bg-[#080D17] p-3 text-sm text-white">
            <option value="">Select an approved inquiry</option>
            {inquiries.map(item => <option key={item.inquiry_id} value={item.inquiry_id}>{item.product_query} · {item.place_id.slice(0, 20)} · expires {new Date(item.expires_at).toLocaleDateString()}</option>)}
          </select>
        </label>
      </div>}
      {selected && <form onSubmit={(event) => void submit(event)} className="grid gap-3 rounded-xl border border-slate-700 p-3 sm:max-w-xl">
        <label className="text-xs text-slate-300">Reported units in stock
          <input required type="number" min="0" max="1000000" step="1" value={draft.qty} onChange={event => setDraft({...draft, qty: event.target.value})} className="mt-1 block w-full rounded-lg border border-slate-700 bg-[#080D17] p-3 text-sm text-white" />
        </label>
        <label className="text-xs text-slate-300">Reported unit price (₹)
          <input type="text" inputMode="decimal" placeholder="e.g. 899.00" maxLength={12} value={draft.price} onChange={event => setDraft({...draft, price: event.target.value})} className="mt-1 block w-full rounded-lg border border-slate-700 bg-[#080D17] p-3 text-sm text-white" />
        </label>
        <label className="text-xs text-slate-300">Delivery available
          <select value={draft.delivery} onChange={event => setDraft({...draft, delivery: event.target.value as Draft["delivery"]})} className="mt-1 block w-full rounded-lg border border-slate-700 bg-[#080D17] p-3 text-sm text-white">
            <option value="unknown">Unknown</option><option value="yes">Merchant says yes</option><option value="no">Merchant says no</option>
          </select>
        </label>
        <label className="text-xs text-slate-300">Product and compatibility notes
          <textarea maxLength={1500} rows={3} value={draft.notes} onChange={event => setDraft({...draft, notes: event.target.value})} className="mt-1 block w-full rounded-lg border border-slate-700 bg-[#080D17] p-3 text-sm text-white" />
        </label>
        <label className="flex items-start gap-2 text-xs text-slate-300"><input type="checkbox" checked={draft.confirmed} onChange={event => setDraft({...draft, confirmed: event.target.checked})} /> I am authorized to submit this report for my approved business.</label>
        <button disabled={working || !draft.confirmed} className="min-h-11 rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950 disabled:opacity-40">{working ? "Submitting..." : "Submit merchant-reported evidence"}</button>
      </form>}
      {lastReport && <div className="rounded-lg border border-sky-500/25 p-3 text-xs text-slate-300">
        <p className="flex items-center gap-2 font-semibold text-sky-200"><ClipboardList size={14}/> Evidence history: {lastReport.history.length} revision(s)</p>
        <p className="mt-2">Latest status: {lastReport.status.replace(/_/g, " ")}</p>
        <p className="mt-1">Decision: {lastReport.replanning.candidates[0]?.status ?? "UNKNOWN"}; next verification: {lastReport.replanning.recommended_next_action.replace(/_/g, " ")}</p>
        <p className="mt-1">No purchase authorization. Merchant report is not independently verified.</p>
      </div>}
    </div>}
    {!!notice && <p role="status" className="mt-3 text-xs text-sky-300">{notice}</p>}
    {!!error && <p role="alert" className="mt-3 flex items-center gap-2 text-xs text-rose-300"><ShieldAlert size={14}/>{error}</p>}
  </section>;
}
