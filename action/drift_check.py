"""Repo-root shim for the composite GitHub Action.

GitHub Actions looks for action/drift_check.py at the repository root.
This file forwards to the real implementation in keel.action.drift_check.
"""

from keel.action.drift_check import main

if __name__ == "__main__":
    raise SystemExit(main())
