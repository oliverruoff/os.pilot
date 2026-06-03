# OSPilot

OSPilot is a macOS menu-bar/background cursor companion for `pi-coding-agent`.

This repository contains the MVP scaffold from `SPEC.md`: a Python/PySide6 desktop shell, a JSON-RPC bridge to `pi`, a local authenticated IPC server for desktop tools, and a TypeScript pi extension.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
ospilot
```

Set provider/model configuration the same way you would for `pi` directly, for example:

```bash
export PI_ARGS="--model provider/model"
```

## Test

```bash
pip install -e '.[dev]'
pytest
```
