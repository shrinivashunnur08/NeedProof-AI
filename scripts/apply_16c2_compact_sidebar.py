"""Apply the compact, non-scrolling NeedProof desktop sidebar (local-only)."""
from __future__ import annotations
import argparse
import hashlib
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "frontend/src/FreeShowcase.tsx"
BASELINE = "56a81b7"
SUPPORTED_HASHES = {'17c50a6caf37629a588076aa3a5b0ac48f0360764942ee1f21ede827cd586e54', 'd1e5ede76363027b3a511518d0405a5846a6c1cef94ae63f0f3ec0db19469ca9'}
RESULT_HASH = "2bbc2e5d2da52765d113758265a8242338e6dfed4c9646f643a76ece9beeb35d"
OLD_MARKER = '<aside '
NEW_MARKER = 'aria-label="NeedProof workspace sidebar"'
NEW_BLOCK = '      <aside\n        aria-label="NeedProof workspace sidebar"\n        className="hidden w-[240px] shrink-0 flex-col overflow-hidden border-r border-[#233348] bg-[#0B121D] px-3 py-4 lg:sticky lg:top-0 lg:flex lg:h-dvh"\n      >\n        <div className="flex shrink-0 items-center gap-2.5 rounded-xl px-2 py-1">\n          <span className="flex size-10 shrink-0 items-center justify-center rounded-xl border border-sky-400/15 bg-sky-400/10 text-sky-400">\n            <ShieldCheck size={22} />\n          </span>\n          <div className="min-w-0">\n            <h1 className="text-[15px] font-bold tracking-tight text-white">\n              NeedProof <span className="text-sky-400">AI</span>\n            </h1>\n            <p className="text-[9px] font-medium tracking-[0.11em] text-slate-500">\n              COMMERCE INTELLIGENCE\n            </p>\n          </div>\n        </div>\n\n        <p className="mb-2 mt-5 shrink-0 px-2 text-[10px] font-semibold uppercase tracking-[0.15em] text-slate-500 [@media(max-height:550px)]:mt-3">\n          Workspace\n        </p>\n        <nav aria-label="Showcase workspace" className="flex shrink-0 flex-col gap-1.5 [@media(max-height:550px)]:gap-1">\n          <a\n            href="#judge-replay-16c2"\n            className="group flex min-h-[36px] items-center gap-2.5 rounded-lg border border-emerald-400/40 bg-emerald-400/10 px-2.5 py-2 text-[11px] font-semibold text-emerald-200 transition-colors hover:border-emerald-400/70 hover:bg-emerald-400/15 [@media(max-height:550px)]:min-h-[32px] [@media(max-height:550px)]:py-1.5"\n          >\n            <Sparkles size={14} className="shrink-0 text-emerald-300" />\n            <span className="min-w-0 flex-1">Start guided demo</span>\n            <ArrowRight size={13} className="shrink-0 text-emerald-400/70 transition-transform group-hover:translate-x-0.5" />\n          </a>\n          <a\n            href="#real-store-discovery"\n            className="flex min-h-[36px] items-center gap-2.5 rounded-lg px-2.5 py-2 text-[11px] font-medium text-slate-300 transition-colors hover:bg-sky-500/10 hover:text-sky-200 [@media(max-height:550px)]:min-h-[32px] [@media(max-height:550px)]:py-1.5"\n          >\n            <MapPin size={14} className="shrink-0 text-sky-400" /> Discover Real Stores\n          </a>\n          {evidence13bEnabled && (\n            <a\n              href="#merchant-evidence-desk"\n              className="flex min-h-[36px] items-center gap-2.5 rounded-lg px-2.5 py-2 text-[11px] font-medium text-slate-300 transition-colors hover:bg-sky-500/10 hover:text-sky-200 [@media(max-height:550px)]:min-h-[32px] [@media(max-height:550px)]:py-1.5"\n            >\n              <ShoppingBag size={14} className="shrink-0 text-sky-400" /> Merchant Desk\n            </a>\n          )}\n          <a\n            href="#evidence-workbench"\n            className="flex min-h-[36px] items-center gap-2.5 rounded-lg px-2.5 py-2 text-[11px] font-medium text-slate-300 transition-colors hover:bg-sky-500/10 hover:text-sky-200 [@media(max-height:550px)]:min-h-[32px] [@media(max-height:550px)]:py-1.5"\n          >\n            <ShieldCheck size={14} className="shrink-0 text-sky-400" /> Evidence Intelligence\n          </a>\n          <a\n            href="#customer-request"\n            className="flex min-h-[36px] items-center gap-2.5 rounded-lg border border-sky-400/25 bg-sky-400/[0.08] px-2.5 py-2 text-[11px] font-semibold text-sky-200 transition-colors hover:bg-sky-400/[0.14] [@media(max-height:550px)]:min-h-[32px] [@media(max-height:550px)]:py-1.5"\n          >\n            <BrainCircuit size={14} className="shrink-0 text-sky-400" /> Demand Studio\n          </a>\n          <a\n            href="#adaptive-demo"\n            className="flex min-h-[36px] items-center gap-2.5 rounded-lg px-2.5 py-2 text-[11px] font-medium text-slate-300 transition-colors hover:bg-slate-800/70 hover:text-white [@media(max-height:550px)]:min-h-[32px] [@media(max-height:550px)]:py-1.5"\n          >\n            <FlaskConical size={14} className="shrink-0 text-slate-400" /> Scenario Lab\n          </a>\n          <a\n            href="#journey-history"\n            className="flex min-h-[36px] items-center gap-2.5 rounded-lg px-2.5 py-2 text-[11px] font-medium text-slate-300 transition-colors hover:bg-slate-800/70 hover:text-white [@media(max-height:550px)]:min-h-[32px] [@media(max-height:550px)]:py-1.5"\n          >\n            <Clock3 size={14} className="shrink-0 text-slate-400" /> Saved Journey\n          </a>\n        </nav>\n\n        <section aria-label="Local capabilities" className="mt-4 shrink-0 border-t border-slate-800/80 pt-3 [@media(max-height:650px)]:hidden">\n          <p className="px-2 text-[10px] font-semibold uppercase tracking-[0.13em] text-slate-500">\n            Local full-stack modules\n          </p>\n          <div className="mt-2 grid grid-cols-2 gap-1.5 px-1 text-[10px] text-slate-400">\n            <span className="rounded-md bg-white/[0.035] px-2 py-1">Store discovery</span>\n            <span className="rounded-md bg-white/[0.035] px-2 py-1">Merchant evidence</span>\n            <span className="rounded-md bg-white/[0.035] px-2 py-1">Optimization</span>\n            <span className="rounded-md bg-white/[0.035] px-2 py-1">Merchant portal</span>\n            <span className="col-span-2 rounded-md bg-white/[0.035] px-2 py-1">Assurance desk</span>\n          </div>\n          <p className="mt-2 px-2 text-[10px] leading-[15px] text-amber-200/70">\n            Merchant operations require local FastAPI. Cloud decisions are opt-in.\n          </p>\n        </section>\n\n        <div className="mt-auto shrink-0 pt-3 [@media(max-height:550px)]:pt-1.5">\n          <div className="rounded-xl border border-sky-400/15 bg-gradient-to-br from-[#112638] to-[#101A29] px-3 py-2.5 [@media(max-height:550px)]:py-2">\n            <p className="flex items-center gap-2 text-[11px] font-semibold text-sky-200">\n              <Sparkles size={13} className="text-sky-400" /> Firebase Spark Showcase\n            </p>\n            <p className="mt-1 text-[10px] leading-[15px] text-slate-400 [@media(max-height:480px)]:hidden">\n              Gemini via Firebase · Cloud decisions opt-in · Merchant claims unverified\n            </p>\n          </div>\n        </div>\n      </aside>'


def digest(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def verify_git() -> None:
    if (ROOT / ".git").exists():
        result = subprocess.run(
            ["git", "merge-base", "--is-ancestor", BASELINE, "HEAD"],
            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if result.returncode:
            raise ValueError("Git HEAD must include commit 56a81b7")


def main() -> None:
    parser = argparse.ArgumentParser(description="Single-screen NeedProof sidebar, no scrollbar")
    commands = parser.add_mutually_exclusive_group(required=True)
    commands.add_argument("--check", action="store_true")
    commands.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    try:
        verify_git()
        raw = TARGET.read_bytes()
        src = raw.decode("utf-8")
        original = digest(src)
        if original == RESULT_HASH:
            print("PASS: Compact desktop sidebar already installed. No changes.")
            return
        if original not in SUPPORTED_HASHES:
            raise ValueError("Unexpected FreeShowcase.tsx source; refusing to overwrite custom edits. Send git diff for a tailored patch.")
        start = src.index("      <aside ")
        end = src.index("</aside>", start) + len("</aside>")
        if src.count("<aside ") != 1 or src.count("</aside>") != 1:
            raise ValueError("Sidebar anchor is ambiguous")
        result = src[:start] + NEW_BLOCK + src[end:]
        if digest(result) != RESULT_HASH:
            raise ValueError("Post-patch fingerprint differs; aborting")
        if args.check:
            print("PASS: Audited original 16C.2 or prior scrollbar-fix source detected.")
            print("DRY RUN: Only frontend/src/FreeShowcase.tsx would change.")
            print("Layout: compact full-height sidebar, no scrollbar, short-height fallback.")
            print("No cloud APIs, feature flags, credentials, deployments or costs touched.")
            return
        backup_dir = ROOT / "backup_16c2_compact_sidebar"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / "FreeShowcase.tsx"
        if backup_path.exists():
            raise ValueError("Backup already exists; refusing to overwrite it")
        shutil.copy2(TARGET, backup_path)
        newline = "\r\n" if b"\r\n" in raw else "\n"
        with TARGET.open("w", encoding="utf-8", newline=newline) as out:
            out.write(result)
        if digest(TARGET.read_text(encoding="utf-8")) != RESULT_HASH:
            shutil.copy2(backup_path, TARGET)
            raise ValueError("Verification failed; original file restored")
        print("SUCCESS: Compact NeedProof sidebar installed. No sidebar scrollbar.")
        print("Backup:", backup_path)
        print(r"NEXT: scripts\verify_16c2_compact_sidebar.cmd")
    except (ValueError, OSError, UnicodeError) as exc:
        raise SystemExit("STOP: " + str(exc)) from exc


if __name__ == "__main__":
    main()
