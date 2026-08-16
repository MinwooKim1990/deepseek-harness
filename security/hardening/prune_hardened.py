#!/usr/bin/env python3
"""Prune risky packages from the already-built production closure."""
from __future__ import annotations
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
risky = {
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
manifests = [
    "apps/cli/package.json",
    "packages/api/remotes/package.json",
    "packages/bundle/base/package.json",
    "packages/bundle/web-app/package.json",
    "packages/bundle/headless/package.json",
    "packages/llm/llm-deepseek/package.json",
    "packages/host/apiproxy/package.json",
    "python/sdk-runtime/package.json",
]
removed: list[str] = []
for rel in manifests:
    path = root / rel
    data = json.loads(path.read_text())
    for section in ("dependencies", "optionalDependencies", "peerDependencies"):
        deps = data.get(section)
        if not isinstance(deps, dict):
            continue
        for name in sorted(set(deps) & risky):
            del deps[name]
            removed.append(f"{rel}:{section}:{name}")
    path.write_text(json.dumps(data, indent=2) + "\n")

manifest_path = root / "HARDENING-MANIFEST.json"
manifest = json.loads(manifest_path.read_text())
previous = manifest.get("postbuild_pruned_dependencies", [])
if not isinstance(previous, list):
    raise SystemExit("invalid postbuild prune record")
combined = sorted(set(previous + removed))
manifest["postbuild_pruned_dependencies"] = combined
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
if not combined:
    raise SystemExit("postbuild prune removed nothing")
print(json.dumps({"newly_pruned_dependencies": len(removed), "total_pruned_dependencies": len(combined)}, indent=2))
