"""Repo-root shim for the composite GitHub Action."""

from keel.action.drift_check import main

if __name__ == "__main__":
    raise SystemExit(main())
