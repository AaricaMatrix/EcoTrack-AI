#!/usr/bin/env python3
"""
Run this from your project root with: python fix_imports.py

Fixes the _hardened/_clean naming mismatches by:
1. Renaming the physical files to their canonical names
2. Fixing every import statement across the codebase that points to old names
3. Wiring the community router into main.py

Works on Windows, macOS, and Linux — no shell-specific commands.
"""

import os
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))

# ── Step 1: Rename files to canonical names ───────────────────────────────────
RENAMES = [
    ("backend/app/main_hardened.py",              "backend/app/main.py"),
    ("backend/app/routers/auth_hardened.py",       "backend/app/routers/auth.py"),
    ("backend/app/routers/community_clean.py",     "backend/app/routers/community.py"),
    ("backend/app/models/schemas_hardened.py",     "backend/app/models/schemas.py"),
]

print("=" * 60)
print("STEP 1: Renaming files")
print("=" * 60)

for src, dst in RENAMES:
    src_path = os.path.join(ROOT, src)
    dst_path = os.path.join(ROOT, dst)
    if os.path.exists(src_path):
        if os.path.exists(dst_path):
            os.remove(dst_path)   # overwrite stale old-named file if present
        shutil.move(src_path, dst_path)
        print(f"  ✅ {src} -> {dst}")
    elif os.path.exists(dst_path):
        print(f"  ⏭  {dst} already correct (source not found, skipping)")
    else:
        print(f"  ⚠️  NEITHER {src} NOR {dst} found — check manually")

# ── Step 2: Fix import references in every .py file ──────────────────────────
print("\n" + "=" * 60)
print("STEP 2: Fixing import statements")
print("=" * 60)

REPLACEMENTS = [
    ("app.models.schemas_hardened", "app.models.schemas"),
    ("app.main_hardened",           "app.main"),
    ("app.routers.auth_hardened",   "app.routers.auth"),
    ("app.routers.community_clean", "app.routers.community"),
]

py_files = []
for dirpath, _, filenames in os.walk(os.path.join(ROOT, "backend")):
    if "__pycache__" in dirpath or ".pytest_cache" in dirpath:
        continue
    for f in filenames:
        if f.endswith(".py"):
            py_files.append(os.path.join(dirpath, f))

changed_files = []
for filepath in py_files:
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    original = content
    for old, new in REPLACEMENTS:
        content = content.replace(old, new)
    if content != original:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        rel = os.path.relpath(filepath, ROOT)
        changed_files.append(rel)
        print(f"  ✅ Fixed imports in {rel}")

if not changed_files:
    print("  (no files needed import fixes)")

# ── Step 3: Wire community router into main.py ────────────────────────────────
print("\n" + "=" * 60)
print("STEP 3: Registering community router in main.py")
print("=" * 60)

main_path = os.path.join(ROOT, "backend/app/main.py")
if os.path.exists(main_path):
    with open(main_path, "r", encoding="utf-8") as f:
        main_content = f.read()

    old_import = "from app.routers import auth, carbon, predictions, tips, insights"
    new_import = "from app.routers import auth, carbon, predictions, tips, insights, community"

    if old_import in main_content and "community" not in main_content.split(old_import)[0]:
        main_content = main_content.replace(old_import, new_import)
        print("  ✅ Added community to router imports")
    elif "import community" in main_content or ", community" in main_content:
        print("  ⏭  community already imported")
    else:
        print("  ⚠️  Could not find expected import line — check main.py manually")

    if 'app.include_router(community.router' not in main_content:
        marker = 'app.include_router(insights.router,    prefix="/api/insights",    tags=["AI Insights"])'
        if marker in main_content:
            replacement = marker + '\napp.include_router(community.router,   prefix="/api/community",   tags=["Community"])'
            main_content = main_content.replace(marker, replacement)
            print("  ✅ Registered community router with app.include_router()")
        else:
            print("  ⚠️  Could not find insights router line to anchor community registration — add manually")
    else:
        print("  ⏭  community router already registered")

    with open(main_path, "w", encoding="utf-8") as f:
        f.write(main_content)
else:
    print("  ❌ backend/app/main.py not found — rename step may have failed")

# ── Step 4: Verify no stale references remain ─────────────────────────────────
print("\n" + "=" * 60)
print("STEP 4: Verifying no stale references remain")
print("=" * 60)

stale_found = False
for filepath in py_files:
    # Re-walk since filenames may have changed; just check remaining content
    if not os.path.exists(filepath):
        continue
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
    for old, _ in REPLACEMENTS:
        if old in content:
            rel = os.path.relpath(filepath, ROOT)
            print(f"  ❌ STILL CONTAINS '{old}': {rel}")
            stale_found = True

if not stale_found:
    print("  ✅ Clean — no stale _hardened/_clean references found")

print("\n" + "=" * 60)
print("DONE. Next steps:")
print("=" * 60)
print("  1. cd backend && pytest tests/ -v --tb=short")
print("  2. If green: git add -A && git commit -m 'fix: resolve naming mismatches' && git push origin main")
print("  3. git push hfspace main --force")
