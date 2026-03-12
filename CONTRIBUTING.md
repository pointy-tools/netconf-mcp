# Contributing

Thanks for your interest in improving `netconf-mcp`.

## Getting started

1. Install dependencies:

```bash
python -m pip install -e '.[dev]'
```

2. Run the test suite:

```bash
python -m pytest -q
```

3. Make focused changes with tests when practical.

## Development guidelines

- Keep read-only and live-device safety constraints intact.
- Prefer vendor-aware domain views over broad raw datastore reads when adding new user-facing workflows.
- Treat NETCONF-returned values as authoritative structured data and quote them verbatim in summaries.
- Do not add production write behavior without explicit safety and review controls.

## Pull requests

- Include a short description of the change and why it matters.
- Call out any live-device assumptions or limitations.
- Mention test coverage or manual verification performed.
