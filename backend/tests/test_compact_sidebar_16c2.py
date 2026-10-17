"""NeedProof 16C.2 compact sidebar layout contract tests."""
from pathlib import Path
import hashlib
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
SRC = (ROOT / "frontend/src/FreeShowcase.tsx").read_text(encoding="utf-8")
SIDEBAR = SRC[SRC.index("      <aside"):SRC.index("</aside>") + len("</aside>")]


def test_single_sidebar_and_full_viewport_height():
    assert SRC.count('aria-label="NeedProof workspace sidebar"') == 1
    assert "lg:h-dvh" in SIDEBAR and "lg:sticky" in SIDEBAR and "lg:top-0" in SIDEBAR


def test_no_left_sidebar_scrollbar():
    assert "overflow-hidden" in SIDEBAR
    for bad in ("overflow-y-scroll", "overflow-y-auto", "scrollbar-gutter", "overscroll-y-contain"):
        assert bad not in SIDEBAR


def test_all_primary_navigation_is_available():
    for destination in ("#judge-replay-16c2", "#real-store-discovery", "#evidence-workbench", "#customer-request", "#adaptive-demo", "#journey-history"):
        assert f'href="{destination}"' in SIDEBAR
    assert "evidence13bEnabled &&" in SIDEBAR
    assert '#merchant-evidence-desk' in SIDEBAR


def test_design_is_compact_with_responsive_short_window_fallback():
    assert 'min-h-[36px]' in SIDEBAR
    assert 'gap-1.5' in SIDEBAR
    assert '[@media(max-height:650px)]:hidden' in SIDEBAR
    assert '[@media(max-height:550px)]:min-h-[32px]' in SIDEBAR
    assert '[@media(max-height:480px)]:hidden' in SIDEBAR


def test_merchant_disclaimer_and_firebase_status_remain():
    assert 'Merchant operations require local FastAPI' in SIDEBAR
    assert 'Firebase Spark Showcase' in SIDEBAR
    assert 'Merchant claims unverified' in SIDEBAR
    assert 'mt-auto shrink-0' in SIDEBAR


def test_mobile_nav_and_core_demo_untouched():
    assert 'Mobile showcase navigation' in SRC
    assert 'lg:hidden' in SRC
    assert '<JudgeReplay16C2 />' in SRC
    assert SRC.count('export default function FreeShowcase()') == 1


def test_source_integrity_expected_patch():
    canonical = SRC.replace('\r\n', '\n')
    assert hashlib.sha256(canonical.encode('utf-8')).hexdigest() == '2bbc2e5d2da52765d113758265a8242338e6dfed4c9646f643a76ece9beeb35d'


def test_installer_idempotent():
    p = subprocess.run([sys.executable, str(ROOT/'scripts/apply_16c2_compact_sidebar.py'), '--check'], capture_output=True, text=True, cwd=ROOT)
    assert p.returncode == 0 and 'already installed' in p.stdout
