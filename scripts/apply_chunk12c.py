"""Safe, layout-tolerant installer for NeedProof Chunk 12C.

Run from repository root:
    python scripts\\apply_chunk12c.py

Only updates FreeShowcase.tsx, does not touch API, env, Firestore, or App.tsx.
"""
from pathlib import Path
import os
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "frontend" / "src" / "FreeShowcase.tsx"
COMPONENT = ROOT / "frontend" / "src" / "components" / "EvidenceWorkbench.tsx"
IMPORT_LINE = 'import EvidenceWorkbench from "./components/EvidenceWorkbench";'


def stop(message: str) -> None:
    sys.exit("ERROR: " + message + "\nNo source files were modified.")


if not TARGET.is_file() or not COMPONENT.is_file():
    stop("FreeShowcase.tsx or EvidenceWorkbench.tsx is missing. Extract Chunk 12C into the project root.")

original = TARGET.read_text(encoding="utf-8-sig")
source = original
if IMPORT_LINE in source and re.search(r"<EvidenceWorkbench\b", source):
    print("Already installed: EvidenceWorkbench import and component found. No changes made.")
    sys.exit(0)
if IMPORT_LINE in source or re.search(r"<EvidenceWorkbench\b", source):
    stop("Only part of Chunk 12C seems installed. Please upload your current FreeShowcase.tsx for a tailored fix.")

# The lab is designed for the Chunk 12B dashboard event callback.
for symbol in ("recordEvent", "isCurrent", "intent"):
    if not re.search(r"\b" + re.escape(symbol) + r"\b", source):
        stop(f"Expected variable {symbol!r} was not found in your dashboard. Please upload FreeShowcase.tsx.")

# The header of the existing DecisionSpotlight is a stable import anchor.
import_match = re.search(
    r'^[ \t]*import[ \t]+DecisionSpotlight[ \t]+from[ \t]+[\'\"]\./components/DecisionSpotlight[\'\"];?[ \t]*$',
    source,
    flags=re.MULTILINE,
)
if not import_match:
    stop("Could not identify the DecisionSpotlight import. Please upload FreeShowcase.tsx.")

# Find section independently of its Tailwind classes, attribute order, or whitespace.
section_matches = list(re.finditer(
    r'<section\b(?=[^>]*\bid[ \t]*=[ \t]*[\'\"]adaptive-demo[\'\"])[^>]*>',
    source,
    flags=re.DOTALL,
))
if len(section_matches) != 1:
    stop(f"Expected one section with id='adaptive-demo'; found {len(section_matches)}. Please upload FreeShowcase.tsx.")

# Insert imported component before the original adaptive simulation.
source = source[:import_match.end()] + "\n" + IMPORT_LINE + source[import_match.end():]
section_matches = list(re.finditer(
    r'<section\b(?=[^>]*\bid[ \t]*=[ \t]*[\'\"]adaptive-demo[\'\"])[^>]*>',
    source,
    flags=re.DOTALL,
))
section = section_matches[0]
line_start = source.rfind("\n", 0, section.start()) + 1
indent = re.match(r"[ \t]*", source[line_start:]).group(0)
block = (
    f"{indent}<EvidenceWorkbench\n"
    f"{indent}  requestedProduct={{isCurrent && intent ? intent.requested_product : null}}\n"
    f"{indent}  extractedBudget={{isCurrent && intent ? intent.budget_amount : null}}\n"
    f"{indent}  onEvent={{recordEvent}}\n"
    f"{indent}/>\n\n"
)
# The expected <section> must be at the start of an indented line to avoid damaging JSX.
if source[line_start:section.start()].strip():
    stop("The adaptive-demo section is not on its own line; please upload FreeShowcase.tsx.")
source = source[:line_start] + block + source[line_start:]

# Add links based on navigation containers, not exact <a> classes.
nav_links_added = 0
for label, link in (
    (
        "Showcase workspace",
        '<a href="#evidence-workbench" className="flex items-center rounded-lg border border-sky-500/25 bg-sky-500/5 px-3 py-3 text-xs text-sky-200 hover:bg-sky-500/10">Evidence Intelligence</a>',
    ),
    (
        "Mobile showcase navigation",
        '<a href="#evidence-workbench" className="shrink-0 rounded-lg border border-sky-500/30 bg-sky-500/5 px-3 py-2 text-xs text-sky-200">Evidence Lab</a>',
    ),
):
    pat = r'<nav\b(?=[^>]*\baria-label\s*=\s*[\'\"]' + re.escape(label) + r'[\'\"])[^>]*>'
    matches = list(re.finditer(pat, source, flags=re.DOTALL | re.IGNORECASE))
    if len(matches) == 1:
        n = matches[0]
        # Indent to match child elements, but don't rely on a specific element's formatting.
        line_start_nav = source.rfind("\n", 0, n.start()) + 1
        nav_indent = re.match(r"[ \t]*", source[line_start_nav:]).group(0)
        insertion = "\n" + nav_indent + "  " + link
        source = source[:n.end()] + insertion + source[n.end():]
        nav_links_added += 1
    elif len(matches) > 1:
        stop(f"Multiple navigation regions called {label!r} found. Please upload FreeShowcase.tsx.")

# Backup original before making any changes, then replace atomically.
backup_dir = ROOT / "backup_12c"
backup_dir.mkdir(parents=True, exist_ok=True)
backup_path = backup_dir / "FreeShowcase.before_chunk12c.tsx"
if backup_path.exists():
    stop(f"Backup already exists at {backup_path}; refusing to overwrite it.")
shutil.copy2(TARGET, backup_path)
temp_path = TARGET.with_name(TARGET.name + ".12c.tmp")
try:
    temp_path.write_text(source, encoding="utf-8")
    os.replace(temp_path, TARGET)
except Exception:
    if temp_path.exists():
        temp_path.unlink()
    raise

print("SUCCESS: Evidence Intelligence Workbench installed.")
print(f"Sidebar/mobile navigation links added: {nav_links_added}/2")
if nav_links_added < 2:
    print("NOTE: Some navigation labels differ. The workbench is still added; it can be reached by scrolling.")
print("Original backed up to: " + str(backup_path))
print("Next: cd frontend && npm run build")
