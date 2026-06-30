# Phase 61.2 JSON Serialization Fix

Fixes `/mikrotik/data/` JSON serialization after Phase 61 by removing Django model objects from `insight_dashboard` and `action_items` before `JsonResponse`.

No migration. No database change. No RouterOS change. No credential change.
