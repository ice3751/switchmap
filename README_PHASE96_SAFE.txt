SwitchMap Phase96 — Model Index Metadata Alignment

Scope:
- Align inventory/models.py Meta.indexes with already-applied Phase77 migration 0018 indexes.
- Add read-only management guard: phase96_model_index_alignment_check.

No DB migration is created.
No migration is executed.
No service restart.
No SSH.
No restore.
No backup write.
No UI/menu/device/test data change.

Run:
cd /d C:\SwitchMap
scripts\96_phase96_model_index_metadata_alignment.cmd
