"""Frozen Sports Event OS v1.0 code: the single-document model, its quality gate, revenue engine,
versioning, exporters and CLI (`sports-os --legacy ...`), plus the explicit v1.0 → modular adapter.

The modular kernel (``sports_os.kernel``), business modules (``sports_os.modules``) and the desktop sidecar
never import this package at import time. ``sports_os.application`` reaches it lazily for three explicit
operations only: ``--legacy`` CLI, ``migrate-v10`` and generating the demo (built from the v1.0 demo via
the adapter, so both formats describe the same fictional event).
"""
