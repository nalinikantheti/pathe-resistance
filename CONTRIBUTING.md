# Contributing to PathéResistance

Small, reusable changes are welcome. Explain the use case and keep file acquisition, feature calculation, cost modeling and presentation separate.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,map]'
ruff check .
pytest -q
python -m build
```

Tests must run without network access, downloaded model weights or private data. Use small synthetic georeferenced fixtures. Include a regression test when changing units, missing-data behavior, parallel-edge selection or route objectives.

## Design rules

- No hardcoded city, absolute project paths, credentials or work started at import.
- Preserve unknown data and per-feature coverage. Do not substitute zero or a favorable cost silently.
- Use meters for physical buffers/lengths. Declare rasters' units and scale exactly once.
- Keep costs finite and nonnegative; compare routes on identical feature support.
- Document any model, normalization reference, assumed coefficient or fallback.
- Do not bundle large data, imagery, model weights or generated maps in Git.
- Update the quickstart when changing public APIs or configuration keys.

Use GitHub issues for reproducible bugs and proposed extensions. Include the package version, OS/Python versions, command, traceback and a minimal synthetic example; redact private paths or data when appropriate. A pull request should describe the behavioral change and checks run.
