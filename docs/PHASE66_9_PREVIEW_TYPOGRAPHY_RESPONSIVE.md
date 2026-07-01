# Phase 66.9 - Dashboard Preview Typography and Responsive Polish

Scope:
- Preview page only: `/dashboard-preview/`
- No backend, database, SNMP, SSH or production dashboard logic changes.

Changed:
- Persian-first font stack.
- Cleaner top navigation visual treatment.
- Better card text scale.
- Responsive 2x2 card grid with growing rows instead of broken fixed-height cards.
- No internal card scroll.

Touched files:
- inventory/templates/inventory/dashboard_visual_preview.html
- inventory/static/inventory/css/dashboard-visual-preview.css
- smoke_tests/switchmap_66_9_preview_typography_responsive_smoke_test.py
