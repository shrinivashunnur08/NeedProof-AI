import { lazy, Suspense } from "react";

// Only the selected route is fetched. No workspace/merchant module is
// eagerly downloaded by the public judge-facing showcase.
const FreeShowcase = lazy(() => import("./FreeShowcase"));
const NeedProofWorkspace = lazy(() => import("./NeedProofWorkspace"));
const MerchantVerificationPage = lazy(() => import("./components/MerchantVerificationPage"));
const LoopApp = lazy(() => import("./loop/LoopApp"));

function RouteLoading() {
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex min-h-dvh items-center justify-center bg-[#090E18] px-4 text-sm text-slate-300"
    >
      Loading NeedProof…
    </div>
  );
}

export default function NeedProofRouter() {
  // The commerce loop app lives at /app in every mode.
  if (/^\/app\/?$/.test(window.location.pathname)) {
    return <Suspense fallback={<RouteLoading />}><LoopApp /></Suspense>;
  }
  // Preserve the previous precedence: showcase mode wins over verify routes.
  if (import.meta.env.VITE_PUBLIC_SHOWCASE === "true") {
    return <Suspense fallback={<RouteLoading />}><FreeShowcase /></Suspense>;
  }
  const match = window.location.pathname.match(/^\/verify\/(\d+)\/?$/);
  if (match) {
    return (
      <Suspense fallback={<RouteLoading />}>
        <MerchantVerificationPage
          requestId={Number(match[1])}
          token={decodeURIComponent(window.location.hash.slice(1))}
        />
      </Suspense>
    );
  }
  return <Suspense fallback={<RouteLoading />}><NeedProofWorkspace /></Suspense>;
}
