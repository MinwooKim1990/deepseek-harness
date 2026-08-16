#!/usr/bin/env python3
"""Static acceptance checks for the hardened source/image."""
from __future__ import annotations
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
errors: list[str] = []

def value(rel: str) -> str:
    p = root / rel
    if not p.is_file():
        errors.append(f"missing required file: {rel}")
        return ""
    return p.read_text(errors="ignore")

def absent(rel: str, needles: list[str]) -> None:
    s = value(rel)
    for needle in needles:
        if needle in s:
            errors.append(f"{rel}: forbidden string remains: {needle}")

def present(rel: str, needles: list[str]) -> None:
    s = value(rel)
    for needle in needles:
        if needle not in s:
            errors.append(f"{rel}: required hardening marker missing: {needle}")

for rel in [
    "packages/bundle/base/cordis.patch.yml",
    "packages/bundle/web-app/cordis.patch.yml",
    "packages/bundle/headless/cordis.patch.yml",
]:
    absent(rel, [
        "session-telemetry-otel", "command-feedback", "cordis-host-runner",
        "cordis-client-runner", "dsh-tool-cordis", "workflow-worker-thread",
        "dsh-tool-workflow", "dsh-tool-ralph", "code-runtime-worker-thread",
        "harness-telemetry.deepseeksvc.com",
        "dsh-llm-pi-ai",
    ])

absent("packages/llm/llm-deepseek/src/index.ts", [
    "getOrCreateAnonymousUserId", "AnonymousUserId", "resolveUserId",
])
absent("packages/llm/llm-deepseek/src/adapter.ts", [
    "x-deepseek-harness-user-id", "AnonymousUserId", "this.config.resolveUserId",
])
present("packages/boot/app-boot/src/index.ts", [
    "executable YAML tags are disabled in user patch",
    "for (const layer of [user])",
    "loadTrustedOverlayPatches",
    "assertUserPatchOverridesOnly(binName, file, patches)",
    "plugin insertion is disabled in user patches",
    "plugin module names are disabled in user patches",
    "yaml.JSON_SCHEMA",
    "tag:yaml\\.org,2002:js",
])
absent("packages/boot/app-boot/src/index.ts", [
    "blockedUserPlugins", "assertNoBlockedUserPlugins",
])
absent("packages/api/remotes/src/client/index.ts", [
    "import dynamicRemote", "goalsRemote, dynamicRemote",
])
absent("packages/api/remotes/src/remote-events.ts", [
    "cordis/request-run", "cordis/dynamic-package", "cordis/inspect-query",
])
absent("packages/api/remotes/src/index.ts", ["dsh-cordis-host-runner/types"])
absent("packages/host/apiproxy/src/api-proxy.ts", ["dsh-cordis-host-runner/types"])
absent("packages/extensions/cordis-client-runner/src/client/index.ts", [
    "ctx.remote.$on('cordis/request-run'", "ctx.remote.$on('cordis/inspect-query'",
])
absent("packages/extensions/ui-cordis/src/client/index.ts", [
    "ctx.remote.$on('cordis/dynamic-package'", "ctx.remote.$on('cordis/request-run'",
])
present("apps/cli/src/plugin.ts", ["external profile plugin management is disabled"])

present("apps/cli/README.md", [
    "Disabled in this hardened fork", "data-only, id-targeted overrides",
])
present("apps/cli/README.zh.md", [
    "hardened fork 已禁用", "data-only、按 id 定位",
])
present("apps/cli/reference/README.md", [
    "exits 126 without invoking pnpm", "invoking directory's `.env` is deliberately ignored",
    "production closure excludes dynamic Cordis",
])
present("apps/cli/reference/README.zh.md", [
    "不会调用 pnpm", "调用目录的 `.env` 会被明确忽略", "生产依赖闭包排除了动态 Cordis",
])
for rel in [
    "package.json",
    "apps/cli/package.json",
    "packages/boot/app-boot/package.json",
]:
    data = json.loads(value(rel))
    versions = [
        data.get(section, {}).get("js-yaml")
        for section in ("dependencies", "optionalDependencies", "peerDependencies", "devDependencies")
        if isinstance(data.get(section), dict) and "js-yaml" in data.get(section, {})
    ]
    if any(version != "^4.3.1" for version in versions):
        errors.append(f"{rel}: js-yaml is not pinned to the fixed ^4.3.1 range")
present("packages/extensions/cordis-host-runner/src/sandbox.ts", [
    "dynamic Cordis packages are disabled in this hardened build",
])
absent("packages/extensions/cordis-host-runner/src/sandbox.ts", [
    "runInContext(", "new Script(",
])
absent("packages/extensions/cordis-client-runner/src/client/evaluator.ts", ["new Function("])
absent("packages/workflow/workflow-worker-thread/src/runtime.ts", ["this.compiled.runInContext("])
absent("vendor/schemastery/src/index.ts", ["new Function('return ' + schema.callback)"])
present("vendor/schemastery/src/index.ts", ["schema.callback = undefined"])

risky_packages = {
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
production_manifests = [
    "apps/cli/package.json",
    "packages/api/remotes/package.json",
    "packages/bundle/base/package.json",
    "packages/bundle/web-app/package.json",
    "packages/bundle/headless/package.json",
    "packages/llm/llm-deepseek/package.json",
    "packages/host/apiproxy/package.json",
    "python/sdk-runtime/package.json",
]
for rel in production_manifests:
    data = json.loads(value(rel))
    for section in ("dependencies", "optionalDependencies", "peerDependencies"):
        deps = data.get(section, {})
        if not isinstance(deps, dict):
            continue
        for package in sorted(set(deps) & risky_packages):
            errors.append(f"{rel}: risky production dependency reintroduced: {package}")

manifest_path = root / "HARDENING-MANIFEST.json"
if manifest_path.is_file():
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("source_commit") != "47f943859bef60e4160492346772ded9b24f765a":
        errors.append("hardening manifest source commit mismatch")
    if not manifest.get("postbuild_pruned_dependencies"):
        errors.append("hardening manifest has no postbuild dependency-prune record")
else:
    errors.append("HARDENING-MANIFEST.json missing")

if errors:
    print("HARDENED_VERIFY_FAIL")
    for error in errors:
        print(error)
    raise SystemExit(1)
print("HARDENED_VERIFY_PASS")
