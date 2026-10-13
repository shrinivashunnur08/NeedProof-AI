import { useState, type FormEvent } from "react";
import { LogIn, LogOut, Store, X } from "lucide-react";

interface Claim {
  id: number;
  place_id: string;
  status: string;
  business_ownership_independently_verified: boolean;
}

interface MerchantProfile {
  id: number;
  display_name: string;
  email: string;
}

async function getJson(response: Response) {
  const raw = await response.text();

  if (!response.ok) {
    let message = `HTTP ${response.status}`;

    try {
      const parsed = JSON.parse(raw);
      if (typeof parsed.detail === "string") {
        message = parsed.detail;
      }
    } catch {
      // Keep HTTP status.
    }

    throw new Error(message);
  }

  if (!raw.trim()) {
    throw new Error("Server returned an empty response.");
  }

  return JSON.parse(raw);
}

export default function MerchantOnboardingModal({
  onClose,
}: {
  onClose: () => void;
}) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");

  const [token, setToken] = useState("");
  const [profile, setProfile] = useState<MerchantProfile | null>(null);
  const [claims, setClaims] = useState<Claim[]>([]);
  const [placeId, setPlaceId] = useState("");

  const [operatorKey, setOperatorKey] = useState("");
  const [queue, setQueue] = useState<Claim[]>([]);
  const [note] = useState(
    "Local operator review only; no independent ownership proof.",
  );

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  function merchantHeaders() {
    return {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    };
  }

  async function loadClaims(accessToken: string) {
    const response = await fetch("/api/onboarding/claims", {
      headers: {
        Authorization: `Bearer ${accessToken}`,
      },
      cache: "no-store",
    });

    setClaims(await getJson(response));
  }

  async function submitCredentials(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");
    setMessage("");

    try {
      if (mode === "register") {
        await getJson(
          await fetch("/api/onboarding/register", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email,
              password,
              display_name: displayName,
            }),
          }),
        );

        setMode("login");
        setMessage("Account created. Sign in to continue.");
      } else {
        const data = await getJson(
          await fetch("/api/onboarding/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email, password }),
          }),
        );

        setToken(data.access_token);
        setProfile(data.merchant);
        setPassword("");
        await loadClaims(data.access_token);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
    } finally {
      setLoading(false);
    }
  }

  async function createClaim(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setLoading(true);
    setError("");

    try {
      await getJson(
        await fetch("/api/onboarding/claims", {
          method: "POST",
          headers: merchantHeaders(),
          body: JSON.stringify({ place_id: placeId.trim() }),
        }),
      );

      setPlaceId("");
      await loadClaims(token);
      setMessage("Ownership claim submitted for operator review.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not submit claim.");
    } finally {
      setLoading(false);
    }
  }

  async function loadOperatorQueue() {
    setLoading(true);
    setError("");

    try {
      const response = await fetch("/api/onboarding/operator/claims", {
        headers: { "X-Assurance-Key": operatorKey },
        cache: "no-store",
      });

      setQueue(await getJson(response));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Queue unavailable.");
    } finally {
      setLoading(false);
    }
  }

  async function decide(id: number, decision: "APPROVE" | "REJECT") {
    setLoading(true);
    setError("");

    try {
      await getJson(
        await fetch(`/api/onboarding/operator/claims/${id}/decision`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Assurance-Key": operatorKey,
          },
          body: JSON.stringify({
            decision,
            reviewer_note: note,
          }),
        }),
      );

      await loadOperatorQueue();
      if (token) await loadClaims(token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Review failed.");
    } finally {
      setLoading(false);
    }
  }

  async function logout() {
    try {
      await fetch("/api/onboarding/logout", {
        method: "POST",
        headers: merchantHeaders(),
      });
    } finally {
      setToken("");
      setProfile(null);
      setClaims([]);
    }
  }

  return (
    <div className="fixed inset-0 z-[80] flex items-center justify-center bg-black/85 p-3 text-slate-100 backdrop-blur-sm">
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="merchant-portal-title"
        className="flex max-h-[91dvh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl border border-slate-700 bg-[#111827]"
      >
        <header className="flex items-center justify-between border-b border-slate-800 p-5">
          <div className="flex items-center gap-3">
            <Store className="text-sky-400" size={22} />
            <div>
              <h2 id="merchant-portal-title" className="font-semibold">
                Merchant Onboarding
              </h2>
              <p className="text-xs text-slate-400">
                Local accounts · Ownership claims · Operator review
              </p>
            </div>
          </div>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="rounded-lg border border-slate-700 p-2"
          >
            <X size={18} />
          </button>
        </header>

        <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-5">
          {error && (
            <p
              role="alert"
              className="rounded-lg bg-rose-500/10 p-3 text-sm text-rose-300"
            >
              {error}
            </p>
          )}
          {message && (
            <p role="status" className="text-sm text-emerald-400">
              {message}
            </p>
          )}

          {!profile ? (
            <form
              onSubmit={submitCredentials}
              className="mx-auto max-w-md space-y-3 rounded-xl border border-slate-700 bg-[#0A101B] p-5"
            >
              <h3 className="font-semibold">
                {mode === "login"
                  ? "Merchant Sign In"
                  : "Create Merchant Account"}
              </h3>
              {mode === "register" && (
                <input
                  required
                  minLength={2}
                  maxLength={120}
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Display name"
                  className="w-full rounded-lg border border-slate-700 bg-[#080D17] p-3 text-sm"
                />
              )}
              <input
                required
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="Email address"
                autoComplete="username"
                className="w-full rounded-lg border border-slate-700 bg-[#080D17] p-3 text-sm"
              />
              <input
                required
                type="password"
                minLength={mode === "register" ? 12 : 1}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Password"
                autoComplete={
                  mode === "register" ? "new-password" : "current-password"
                }
                className="w-full rounded-lg border border-slate-700 bg-[#080D17] p-3 text-sm"
              />
              <button
                disabled={loading}
                className="w-full rounded-lg bg-sky-500 p-3 text-sm font-semibold text-slate-950"
              >
                <LogIn className="mr-2 inline" size={15} />
                {mode === "login" ? "Sign In" : "Create Account"}
              </button>
              <button
                type="button"
                onClick={() => setMode(mode === "login" ? "register" : "login")}
                className="w-full text-xs text-sky-400"
              >
                {mode === "login"
                  ? "Create a merchant account"
                  : "Already registered? Sign in"}
              </button>
            </form>
          ) : (
            <div className="rounded-xl border border-slate-700 bg-[#0A101B] p-4">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="font-semibold">{profile.display_name}</p>
                  <p className="text-xs text-slate-400">{profile.email}</p>
                </div>
                <button
                  type="button"
                  onClick={() => void logout()}
                  className="rounded-lg border border-slate-700 px-3 py-2 text-xs"
                >
                  <LogOut className="mr-1 inline" size={14} /> Sign Out
                </button>
              </div>

              <form
                onSubmit={createClaim}
                className="mt-5 flex flex-wrap gap-2"
              >
                <input
                  required
                  minLength={3}
                  maxLength={300}
                  value={placeId}
                  onChange={(e) => setPlaceId(e.target.value)}
                  placeholder="Google Place ID"
                  className="min-w-48 flex-1 rounded-lg border border-slate-700 bg-[#080D17] p-3 text-sm"
                />
                <button
                  disabled={loading}
                  className="rounded-lg bg-sky-500 px-4 py-2 text-sm font-semibold text-slate-950"
                >
                  Request Ownership Review
                </button>
              </form>

              <div className="mt-4 space-y-2">
                {claims.map((claim) => (
                  <div
                    key={claim.id}
                    className="rounded-lg border border-slate-800 p-3 text-xs"
                  >
                    <p>Place ID: {claim.place_id}</p>
                    <p className="mt-1 text-amber-300">
                      {claim.status.replaceAll("_", " ")}
                    </p>
                    <p className="mt-1 text-slate-500">
                      Independent business ownership verification: No
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div className="rounded-xl border border-slate-700 bg-[#0A101B] p-4">
            <h3 className="text-sm font-semibold">Local Operator Review</h3>
            <p className="mt-1 text-xs text-slate-400">
              Operator approval records a review decision only. It does not
              establish independent ownership.
            </p>
            <input
              type="password"
              value={operatorKey}
              onChange={(e) => setOperatorKey(e.target.value)}
              placeholder="Assurance operator key"
              autoComplete="off"
              className="mt-3 w-full rounded-lg border border-slate-700 bg-[#080D17] p-3 text-sm"
            />
            <button
              type="button"
              disabled={loading || !operatorKey}
              onClick={() => void loadOperatorQueue()}
              className="mt-2 rounded-lg border border-sky-500/30 px-4 py-2 text-xs text-sky-300"
            >
              Load Pending Claims
            </button>

            {queue
              .filter((claim) => claim.status === "PENDING_REVIEW")
              .map((claim) => (
                <div
                  key={claim.id}
                  className="mt-3 rounded-lg border border-slate-700 p-3"
                >
                  <p className="text-xs">
                    Claim #{claim.id} · {claim.place_id}
                  </p>
                  <div className="mt-2 flex gap-2">
                    <button
                      type="button"
                      disabled={loading}
                      onClick={() => void decide(claim.id, "APPROVE")}
                      className="rounded-lg bg-sky-500 px-3 py-2 text-xs font-semibold text-slate-950"
                    >
                      Operator Approve
                    </button>
                    <button
                      type="button"
                      disabled={loading}
                      onClick={() => void decide(claim.id, "REJECT")}
                      className="rounded-lg border border-rose-500/30 px-3 py-2 text-xs text-rose-300"
                    >
                      Reject
                    </button>
                  </div>
                </div>
              ))}
          </div>

          <p className="text-xs leading-5 text-amber-300">
            Local development only. Account registration, place claims and
            operator approval do not authorize selling, inventory verification,
            payment or purchase commitments.
          </p>
        </div>
      </section>
    </div>
  );
}
