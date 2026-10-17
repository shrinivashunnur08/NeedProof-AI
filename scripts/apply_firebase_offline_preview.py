#!/usr/bin/env python3
"""NeedProof offline Firebase preview display fix. Local source-only edit."""
from __future__ import annotations
import argparse, hashlib, pathlib, sys
BASE = pathlib.Path(__file__).resolve().parent.parent
SOURCE_HASHES = {'frontend/src/FreeShowcase.tsx': '2bbc2e5d2da52765d113758265a8242338e6dfed4c9646f643a76ece9beeb35d', 'frontend/src/lib/cloudDecisions.ts': 'fdbc5beb8a23f5ad9b3bd6f545371bbe854db70dc4c7f6025751661aee9185ec'}
RESULT_HASHES = {'frontend/src/lib/cloudDecisions.ts': 'cda32ffb32851301f85ddb1937a596f900db77e1ff9d49bbdea2c281fb2f2024', 'frontend/src/FreeShowcase.tsx': '0f74af8ec4c81a23468ce2ac2875d5d9f862464b82e473c925ab88e4f1abf190'}


def normalized(text: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n")


def hash_text(text: str) -> str:
    return hashlib.sha256(normalized(text).encode("utf-8")).hexdigest()


def swap_once(text: str, old: str, new: str) -> str:
    count = text.count(old)
    if count != 1:
        raise ValueError(f"Expected one audited occurrence; found {count}")
    return text.replace(old, new, 1)


def patch_cloud(text: str) -> str:
    text = swap_once(text, 'export function firebaseShowcaseClients(): Clients {', '/** Check required public web-client configuration without contacting Firebase. */\nexport function firebaseShowcaseConfigured(): boolean {\n  return Boolean(\n    import.meta.env.VITE_FIREBASE_PROJECT_ID &&\n    import.meta.env.VITE_FIREBASE_API_KEY &&\n    import.meta.env.VITE_FIREBASE_APP_ID &&\n    import.meta.env.VITE_APPCHECK_SITE_KEY\n  );\n}\n\nexport function firebaseShowcaseClients(): Clients {')
    text = swap_once(text,'throw new Error("Firebase configuration is incomplete. Check .env.production.local.");', 'throw new Error("Firebase web configuration is incomplete. Configure this Vite environment before using Gemini or Firestore.");')
    return text


def patch_showcase(text: str) -> str:
    transforms = [('  cloudApiUrl,\n  getShowcaseGeminiModel,', '  cloudApiUrl,\n  firebaseShowcaseConfigured,\n  getShowcaseGeminiModel,'), ('  const remoteEnabled = cloudApiUrl.length > 0;', '  const firebaseReady = firebaseShowcaseConfigured();\n  const remoteEnabled = cloudApiUrl.length > 0;'), ('  const [storeStatus, setStoreStatus] = useState("Checking saved journey...");', '  const [storeStatus, setStoreStatus] = useState(\n    firebaseReady\n      ? "Checking saved journey..."\n      : "Offline preview · Firebase journey saving is not configured."\n  );'), ('  useEffect(() => {\n    let alive = true;\n    loadJourney()', '  useEffect(() => {\n    // No Firebase calls or authentication prompts in the unconfigured offline preview.\n    if (!firebaseReady) return;\n    let alive = true;\n    loadJourney()'), ('  }, []);\n\n  useEffect(() => {\n    if (!loading)', '  }, [firebaseReady]);\n\n  useEffect(() => {\n    if (!loading)'), ('<CheckCircle2 size={13} /> Firebase showcase', '<CheckCircle2 size={13} /> {firebaseReady ? "Firebase configured" : "Offline preview"}'), ('<Sparkles size={13} /> Gemini via Firebase AI Logic', '<Sparkles size={13} /> {firebaseReady ? "Gemini via Firebase AI Logic" : "Offline evidence walkthrough"}'), ('Live customer-intent intelligence with a separate, fictional\n              merchant decision scenario.', '{firebaseReady\n                ? "Firebase-powered intent analysis with a separate fictional merchant scenario."\n                : "Explore the evidence decisions offline. Live Gemini and saved journeys require Firebase configuration."}'), ('<Sparkles size={13} className="text-sky-400" /> Firebase Spark Showcase', '<Sparkles size={13} className="text-sky-400" /> {firebaseReady ? "Firebase Spark Showcase" : "Offline Judge Preview"}'), ('Gemini via Firebase · Cloud decisions opt-in · Merchant claims unverified', '{firebaseReady ? "Gemini via Firebase · Cloud decisions opt-in · Merchant claims unverified" : "Synthetic decision replay · No Firebase connection"}'), ('<Clock3 size={16} className="text-sky-400" /> Firestore\n                  Journey History', '<Clock3 size={16} className="text-sky-400" /> {firebaseReady ? "Firestore Journey History" : "Journey Timeline · Offline Preview"}'), ("Private to this browser's Firebase anonymous account. Save\n                  only when you choose; no writing on every keystroke.", '{firebaseReady\n                    ? "Private to this browser\'s Firebase anonymous account. Save only when you choose; no writing on every keystroke."\n                    : "Events remain in this page session. Firebase saving is unavailable until the web app is configured."}'), ('Extract with Gemini or start a demo; then Save journey to\n                    preserve the events in Firestore.', '{firebaseReady\n                      ? "Extract with Gemini or start a demo; then Save journey to preserve events in Firestore."\n                      : "Start the fictional guided demo to explore decisions. Session events are not saved to Firestore in offline preview."}'), ('Live Gemini interpretation · No fabricated merchant facts', '{firebaseReady ? "Live Gemini interpretation · No fabricated merchant facts" : "Gemini is not connected · Offline decision demo available"}'), ('disabled={loading || request.trim().length < 8}', 'disabled={!firebaseReady || loading || request.trim().length < 8}'), (': "Extract with live Gemini"}', ': firebaseReady ? "Extract with live Gemini" : "Gemini not configured"}'), ('This request is analyzed by Gemini. Merchant inventory,\n                authenticity, delivery and prices are not checked by the AI\n                extraction.', '{firebaseReady\n                  ? "This request is analyzed by Gemini. Merchant inventory, authenticity, delivery and prices are not checked by AI extraction."\n                  : "Offline preview: Gemini extraction is unavailable. Use Start guided demo for the engine-derived fictional walkthrough."}'), ('Submit the request to see structured requirements and\n                    missing information.', '{firebaseReady\n                      ? "Submit the request to see structured requirements and missing information."\n                      : "Configure Firebase to enable AI extraction, or explore the offline guided evidence replay above."}')]
    for old, new in transforms:
        text = swap_once(text, old, new)
    if text.count('disabled={storeBusy}') != 3:
        raise ValueError("Could not verify three journey action buttons")
    return text.replace('disabled={storeBusy}', 'disabled={storeBusy || !firebaseReady}')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--check', action='store_true')
    group.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    source = {}
    for rel in SOURCE_HASHES:
        path = BASE / rel
        if not path.is_file():
            raise RuntimeError(f"Missing source file: {rel}")
        text = path.read_text(encoding='utf-8')
        digest = hash_text(text)
        if digest not in (SOURCE_HASHES[rel], RESULT_HASHES[rel]):
            raise RuntimeError(f"Source has changed unexpectedly: {rel}. No edits applied; ask for a refreshed patch.")
        source[rel] = (path, text, digest)
    if all(digest == RESULT_HASHES[rel] for rel, (_, _, digest) in source.items()):
        print('PASS: Offline Firebase preview UI is already installed. No changes.')
        return 0
    if not all(digest == SOURCE_HASHES[rel] for rel, (_, _, digest) in source.items()):
        raise RuntimeError('Partially applied sources detected. No edits made.')
    updated = {}
    for rel, (_, old, _) in source.items():
        new = patch_showcase(old) if rel.endswith('/FreeShowcase.tsx') else patch_cloud(old)
        if hash_text(new) != RESULT_HASHES[rel]:
            raise RuntimeError(f"Internal patch integrity error: {rel}")
        updated[rel] = new
    if args.check:
        print('PASS: Source matches audited 16C.4 baseline; offline-preview Firebase UX fix is safe to apply.')
        print('DRY RUN: Would adjust only FreeShowcase.tsx and cloudDecisions.ts, without network or deployments.')
        return 0
    backup = BASE / 'backup_firebase_offline_preview'
    backup.mkdir(exist_ok=True)
    for rel,(path,old,_) in source.items():
        dest = backup / path.name
        if dest.exists():
            raise RuntimeError(f"Backup already exists: {dest}. No edits made.")
    for rel,(path,old,_) in source.items():
        (backup / path.name).write_text(old, encoding='utf-8')
    for rel,(path,old,_) in source.items():
        path.write_text(updated[rel], encoding='utf-8', newline='\n')
    print('SUCCESS: Unconfigured Firebase is now presented as a deliberate offline preview.')
    print('Firestore/Gemini actions disabled only when required configuration is missing.')
    print('Backup:',backup)
    print('No Firebase tokens, cloud calls, flags, project settings or deployments changed.')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, ValueError, RuntimeError, UnicodeError) as ex:
        print('ERROR:',ex, file=sys.stderr)
        sys.exit(1)
