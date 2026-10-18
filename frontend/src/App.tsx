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

function ClassicBar() {
  return (
    <div className="sticky top-0 z-50 flex flex-wrap items-center justify-between gap-2 border-b border-teal-500/30 bg-[#06231f] px-4 py-2 text-sm text-teal-100">
      <span><strong>Evidence lab</strong> · the decision engine, Evidence Passport and benchmarks behind NeedProof</span>
      <a href="/" className="rounded-md bg-teal-500 px-3 py-1 text-xs font-semibold text-slate-950 hover:bg-teal-400">← Back to the NeedProof app</a>
    </div>
  );
}

export default function NeedProofRouter() {
  const path = window.location.pathname;
  // The hosted static showcase (production build without a backend) keeps its old home page.
  const hostedShowcase = import.meta.env.PROD && import.meta.env.VITE_PUBLIC_SHOWCASE === "true";
  // The commerce loop app is the home page; the earlier screens live under /classic.
  if (/^\/app\/?$/.test(path) || (path === "/" && !hostedShowcase)) {
    return <Suspense fallback={<RouteLoading />}><LoopApp /></Suspense>;
  }
  if (path.startsWith("/classic")) {
    return (
      <>
        <ClassicBar />
        {import.meta.env.VITE_PUBLIC_SHOWCASE === "true"
          ? <Suspense fallback={<RouteLoading />}><FreeShowcase /></Suspense>
          : <Suspense fallback={<RouteLoading />}><NeedProofWorkspace /></Suspense>}
      </>
    );
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
