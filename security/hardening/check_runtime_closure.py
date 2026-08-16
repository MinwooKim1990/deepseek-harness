#!/usr/bin/env python3
"""Fail when a hardened production root reaches a blocked workspace package."""
from __future__ import annotations

import json
import sys
from collections import deque
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
BLOCKED = {
    "@deepseek-ai/dsh-session-telemetry",
    "@deepseek-ai/dsh-session-telemetry-otel",
    "@deepseek-ai/dsh-anonymous-user-id",
    "@deepseek-ai/dsh-command-feedback",
    "@deepseek-ai/dsh-cordis-host-runner",
    "@deepseek-ai/dsh-cordis-client-runner",
    "@deepseek-ai/dsh-client-ui-cordis",
    "@deepseek-ai/dsh-tool-cordis",
    "@deepseek-ai/dsh-workflow-worker-thread",
    "@deepseek-ai/dsh-tool-workflow",
    "@deepseek-ai/dsh-tool-ralph",
    "@deepseek-ai/dsh-client-ui-workflow-run",
    "@deepseek-ai/dsh-code-runtime-worker-thread",
    "@deepseek-ai/dsh-mcp-client",
    "@deepseek-ai/dsh-llm-pi-ai",
}
ROOT_MANIFESTS = ["apps/cli/package.json", "python/sdk-runtime/package.json"]
SECTIONS = ("dependencies", "optionalDependencies", "peerDependencies")


def load_manifest(path: Path) -> dict[str, object]:
    return json.loads(path.read_text())


manifests: dict[str, tuple[Path, dict[str, object]]] = {}
patterns = ("vendor/*/package.json", "packages/*/*/package.json", "apps/*/package.json", "python/sdk-runtime/package.json")
for pattern in patterns:
    for path in ROOT.glob(pattern):
        data = load_manifest(path)
        name = data.get("name")
        if isinstance(name, str):
            manifests[name] = (path, data)

errors: list[str] = []
for rel in ROOT_MANIFESTS:
    root_path = ROOT / rel
    root_data = load_manifest(root_path)
    root_name = root_data.get("name")
    if not isinstance(root_name, str):
        errors.append(f"{rel}: missing package name")
        continue

    queue: deque[str] = deque([root_name])
    parent: dict[str, str | None] = {root_name: None}
    while queue:
        current = queue.popleft()
        entry = manifests.get(current)
        if entry is None:
            continue
        _, data = entry
        for section in SECTIONS:
            deps = data.get(section, {})
            if not isinstance(deps, dict):
                continue
            for dep in deps:
                if dep not in manifests or dep in parent:
                    continue
                parent[dep] = current
                queue.append(dep)

    for blocked in sorted(BLOCKED & set(parent)):
        chain = [blocked]
        ancestor = parent[blocked]
        while ancestor is not None:
            chain.append(ancestor)
            ancestor = parent[ancestor]
        chain.reverse()
        errors.append(f"{rel}: blocked production dependency path: {' -> '.join(chain)}")

if errors:
    print("HARDENED_CLOSURE_FAIL")
    for error in errors:
        print(error)
    raise SystemExit(1)

print("HARDENED_CLOSURE_PASS")
