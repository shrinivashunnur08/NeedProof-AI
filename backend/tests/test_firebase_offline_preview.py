from pathlib import Path
import importlib.util
import pytest

ROOT=Path(__file__).resolve().parents[2]
SCRIPT=ROOT/'scripts'/'apply_firebase_offline_preview.py'
spec=importlib.util.spec_from_file_location('offline_patch',SCRIPT)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def test_source_state_is_complete():
    hashes=[]
    for rel in module.SOURCE_HASHES:
        s=(ROOT/rel).read_text(encoding='utf-8')
        hashes.append(module.hash_text(s)==module.RESULT_HASHES[rel])
    assert hashes==[True,True], 'Apply the guarded patch first'

def test_firebase_config_not_bypassed():
    text=(ROOT/'frontend/src/lib/cloudDecisions.ts').read_text(encoding='utf-8')
    for env in ('VITE_FIREBASE_PROJECT_ID','VITE_FIREBASE_API_KEY','VITE_FIREBASE_APP_ID','VITE_APPCHECK_SITE_KEY'):
        assert env in text
    assert 'ReCaptchaEnterpriseProvider(siteKey)' in text
    assert 'getToken(appCheck)' in text
    assert 'signInAnonymously(auth)' in text

def test_offline_skips_initial_firestore_call():
    text=(ROOT/'frontend/src/FreeShowcase.tsx').read_text(encoding='utf-8')
    assert 'if (!firebaseReady) return;' in text
    assert 'loadJourney()' in text
    assert 'Offline preview · Firebase journey saving is not configured.' in text

def test_all_journey_actions_disabled_until_configured():
    text=(ROOT/'frontend/src/FreeShowcase.tsx').read_text(encoding='utf-8')
    assert text.count('disabled={storeBusy || !firebaseReady}')==3
    for action in ('saveCurrentJourney()', 'restoreSavedJourney()', 'removeSavedJourney()'):
        assert action in text

def test_gemini_not_faked_or_connected_in_offline():
    text=(ROOT/'frontend/src/FreeShowcase.tsx').read_text(encoding='utf-8')
    assert 'disabled={!firebaseReady || loading || request.trim().length < 8}' in text
    assert 'Gemini not configured' in text
    assert 'getShowcaseGeminiModel().generateContent(prompt)' in text

def test_replay_and_no_purchase_not_modified():
    text=(ROOT/'frontend/src/FreeShowcase.tsx').read_text(encoding='utf-8')
    assert '<JudgeReplay16C2 />' in text
    assert 'purchase_allowed: false' in text
    assert 'CLIENT_SNAPSHOT_REPLANNING' in text

def test_patch_integrity_is_idempotent():
    for rel in module.SOURCE_HASHES:
        txt=(ROOT/rel).read_text(encoding='utf-8')
        assert module.hash_text(txt)==module.RESULT_HASHES[rel]
