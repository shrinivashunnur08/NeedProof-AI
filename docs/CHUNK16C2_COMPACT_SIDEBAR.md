# NeedProof 16C.2 — Premium single-screen sidebar (no scrollbar)

This redesign replaces the previous tall left navigation with a clean, compact 240px sidebar that fits inside the desktop viewport. It keeps all navigation, groups optional local capabilities into neat chips, and docks a concise Firebase card at the bottom. On **desktop windows shorter than 650 CSS pixels**, explanatory local-module content is hidden to preserve navigation access; below 550px the navigation tightens slightly; below 480px the footer's secondary line collapses. The **sidebar has no scrollbar**. Mobile navigation is preserved.

The patch accepts either of the two audited versions: original 16C.2 (`56a81b7` descendant) or the previous sidebar scrollbar fix. All other `FreeShowcase.tsx` variations are rejected so custom work cannot be silently overwritten.

## Windows CMD — install

Extract this ZIP into `D:\AiBuilderCup\needproof-ai`. From project root:

```cmd
cd /d D:\AiBuilderCup\needproof-ai
call backend\.venv\Scripts\activate.bat
python scripts\apply_16c2_compact_sidebar.py --check
python scripts\apply_16c2_compact_sidebar.py --apply
scripts\verify_16c2_compact_sidebar.cmd
```

If verification passes, preview in a new CMD window:

```cmd
cd /d D:\AiBuilderCup\needproof-ai\frontend
set VITE_PUBLIC_SHOWCASE=true
npm run dev
```

Visit `http://localhost:5173/` and visually check at desktop window heights 900, 768, 650, 550 and 480 CSS pixels (via developer tools), and mobile widths. All essential links should remain visible, the local modules may disappear on unusually short windows, and the Firebase card stays visible. The main page itself can still scroll naturally. No left sidebar scrollbar.

**Important:** If Vite says a port is in use it may choose another local URL; use the URL printed by Vite. The existing React page may initialize Firebase separately; for a completely offline replay use the standalone offline demo HTML.

## Commit after success (from repo root)

```cmd
git diff --check
git add frontend/src/FreeShowcase.tsx backend/tests/test_compact_sidebar_16c2.py scripts/apply_16c2_compact_sidebar.py scripts/verify_16c2_compact_sidebar.cmd docs/CHUNK16C2_COMPACT_SIDEBAR.md
git diff --cached --check
git diff --cached --stat
git commit -m "Polish NeedProof desktop sidebar into single-screen layout"
git push origin main
```

Do **not** use `git add .`. Keep old scratch utilities and backups unstaged.

## Limits

This is a static CSS/layout improvement. It does not validate every possible OS scaling, browser zoom, language expansion, accessibility text enlargement or device configuration. At unusually small desktop heights, secondary capability explanations are intentionally hidden. If you want *all* text visible at any height, a no-scroll sidebar is geometrically impossible. The important navigation links are preserved.

The patch changes only `frontend/src/FreeShowcase.tsx`, creates an untouched backup under `backup_16c2_compact_sidebar`, and does not deploy or change cloud flags.
