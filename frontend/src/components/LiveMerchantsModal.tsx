import { useEffect, useState, type FormEvent } from "react";

import {
  ExternalLink,
  MapPin,
  RefreshCw,
  Search,
  ShieldAlert,
  X,
} from "lucide-react";
import ReportedOffersModal from "./ReportedOffersModal";
import { useRef } from "react";

import type {
  JourneyDiscovery,
  JourneyEvidence,
  JourneyPrefill,
} from "../types/decisionJourney";
type Area =
  | "Thane"
  | "Dombivli"
  | "Kalyan"
  | "Badlapur"
  | "Navi Mumbai"
  | "Mumbai";

type Category = "electronics" | "computer" | "mobile";

interface LiveMerchant {
  place_id: string;
  name: string;
  address: string;
  maps_url: string | null;
  source: "GOOGLE_PLACES";
  is_simulated: false;
  stock_status: "UNKNOWN";
  price_status: "UNKNOWN";
  compatibility_status: "UNKNOWN";
}

interface DiscoveryResult {
  mode: "LIVE_DISCOVERY";
  area: string;
  category: string;
  merchants: LiveMerchant[];
  notice: string;
}

interface Invitation {
  request_id: number;
  invitation_token: string;
  expires_at: string;
}

interface VerificationSummary {
  status: string;
  submission: {
    product_name: string;
    stock_quantity: number;
    price_minor: number | null;
    currency: string;
    submitted_at: string;
    specification_notes: string | null;
    delivery_available: boolean | null;
    evidence_status: string;
    merchant_identity_verified: boolean;
  } | null;
}

interface EvidenceAssessment {
  request_id: number;
  mode: "EVIDENCE_READINESS";
  status: string;
  reported_fields: number;
  total_fields: number;
  report_age_minutes: number | null;
  freshness: string;
  merchant_identity_verified: boolean;
  eligible_for_commitment: boolean;
  checks: {
    field: string;
    status: string;
    detail: string;
  }[];
  recommended_next_action: {
    code: string;
    label: string;
  };
  notice: string;
}

interface Props {
  onClose: () => void;
  isOpen?: boolean;
  initialPrefill?: JourneyPrefill | null;
  onDiscovery?: (data: JourneyDiscovery) => void;
  onEvidence?: (data: JourneyEvidence) => void;
}
export default function LiveMerchantsModal({
  onClose,
  isOpen = true,
  initialPrefill = null,
  onDiscovery,
  onEvidence,
}: Props) {
  const [area, setArea] = useState<Area>("Thane");
  const [category, setCategory] = useState<Category>("electronics");

  const [result, setResult] = useState<DiscoveryResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const [productQuery, setProductQuery] = useState(
    "65W USB-C PD laptop charger",
  );

  const [invites, setInvites] = useState<
    Record<
      string,
      Invitation & {
        link: string;
        product_query: string;
      }
    >
  >({});

  const [verificationResults, setVerificationResults] = useState<
    Record<string, VerificationSummary>
  >({});

  const [creatingFor, setCreatingFor] = useState<string | null>(null);
  const [inviteError, setInviteError] = useState("");
  const [copiedPlace, setCopiedPlace] = useState<string | null>(null);
  const [compareOpen, setCompareOpen] = useState(false);
  const [assessments, setAssessments] = useState<
    Record<string, EvidenceAssessment>
  >({});

  const [assessingFor, setAssessingFor] = useState<string | null>(null);

  const autoSearched = useRef(false);

  useEffect(() => {
    if (!initialPrefill) return;

    setArea(initialPrefill.area ?? "Thane");
    setCategory(initialPrefill.category);
    setProductQuery(initialPrefill.productQuery);
  }, [
    initialPrefill?.area,
    initialPrefill?.category,
    initialPrefill?.productQuery,
  ]);

  useEffect(() => {
    if (
      !isOpen ||
      !initialPrefill ||
      !initialPrefill.area ||
      autoSearched.current
    ) {
      return;
    }

    autoSearched.current = true;

    void searchMerchants(undefined, initialPrefill);
  }, [
    isOpen,
    initialPrefill?.area,
    initialPrefill?.category,
    initialPrefill?.productQuery,
  ]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape" && isOpen && !compareOpen) {
        onClose();
      }
    }

    window.addEventListener("keydown", onKeyDown);

    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose, compareOpen, isOpen]);

  async function searchMerchants(
    event?: FormEvent,
    overrides?: JourneyPrefill,
  ) {
    event?.preventDefault();

    const chosenArea = overrides?.area ?? area;
    const chosenCategory = overrides?.category ?? category;
    const chosenProduct = overrides?.productQuery ?? productQuery.trim();

    setLoading(true);
    setError("");
    setResult(null);

    try {
      const params = new URLSearchParams({
        area: chosenArea,
        category: chosenCategory,
      });

      const response = await fetch(
        `/api/places/merchants?${params.toString()}`,
        { cache: "no-store" },
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : `Merchant discovery failed (${response.status})`,
        );
      }

      const discovered = data as DiscoveryResult;

      setResult(discovered);

      onDiscovery?.({
        area: discovered.area,
        category: discovered.category,
        product_query: chosenProduct,
        merchants: discovered.merchants.map((merchant) => ({
          place_id: merchant.place_id,
          name: merchant.name,
          address: merchant.address,
          maps_url: merchant.maps_url,
        })),
        fetched_at: new Date().toISOString(),
      });
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to discover merchants",
      );
    } finally {
      setLoading(false);
    }
  }

  async function createInvitation(merchant: LiveMerchant) {
    setCreatingFor(merchant.place_id);
    setInviteError("");

    try {
      const response = await fetch("/api/verification/invitations", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          place_id: merchant.place_id,
          product_query: productQuery.trim(),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          typeof data.detail === "string"
            ? data.detail
            : "Could not create invitation",
        );
      }

      const invitation = data as Invitation;

      const link =
        `${window.location.origin}/verify/` +
        `${invitation.request_id}#` +
        encodeURIComponent(invitation.invitation_token);

      setInvites((previous) => ({
        ...previous,
        [merchant.place_id]: {
          ...invitation,
          link,
          product_query: productQuery.trim(),
        },
      }));
      onEvidence?.({
        place_id: merchant.place_id,
        request_id: invitation.request_id,
        product_query: productQuery.trim(),
        status: "AWAITING_RESPONSE",
        submission: null,
        assessment: null,
        updated_at: new Date().toISOString(),
      });
    } catch (err) {
      setInviteError(
        err instanceof Error ? err.message : "Invitation creation failed",
      );
    } finally {
      setCreatingFor(null);
    }
  }

  function publishJourneyEvidence(
    placeId: string,
    summary: VerificationSummary | null,
    assessment: EvidenceAssessment | null,
  ) {
    const invitation = invites[placeId];

    if (!invitation) return;

    const submission = summary?.submission;

    onEvidence?.({
      place_id: placeId,
      request_id: invitation.request_id,
      product_query: invitation.product_query,
      status: summary?.status ?? assessment?.status ?? "AWAITING_RESPONSE",

      submission: submission
        ? {
            product_name: submission.product_name,
            stock_quantity: submission.stock_quantity,
            price_minor: submission.price_minor,
            currency: submission.currency,
            delivery_available: submission.delivery_available,
            submitted_at: submission.submitted_at,
          }
        : null,

      assessment: assessment
        ? {
            status: assessment.status,
            freshness: assessment.freshness,
            reported_fields: assessment.reported_fields,
            total_fields: assessment.total_fields,
            eligible_for_commitment: assessment.eligible_for_commitment,
            recommended_next_action: assessment.recommended_next_action,
          }
        : null,

      updated_at: new Date().toISOString(),
    });
  }

  async function refreshVerification(placeId: string) {
    const invite = invites[placeId];
    if (!invite) return;

    setInviteError("");

    try {
      const response = await fetch(
        `/api/verification/requests/${invite.request_id}`,
        {
          headers: {
            "X-Verification-Token": invite.invitation_token,
          },
          cache: "no-store",
        },
      );

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail ?? "Unable to check evidence");
      }

      const summary = data as VerificationSummary;

      setVerificationResults((previous) => ({
        ...previous,
        [placeId]: summary,
      }));

      publishJourneyEvidence(placeId, summary, assessments[placeId] ?? null);
    } catch (err) {
      setInviteError(
        err instanceof Error ? err.message : "Unable to retrieve evidence",
      );
    }
  }

  async function reviewEvidence(placeId: string) {
    const invitation = invites[placeId];

    if (!invitation) {
      setInviteError("Create an invitation first.");
      return;
    }

    setAssessingFor(placeId);
    setInviteError("");

    try {
      const response = await fetch(
        `/api/verification/requests/${invitation.request_id}/assessment`,
        {
          headers: {
            "X-Verification-Token": invitation.invitation_token,
          },
          cache: "no-store",
        },
      );

      const raw = await response.text();

      if (!response.ok) {
        throw new Error(
          `Evidence assessment failed (HTTP ${response.status}).`,
        );
      }

      if (!raw.trim()) {
        throw new Error("The assessment API returned no data.");
      }

      const data = JSON.parse(raw) as EvidenceAssessment;

      if (data.mode !== "EVIDENCE_READINESS") {
        throw new Error("Unexpected assessment response.");
      }

      setAssessments((previous) => ({
        ...previous,
        [placeId]: data,
      }));

      // Also retrieve the latest merchant response so
      // the shared snapshot is complete even when the
      // operator clicked Review Evidence first.
      const summaryResponse = await fetch(
        `/api/verification/requests/${invitation.request_id}`,
        {
          headers: {
            "X-Verification-Token": invitation.invitation_token,
          },
          cache: "no-store",
        },
      );

      if (!summaryResponse.ok) {
        throw new Error(
          "Assessment loaded, but the merchant response " +
            "could not be refreshed.",
        );
      }

      const summary = (await summaryResponse.json()) as VerificationSummary;

      setVerificationResults((previous) => ({
        ...previous,
        [placeId]: summary,
      }));

      publishJourneyEvidence(placeId, summary, data);
    } catch (err) {
      setInviteError(
        err instanceof Error ? err.message : "Could not assess evidence",
      );
    } finally {
      setAssessingFor(null);
    }
  }

  async function copyInvitation(placeId: string) {
    const invite = invites[placeId];
    if (!invite) return;

    try {
      await navigator.clipboard.writeText(invite.link);
      setCopiedPlace(placeId);
    } catch {
      setInviteError(
        "Clipboard unavailable. Select and copy the link manually.",
      );
    }
  }

  return isOpen ? (
    <>
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-2 backdrop-blur-sm sm:p-4">
        <section
          role="dialog"
          aria-modal="true"
          aria-labelledby="live-merchants-title"
          className="flex max-h-[calc(100dvh-1rem)] w-full max-w-6xl min-w-0 flex-col overflow-hidden rounded-2xl border border-[#33445E] bg-[#111827] shadow-2xl sm:max-h-[92dvh]"
        >
          <header className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-slate-800 px-4 py-3 sm:px-6">
            <div className="flex items-center gap-3">
              <MapPin size={23} className="text-sky-400" />
              <div>
                <h2 id="live-merchants-title" className="text-lg font-semibold">
                  Real Merchant Discovery
                </h2>
                <p className="text-xs text-slate-400">
                  Live business listings from Google Maps Platform
                </p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => setCompareOpen(true)}
              className="rounded-lg border border-sky-500/30 bg-sky-500/10 px-3 py-2 text-xs font-semibold text-sky-300 hover:bg-sky-500/20"
            >
              Compare Reports
            </button>
            <button
              type="button"
              onClick={onClose}
              aria-label="Close discovery"
              className="rounded-lg border border-slate-700 p-2 hover:bg-slate-800"
            >
              <X size={18} />
            </button>
          </header>

          <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
            <form
              onSubmit={searchMerchants}
              className="flex min-w-0 flex-wrap items-end gap-3 border-b border-slate-800 px-4 py-4 sm:px-6"
            >
              <label className="flex min-w-40 flex-1 flex-col gap-2 text-xs text-slate-400">
                Search location
                <select
                  value={area}
                  onChange={(event) => setArea(event.target.value as Area)}
                  className="w-full min-w-0 rounded-lg border border-slate-700 bg-[#080D17] px-3 py-2.5 text-sm text-white"
                >
                  <option>Thane</option>
                  <option>Dombivli</option>
                  <option>Kalyan</option>
                  <option>Badlapur</option>
                  <option>Navi Mumbai</option>
                  <option>Mumbai</option>
                </select>
              </label>

              <label className="flex min-w-40 flex-1 flex-col gap-2 text-xs text-slate-400">
                Store category
                <select
                  value={category}
                  onChange={(event) =>
                    setCategory(event.target.value as Category)
                  }
                  className="rounded-lg border border-slate-700 bg-[#080D17] px-3 py-2.5 text-sm text-white"
                >
                  <option value="electronics">Electronics</option>
                  <option value="computer">Laptop / Computer</option>
                  <option value="mobile">Mobile Stores</option>
                </select>
              </label>

              <label className="flex min-w-48 flex-1 flex-col gap-2 text-xs text-slate-400">
                Product to verify
                <input
                  value={productQuery}
                  onChange={(event) => setProductQuery(event.target.value)}
                  minLength={5}
                  maxLength={250}
                  placeholder="e.g. 65W USB-C PD charger"
                  className="rounded-lg border border-slate-700 bg-[#080D17] px-3 py-2.5 text-sm text-white"
                />
              </label>
              {initialPrefill && !initialPrefill.area && (
                <p className="w-full text-xs text-amber-300">
                  Gemini did not identify a supported search area. Choose the
                  correct location before searching.
                </p>
              )}
              <button
                type="submit"
                disabled={loading}
                className="flex items-center gap-2 rounded-lg bg-sky-500 px-5 py-2.5 text-sm font-semibold text-slate-950 hover:bg-sky-400 disabled:opacity-50"
              >
                {loading ? (
                  <RefreshCw size={17} className="animate-spin" />
                ) : (
                  <Search size={17} />
                )}
                {loading ? "Searching..." : "Find Real Stores"}
              </button>
            </form>

            <div className="p-4 sm:p-6">
              {inviteError && (
                <div
                  role="alert"
                  className="mb-4 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-sm text-rose-300"
                >
                  {inviteError}
                </div>
              )}
              {!result && !loading && !error && (
                <div className="flex min-h-48 flex-col items-center justify-center text-center">
                  <MapPin size={35} className="text-slate-500" />
                  <h3 className="mt-4 font-semibold">
                    Discover actual local merchants
                  </h3>
                  <p className="mt-2 max-w-md text-sm text-slate-400">
                    Select a location and category, then search. Store identity
                    comes from Google Maps. Product availability still needs
                    verification.
                  </p>
                </div>
              )}

              {loading && (
                <div className="py-14 text-center text-sm text-slate-400">
                  Searching Google Places...
                </div>
              )}

              {error && (
                <div
                  role="alert"
                  className="rounded-xl border border-rose-500/30 bg-rose-500/10 p-4 text-sm text-rose-300"
                >
                  {error}
                </div>
              )}

              {result && (
                <>
                  <div className="mb-5 flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <h3 className="font-semibold">
                        {result.merchants.length} stores found
                      </h3>
                      <p className="mt-1 text-xs text-slate-400">
                        {result.area} · {result.category}
                      </p>
                    </div>

                    <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs text-emerald-300">
                      Live discovery
                    </span>
                  </div>

                  {result.merchants.length === 0 ? (
                    <p className="text-sm text-slate-400">
                      No matches returned for this search. Try another location
                      or category.
                    </p>
                  ) : (
                    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                      {result.merchants.map((merchant) => (
                        <article
                          key={merchant.place_id}
                          className="flex flex-col rounded-xl border border-[#304058] bg-[#0A101B] p-4"
                        >
                          <p className="text-sm font-semibold text-slate-100">
                            {merchant.name}
                          </p>

                          <p className="mt-2 flex items-start gap-2 text-xs leading-5 text-slate-400">
                            <MapPin
                              size={14}
                              className="mt-0.5 shrink-0 text-sky-400"
                            />
                            {merchant.address}
                          </p>

                          <div className="mt-4 space-y-2 border-t border-slate-800 pt-3 text-xs">
                            <DataRow
                              label="Product stock"
                              value={
                                verificationResults[merchant.place_id]
                                  ?.submission
                                  ? `${verificationResults[merchant.place_id].submission!.stock_quantity} (reported)`
                                  : "Unknown"
                              }
                            />

                            <DataRow
                              label="Selling price"
                              value={
                                verificationResults[merchant.place_id]
                                  ?.submission?.price_minor != null
                                  ? new Intl.NumberFormat("en-IN", {
                                      style: "currency",
                                      currency: "INR",
                                    }).format(
                                      verificationResults[merchant.place_id]
                                        .submission!.price_minor! / 100,
                                    ) + " (reported)"
                                  : "Unknown"
                              }
                            />

                            <DataRow
                              label="Compatibility"
                              value="Not independently verified"
                            />
                          </div>

                          <div className="mt-auto pt-5">
                            {merchant.maps_url ? (
                              <a
                                href={merchant.maps_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-2 text-xs font-semibold text-sky-400 hover:text-sky-300"
                              >
                                Open in Google Maps
                                <ExternalLink size={14} />
                              </a>
                            ) : (
                              <span className="text-xs text-slate-500">
                                Google Maps link unavailable
                              </span>
                            )}
                          </div>

                          <div className="mt-4 border-t border-slate-800 pt-4">
                            {!invites[merchant.place_id] ? (
                              <button
                                type="button"
                                disabled={
                                  creatingFor !== null ||
                                  productQuery.trim().length < 5
                                }
                                onClick={() => void createInvitation(merchant)}
                                className="w-full rounded-lg border border-sky-500/30 bg-sky-500/10 px-3 py-2.5 text-xs font-semibold text-sky-300 hover:bg-sky-500/20 disabled:opacity-40"
                              >
                                {creatingFor === merchant.place_id
                                  ? "Creating invitation..."
                                  : "Create Verification Invitation"}
                              </button>
                            ) : (
                              <div className="space-y-2">
                                <p className="text-xs text-amber-300">
                                  Invitation created — not sent
                                </p>

                                <input
                                  aria-label="Private invitation link"
                                  readOnly
                                  onFocus={(event) =>
                                    event.currentTarget.select()
                                  }
                                  value={invites[merchant.place_id].link}
                                  className="w-full rounded-lg border border-slate-700 bg-[#080D17] p-2 text-xs text-slate-300"
                                />

                                <div className="flex flex-wrap gap-2">
                                  <button
                                    type="button"
                                    onClick={() =>
                                      void copyInvitation(merchant.place_id)
                                    }
                                    className="rounded-lg bg-sky-500 px-3 py-2 text-xs font-semibold text-slate-950"
                                  >
                                    {copiedPlace === merchant.place_id
                                      ? "Copied"
                                      : "Copy Link"}
                                  </button>

                                  <a
                                    href={invites[merchant.place_id].link}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800"
                                  >
                                    Open Form
                                  </a>

                                  <button
                                    type="button"
                                    onClick={() =>
                                      void refreshVerification(
                                        merchant.place_id,
                                      )
                                    }
                                    className="rounded-lg border border-slate-700 px-3 py-2 text-xs text-slate-300 hover:bg-slate-800"
                                  >
                                    Refresh Evidence
                                  </button>
                                  <button
                                    type="button"
                                    disabled={
                                      assessingFor === merchant.place_id
                                    }
                                    onClick={() =>
                                      void reviewEvidence(merchant.place_id)
                                    }
                                    className="rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs font-semibold text-amber-300 hover:bg-amber-500/20 disabled:opacity-50"
                                  >
                                    {assessingFor === merchant.place_id
                                      ? "Reviewing..."
                                      : "Review Evidence"}
                                  </button>
                                </div>

                                {verificationResults[merchant.place_id] && (
                                  <p className="text-xs text-emerald-300">
                                    Status:{" "}
                                    {
                                      verificationResults[merchant.place_id]
                                        .status
                                    }
                                  </p>
                                )}

                                {assessments[merchant.place_id] && (
                                  <div className="rounded-xl border border-amber-500/25 bg-[#101720] p-3">
                                    <p className="text-xs font-semibold text-amber-300">
                                      Evidence Readiness Assessment
                                    </p>

                                    <div className="mt-3 flex items-center justify-between text-xs">
                                      <span className="text-slate-400">
                                        Information provided
                                      </span>

                                      <span className="font-semibold text-slate-100">
                                        {
                                          assessments[merchant.place_id]
                                            .reported_fields
                                        }
                                        /
                                        {
                                          assessments[merchant.place_id]
                                            .total_fields
                                        }
                                      </span>
                                    </div>

                                    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-800">
                                      <div
                                        className="h-full rounded-full bg-sky-400"
                                        style={{
                                          width: `${
                                            (assessments[merchant.place_id]
                                              .reported_fields /
                                              assessments[merchant.place_id]
                                                .total_fields) *
                                            100
                                          }%`,
                                        }}
                                      />
                                    </div>

                                    <p className="mt-2 text-[11px] leading-5 text-slate-500">
                                      Information coverage only. Not a trust or
                                      verification score.
                                    </p>

                                    <div className="mt-3 space-y-2 border-t border-slate-800 pt-3">
                                      {assessments[
                                        merchant.place_id
                                      ].checks.map((check) => (
                                        <div
                                          key={check.field}
                                          className="flex flex-wrap items-center justify-between gap-1 text-xs"
                                          title={check.detail}
                                        >
                                          <span className="text-slate-400">
                                            {check.field}
                                          </span>

                                          <span className="text-amber-300">
                                            {check.status.replaceAll("_", " ")}
                                          </span>
                                        </div>
                                      ))}
                                    </div>

                                    <div className="mt-3 rounded-lg border border-sky-500/20 bg-sky-500/5 p-3">
                                      <p className="text-[10px] font-semibold uppercase tracking-wide text-sky-400">
                                        Recommended next step
                                      </p>

                                      <p className="mt-1 text-xs font-medium leading-5 text-slate-200">
                                        {
                                          assessments[merchant.place_id]
                                            .recommended_next_action.label
                                        }
                                      </p>
                                    </div>

                                    <p className="mt-3 text-[11px] text-slate-500">
                                      Freshness:{" "}
                                      {assessments[
                                        merchant.place_id
                                      ].freshness.replaceAll("_", " ")}
                                    </p>

                                    <p className="mt-1 text-[11px] text-slate-500">
                                      Eligible for purchase commitment:{" "}
                                      <span className="font-semibold text-amber-300">
                                        No — further verification required
                                      </span>
                                    </p>
                                  </div>
                                )}
                              </div>
                            )}
                          </div>
                        </article>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>

          <footer className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-t border-slate-800 px-4 py-3 sm:px-6">
            <p className="flex items-center gap-2 text-xs text-amber-300">
              <ShieldAlert size={15} />
              Discovery is not proof of stock, price or fulfillment.
            </p>

            <span
              translate="no"
              className="whitespace-nowrap text-sm font-medium text-slate-200"
            >
              Google Maps
            </span>
          </footer>
        </section>
      </div>

      {compareOpen && (
        <ReportedOffersModal
          onClose={() => setCompareOpen(false)}
          initialInvitations={Object.values(invites).map((invitation) => ({
            request_id: invitation.request_id,
            invitation_token: invitation.invitation_token,
          }))}
          merchantLabels={Object.fromEntries(
            (result?.merchants ?? []).map((merchant) => [
              merchant.place_id,
              merchant.name,
            ]),
          )}
        />
      )}
    </>
  ) : null;
}

function DataRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-slate-500">{label}</span>
      <span className="font-medium text-amber-300">{value}</span>
    </div>
  );
}
