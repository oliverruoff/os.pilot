# OSPilot

OSPilot is a macOS/Windows desktop cursor companion for `pi-coding-agent`.

This repository contains a Python/PySide6 desktop shell, a JSON-RPC bridge to `pi`, a local authenticated IPC server for desktop tools, TypeScript pi tool extensions, and a drop-in pi skills folder.

## Structure

```text
src/ospilot/desktop/macos/    macOS desktop implementation
src/ospilot/desktop/windows/  Windows desktop stubs/implementation
pi/tools/                     TypeScript pi tool extensions
pi/skills/                    Referenced pi skills drop-in folder
```

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
