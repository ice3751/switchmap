# Phase 67 - Office Port Labels Import

Source PDF: جانمایی و آدرس دهی تجهیزات رک_۱۰۵۷۲۷-1.pdf

Scope:
- Page 1 -> Edari-1
- Page 2 -> Edari-2
- Page 3 -> Edari-4 (corrected by user)
- Page 4 -> Edari-3 (corrected by user)
- Page 5 -> Edari-6
- Page 6 -> Edari-5 / company cameras

Only the leading label is imported, e.g. `T1-Z1-R1-P1.1-PO1` becomes `T1`.

Updated field by default: `Port.description`.

Summary:
- Edari-1: 48 labels, missing ports left unchanged: none
- Edari-2: 42 labels, missing ports left unchanged: [18, 19, 35, 46, 47, 48]
- Edari-3: 46 labels, missing ports left unchanged: [37, 38]
- Edari-4: 34 labels, missing ports left unchanged: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]
- Edari-5: 45 labels, missing ports left unchanged: [14, 28, 39]
- Edari-6: 19 labels, missing ports left unchanged: [4, 7, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48]

Rollback: restore the SQLite backup printed as `PHASE67_DB_BACKUP` or restore the full folder backup printed by the apply script.
