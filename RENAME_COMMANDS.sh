#!/bin/bash
# Run this from your project root to fix all the _hardened/_clean naming mismatches.
# This makes every import statement in your codebase actually resolve.

cd backend/app

# main.py is the canonical name — Dockerfile and uvicorn command expect it
git mv main_hardened.py main.py 2>/dev/null || mv main_hardened.py main.py

cd routers
git mv auth_hardened.py auth.py 2>/dev/null || mv auth_hardened.py auth.py
git mv community_clean.py community.py 2>/dev/null || mv community_clean.py community.py

cd ../models
git mv schemas_hardened.py schemas.py 2>/dev/null || mv schemas_hardened.py schemas.py

cd ../../../..
echo "Renamed. Now fixing import references inside files..."

# Fix the two test files that reference the old _hardened name
sed -i 's/app\.models\.schemas_hardened/app.models.schemas/g' backend/tests/test_all.py
sed -i 's/app\.main_hardened/app.main/g' backend/tests/test_integration.py

# Add community router import + registration to main.py
sed -i 's/from app.routers import auth, carbon, predictions, tips, insights/from app.routers import auth, carbon, predictions, tips, insights, community/' backend/app/main.py
sed -i '/app.include_router(insights.router/a app.include_router(community.router, prefix="\/api\/community", tags=["Community"])' backend/app/main.py

echo "Done. Verifying no broken imports remain:"
grep -rn "_hardened\|community_clean" backend/ --include="*.py" || echo "✅ Clean — no stale references found"
