#!/usr/bin/env python3
"""Deterministically harden the pinned DeepSeek Harness source inside a Docker build."""
from __future__ import annotations
import json
import re
import subprocess
import sys
from pathlib import Path

PINNED = "47f943859bef60e4160492346772ded9b24f765a"
ROOT = Path(sys.argv[1]).resolve()


def text(path: str) -> str:
    return (ROOT / path).read_text()


def write(path: str, value: str) -> None:
    (ROOT / path).write_text(value)


def exact(path: str, old: str, new: str, count: int = 1) -> None:
    value = text(path)
    actual = value.count(old)
    if actual != count:
        raise SystemExit(f"{path}: expected {count} exact matches, found {actual}")
    write(path, value.replace(old, new, count))


def regex(path: str, pattern: str, replacement: str, count: int = 1) -> None:
    value = text(path)
    updated, actual = re.subn(pattern, lambda _match: replacement, value, count=count, flags=re.S)
    if actual != count:
        raise SystemExit(f"{path}: expected {count} regex matches, found {actual}: {pattern}")
    write(path, updated)


result = subprocess.run(
    ["git", "-C", str(ROOT), "rev-parse", "HEAD"],
    check=True,
    capture_output=True,
    text=True,
)
head = result.stdout.strip()
if head != PINNED:
    raise SystemExit(f"refusing to harden unexpected commit {head}")

# Remove all shipped activation rows for outbound reporting and model-written/dynamic runtimes.
TARGET_IDS = {
    "session-telemetry-otel",
    "command-feedback",
    "cordis-host-runner",
    "cordis-client-runner",
    "ui-cordis",
    "tool-cordis",
    "workflow-worker-thread",
    "tool-workflow",
    "tool-ralph",
    "ui-workflow-run",
    "code-runtime",
    "llm-pi-ai",
}
row_re = re.compile(r"^(?P<indent>\s*)- id:\s*(?P<id>[^\s#]+)\s*(?:#.*)?$")
removed_rows: list[str] = []
for path in sorted(ROOT.rglob("*.yml")):
    lines = path.read_text(errors="strict").splitlines(keepends=True)
    out: list[str] = []
    i = 0
    changed = False
    while i < len(lines):
        match = row_re.match(lines[i].rstrip("\r\n"))
        if match is None or match.group("id") not in TARGET_IDS:
            out.append(lines[i])
            i += 1
            continue
        indent = match.group("indent")
        removed_rows.append(f"{path.relative_to(ROOT)}:{match.group('id')}")
        changed = True
        i += 1
        next_row = re.compile(rf"^{re.escape(indent)}- id:\s*")
        while i < len(lines) and next_row.match(lines[i]) is None:
            i += 1
    if changed:
        path.write_text("".join(out).rstrip() + "\n")

# Remove risky packages from shipped runtime closure manifests while leaving their source
# present long enough for the monorepo build to prove the patch is type/build compatible.
RISKY_PACKAGES = {
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
MANIFESTS = [
    "apps/cli/package.json",
    "packages/api/remotes/package.json",
    "packages/bundle/base/package.json",
    "packages/bundle/web-app/package.json",
    "packages/bundle/headless/package.json",
    "packages/llm/llm-deepseek/package.json",
    "packages/host/apiproxy/package.json",
    "python/sdk-runtime/package.json",
]
removed_deps: list[str] = []
for rel in MANIFESTS:
    path = ROOT / rel
    data = json.loads(path.read_text())
    for section in ("dependencies", "optionalDependencies", "peerDependencies"):
        deps = data.get(section)
        if not isinstance(deps, dict):
            continue
        for name in sorted(set(deps) & RISKY_PACKAGES):
            removed_deps.append(f"{rel}:{section}:{name}")
    path.write_text(json.dumps(data, indent=2) + "\n")

# Keep the removed MCP workspace available only to the monorepo's compatibility tests.
cli_manifest_path = ROOT / "apps/cli/package.json"
cli_manifest = json.loads(cli_manifest_path.read_text())
cli_manifest.setdefault("devDependencies", {})["@deepseek-ai/dsh-mcp-client"] = "workspace:^"
cli_manifest_path.write_text(json.dumps(cli_manifest, indent=2) + "\n")

# Upgrade the directly used YAML parser to versions fixing both known quadratic-CPU advisories.
for path in sorted(ROOT.rglob("package.json")):
    try:
        data = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        continue
    changed = False
    for section in ("dependencies", "optionalDependencies", "peerDependencies", "devDependencies"):
        deps = data.get(section)
        if isinstance(deps, dict) and "js-yaml" in deps and deps["js-yaml"] != "^4.3.1":
            deps["js-yaml"] = "^4.3.1"
            changed = True
    if changed:
        path.write_text(json.dumps(data, indent=2) + "\n")

# Never load project-controlled .env in the product CLI. Explicit inherited env wins,
# and an optional DSH_HOME/.env remains the only file-backed launch layer.
exact(
    "packages/boot/app-boot/src/index.ts",
    "  const project = readEnvLayer(binName, cwd, warn)\n",
    "",
)
exact(
    "packages/boot/app-boot/src/index.ts",
    "  for (const layer of [project, user]) {\n",
    "  for (const layer of [user]) {\n",
)
exact(
    "packages/boot/app-boot/src/index.ts",
    "    ...project === undefined ? [] : [{ source: 'project-env' as const, path: project.path, values: project.values }],\n",
    "",
)

# User profile/--patch files may not carry executable !!js tags. Trusted first-party
# bundle files retain the existing dialect through a separate loader entry point.
exact(
    "packages/boot/app-boot/src/index.ts",
    "// from the include itself so patch parsing and config dumping can never drift\n// from what the include mounts. User patch layers share it so they may\n// reference `process.env`.\n",
    "// from the include itself so trusted bundle parsing and config dumping cannot\n// drift from what the include mounts. Writable user layers are pre-screened and\n// never reach this schema when executable tags are present.\n",
)
exact(
    "packages/boot/app-boot/src/index.ts",
    "const userPatchesSchema = entryListSchema\n",
    """const userPatchesSchema = entryListSchema

/** Hardened boundary: writable profile and --patch layers are data, never JavaScript. */
function assertNoUserJavaScript(file: string, content: string): void {
  if (/!!?js\\b|!<tag:yaml\\.org,2002:js>/.test(content)) {
    throw new Error(`dsh: executable YAML tags are disabled in user patch ${file}`)
  }
}

const blockedUserPlugins = new Set([
  '@deepseek-ai/dsh-session-telemetry',
  '@deepseek-ai/dsh-session-telemetry-otel',
  '@deepseek-ai/dsh-anonymous-user-id',
  '@deepseek-ai/dsh-command-feedback',
  '@deepseek-ai/dsh-cordis-host-runner',
  '@deepseek-ai/dsh-cordis-client-runner',
  '@deepseek-ai/dsh-client-ui-cordis',
  '@deepseek-ai/dsh-tool-cordis',
  '@deepseek-ai/dsh-workflow-worker-thread',
  '@deepseek-ai/dsh-tool-workflow',
  '@deepseek-ai/dsh-tool-ralph',
  '@deepseek-ai/dsh-client-ui-workflow-run',
  '@deepseek-ai/dsh-code-runtime-worker-thread',
  '@deepseek-ai/dsh-mcp-client',
  '@deepseek-ai/dsh-llm-pi-ai',
])

/** Hardened boundary: writable layers cannot reactivate removed runtime packages. */
function assertNoBlockedUserPlugins(binName: string, file: string, patches: PatchOptions[]): void {
  const seen = new WeakSet<object>()
  const visit = (value: unknown): void => {
    if (typeof value !== 'object' || value === null) return
    if (seen.has(value)) return
    seen.add(value)
    if (Array.isArray(value)) {
      value.forEach(visit)
      return
    }
    const record = value as Record<string, unknown>
    if (typeof record.name === 'string' && blockedUserPlugins.has(record.name)) {
      throw new Error(`${binName}: blocked high-risk plugin ${JSON.stringify(record.name)} in user patch ${file}`)
    }
    Object.values(record).forEach(visit)
  }
  visit(patches)
}
""",
)
exact(
    "packages/boot/app-boot/src/index.ts",
    """ * overrides and `insert` lists, with `!!js` expressions allowed. A missing
 * file means "no layer"; an unreadable, unparsable, or non-array file throws —
""",
    """ * overrides and `insert` lists. Executable YAML and blocked high-risk plugin
 * names are rejected. A missing
 * file means "no layer"; an unreadable, unparsable, or non-array file throws —
""",
)
exact(
    "packages/boot/app-boot/src/index.ts",
    "  return parsePatchList(binName, file, content, 'patches')\n",
    "  assertNoUserJavaScript(file, content)\n  const patches = parsePatchList(binName, file, content, 'patches', yaml.JSON_SCHEMA)\n  assertNoBlockedUserPlugins(binName, file, patches)\n  return patches\n",
)
old_overlay = """export function loadOverlayPatches(binName: string, file: string): PatchOptions[] {
  let content: string
  try {
    content = readFileSync(file, 'utf8')
  } catch (error) {
    throw new Error(`${binName}: failed to read overlay ${file}: ${String(error)}`)
  }
  return parsePatchList(binName, file, content, 'overlay')
}
"""
new_overlay = """export function loadOverlayPatches(binName: string, file: string): PatchOptions[] {
  let content: string
  try {
    content = readFileSync(file, 'utf8')
  } catch (error) {
    throw new Error(`${binName}: failed to read overlay ${file}: ${String(error)}`)
  }
  assertNoUserJavaScript(file, content)
  const patches = parsePatchList(binName, file, content, 'overlay', yaml.JSON_SCHEMA)
  assertNoBlockedUserPlugins(binName, file, patches)
  return patches
}

/** Load an immutable, package-owned bundle with the first-party !!js dialect. */
export function loadTrustedOverlayPatches(binName: string, file: string): PatchOptions[] {
  let content: string
  try {
    content = readFileSync(file, 'utf8')
  } catch (error) {
    throw new Error(`${binName}: failed to read trusted overlay ${file}: ${String(error)}`)
  }
  return parsePatchList(binName, file, content, 'trusted overlay')
}
"""
exact("packages/boot/app-boot/src/index.ts", old_overlay, new_overlay)
exact(
    "packages/boot/app-boot/src/index.ts",
    "  binName: string, file: string, content: string, label: string,\n): PatchOptions[] {\n",
    "  binName: string, file: string, content: string, label: string,\n  schema: yaml.Schema = userPatchesSchema,\n): PatchOptions[] {\n",
)
exact(
    "packages/boot/app-boot/src/index.ts",
    "    parsed = yaml.load(content, { schema: userPatchesSchema })\n",
    "    parsed = yaml.load(content, { schema })\n",
)
exact(
    "packages/boot/app-boot/src/profile.ts",
    "import { loadOverlayPatches } from './index.ts'\n",
    "import { loadOverlayPatches, loadTrustedOverlayPatches } from './index.ts'\n",
)
exact(
    "packages/boot/app-boot/src/profile.ts",
    "return { packageName, packageDir, patchPath, patches: loadOverlayPatches(binName, patchPath) }",
    "return { packageName, packageDir, patchPath, patches: loadTrustedOverlayPatches(binName, patchPath) }",
)

# Remove the dynamic Cordis Remote namespace and forwarded events from the web runtime.
exact(
    "apps/cli/src/profile-boot.ts",
    " * own `cordis.patch.yml`, `--patch` overlays, the telemetry switch), mount the\n",
    " * own data-only `cordis.patch.yml` and `--patch` overlays), mount the\n",
)
exact(
    "packages/api/remotes/src/client/index.ts",
    "import dynamicRemote from '@deepseek-ai/dsh-cordis-host-runner/remote'\n",
    "",
)
exact(
    "packages/api/remotes/src/client/index.ts",
    "      commandsRemote, goalsRemote, dynamicRemote, pluginInventoryRemote, messageFeedbackRemote,\n",
    "      commandsRemote, goalsRemote, pluginInventoryRemote, messageFeedbackRemote,\n",
)
exact(
    "packages/api/remotes/src/index.ts",
    "import type {} from '@deepseek-ai/dsh-cordis-host-runner/types'\n",
    "",
)
exact(
    "packages/api/remotes/src/remote-events.ts",
    """  'cordis/request-run',
  'cordis/request-run-resolved',
  'cordis/dynamic-package',
  'cordis/dynamic-retract',
  'cordis/inspect-query',
  'cordis/inspect-query-resolved',
""",
    "",
)
exact(
    "packages/host/apiproxy/src/api-proxy.ts",
    """// Type-only: the dynamic-package runner's forwarded-event declarations. Its
// client-safe `./types` subpath deliberately, not the package root — the root
// merges `ctx.dynamicCordisRunner`, and a dependency on that package would
// rebuild the api-remotes cycle this direction exists to avoid.
import type {} from '@deepseek-ai/dsh-cordis-host-runner/types'
""",
    "",
)

# Disable arbitrary package installation/update in hardened profiles.
write(
    "apps/cli/src/plugin.ts",
    r"""/** External profile package installation is deliberately absent from the hardened build. */
export function runPlugin(profile: string, args: readonly string[]): number {
  void profile
  void args
  process.stderr.write('dsh: external profile plugin management is disabled in this hardened build\n')
  return 126
}
""",
)

# Remove the stable per-install identifier from every DeepSeek model request.
exact(
    "packages/llm/llm-deepseek/src/index.ts",
    "import { getOrCreateAnonymousUserId, type AnonymousUserId } from '@deepseek-ai/dsh-anonymous-user-id'\n",
    "",
)
exact(
    "packages/llm/llm-deepseek/src/index.ts",
    "  let userId: AnonymousUserId | undefined\n  const resolveUserId = (): AnonymousUserId => userId ??= getOrCreateAnonymousUserId()\n  const adapter = new DeepSeekAdapter({ options, resolveApiKey, resolveUserId })\n",
    "  const adapter = new DeepSeekAdapter({ options, resolveApiKey })\n",
)
exact(
    "packages/llm/llm-deepseek/src/adapter.ts",
    "import type { AnonymousUserId } from '@deepseek-ai/dsh-anonymous-user-id'\n",
    "",
)
exact(
    "packages/llm/llm-deepseek/src/adapter.ts",
    "  /** Resolve the harness-home anonymous id shared with telemetry and feedback. */\n  resolveUserId: () => AnonymousUserId\n",
    "  /** Deprecated compatibility hook; ignored by the hardened adapter. */\n  resolveUserId?: () => unknown\n",
)
exact(
    "packages/llm/llm-deepseek/src/adapter.ts",
    "    const userId = this.config.resolveUserId()\n",
    "",
)
exact(
    "packages/llm/llm-deepseek/src/adapter.ts",
    "      apiKey,\n      userId,\n      () => { watchdog.pulse() },\n",
    "      apiKey,\n      () => { watchdog.pulse() },\n",
)
exact(
    "packages/llm/llm-deepseek/src/adapter.ts",
    "    apiKey: string,\n    userId: AnonymousUserId,\n    onComment: () => void,\n",
    "    apiKey: string,\n    onComment: () => void,\n",
)
exact(
    "packages/llm/llm-deepseek/src/adapter.ts",
    "      'x-deepseek-harness-user-id': String(userId),\n",
    "",
)

# Fail closed even if dynamic Cordis packages are imported directly.
exact(
    "packages/extensions/cordis-host-runner/src/sandbox.ts",
    "import { createContext, runInContext, Script } from 'node:vm'\n",
    "import { createContext } from 'node:vm'\n",
)
exact(
    "packages/extensions/cordis-host-runner/src/sandbox.ts",
    """/**
 * Cross-realm SyntaxError detection: a compile failure inside `runInContext`
 * constructs its error in the SANDBOX realm, so a host `instanceof
 * SyntaxError` is silently false — the `name` property is the realm-safe tag.
 */
function isSyntaxError(error: unknown): error is Error {
  return typeof error === 'object' && error !== null && (error as { name?: unknown }).name === 'SyntaxError'
}

""",
    "",
)
exact(
    "packages/extensions/cordis-host-runner/src/sandbox.ts",
    """/**
 * Patch only VM constructors so `instanceof` accepts both VM values and host values passed as
 * arguments, events, or service results; host intrinsics remain untouched.
 */
const DUAL_REALM_INSTANCEOF_PRELUDE = `
(hostIntrinsics) => {
  'use strict'
  const ordinary = Function.prototype[Symbol.hasInstance]
  for (const name of Object.keys(hostIntrinsics)) {
    const VmCtor = globalThis[name]
    const HostCtor = hostIntrinsics[name]
    if (typeof VmCtor !== 'function' || typeof HostCtor !== 'function') continue
    Object.defineProperty(VmCtor, Symbol.hasInstance, {
      value: (instance) => ordinary.call(VmCtor, instance) || ordinary.call(HostCtor, instance),
      configurable: true,
    })
  }
}
`

/** Run {@link DUAL_REALM_INSTANCEOF_PRELUDE} in a freshly created sandbox, handing it the host intrinsics to pair up. */
""",
    "/** Hardened no-op: dynamic host code execution is disabled. */\n",
)
regex(
    "packages/extensions/cordis-host-runner/src/sandbox.ts",
    r"function patchDualRealmInstanceof\(sandbox: object\): void \{.*?\n\}",
    "function patchDualRealmInstanceof(sandbox: object): void { void sandbox }",
)
regex(
    "packages/extensions/cordis-host-runner/src/sandbox.ts",
    r"export function precheckCode\(code: string, half: 'code\.host' \| 'code\.client'\): void \{.*?\n\}",
    """export function precheckCode(code: string, half: 'code.host' | 'code.client'): void {
  void code
  void half
  throw new Error('dynamic Cordis packages are disabled in this hardened build')
}""",
)
regex(
    "packages/extensions/cordis-host-runner/src/sandbox.ts",
    r"export async function evaluateHostCode\(sandbox: object, code: string, id: string, vmTimeoutMs: number\): Promise<unknown> \{.*?\n\}",
    """export async function evaluateHostCode(sandbox: object, code: string, id: string, vmTimeoutMs: number): Promise<unknown> {
  void sandbox
  void code
  void id
  void vmTimeoutMs
  throw new Error('dynamic Cordis packages are disabled in this hardened build')
}""",
)
write(
    "packages/extensions/cordis-client-runner/src/client/evaluator.ts",
    """/** Fail-closed browser-half API retained for type compatibility. */
import type { CordisDynamicPluginId } from '@deepseek-ai/dsh-api-remotes/client'

export interface DynamicCordisEvaluatedPlugin {
  name?: string
  inject?: string[]
  apply: (ctx: unknown, config?: unknown) => unknown
}

export interface DynamicCordisClosureEnv {
  invoke(method: string, args: unknown): Promise<unknown>
  noteError(message: string): void
}

export const DYNAMIC_CLIENT_REDIRECTS: Readonly<Record<string, string>> = {
  setTimeout: 'dynamic packages are disabled in this hardened build',
  setInterval: 'dynamic packages are disabled in this hardened build',
  clearTimeout: 'dynamic packages are disabled in this hardened build',
  clearInterval: 'dynamic packages are disabled in this hardened build',
  fetch: 'dynamic packages are disabled in this hardened build',
  require: 'dynamic packages are disabled in this hardened build',
}

export class DynamicCordisStyles {
  private readonly tags = new Set<HTMLStyleElement>()
  constructor(private readonly pluginId: CordisDynamicPluginId) {}
  insert(css: string): () => void {
    if (typeof css !== 'string') throw new Error('styles.insert(css) needs a CSS string')
    const tag = document.createElement('style')
    tag.dataset.dyn = this.pluginId
    tag.textContent = css
    document.head.append(tag)
    this.tags.add(tag)
    return () => { this.tags.delete(tag); tag.remove() }
  }
  get count(): number { return this.tags.size }
  dispose(): void { for (const tag of this.tags) tag.remove(); this.tags.clear() }
}

export function isDynamicCordisPlugin(value: unknown): value is DynamicCordisEvaluatedPlugin | ((ctx: unknown) => unknown) {
  if (typeof value === 'function') return true
  return typeof value === 'object' && value !== null
    && typeof (value as { apply?: unknown }).apply === 'function'
}

export async function evaluateClientHalf(
  pluginId: CordisDynamicPluginId,
  clientCode: string,
  env: DynamicCordisClosureEnv,
  styles: DynamicCordisStyles,
): Promise<DynamicCordisEvaluatedPlugin | ((ctx: unknown) => unknown)> {
  void pluginId
  void clientCode
  void env
  void styles
  throw new Error('dynamic Cordis packages are disabled in this hardened build')
}
""",
)

# Workflow JavaScript may still be imported by old callers; make the execution edge fail closed.
exact(
    "packages/workflow/workflow-worker-thread/src/runtime.ts",
    "  private readonly compiled: vm.Script\n",
    "",
)
regex(
    "packages/workflow/workflow-worker-thread/src/runtime.ts",
    r"    // Compile FIRST:.*?    \}\n\n(?=    this\.context)",
    "    void body\n\n",
)
regex(
    "packages/workflow/workflow-worker-thread/src/runtime.ts",
    r"      const scriptPromise =.*?      return \{ value, stopReason: 'completed', agentsStarted: this\.started \}\n",
    "      throw new WorkflowError('dynamic workflow execution is disabled in this hardened build', 'SCRIPT_PARSE')\n",
)
regex(
    "packages/workflow/workflow-worker-thread/src/runtime.ts",
    r"  /\*\* Materialize the script's return value;.*?\n  \}\n\n(?=  /\*\*\n   \* Acquire one concurrency slot)",
    "",
)

# Serialized schema callbacks remain data. Rehydrating callback strings with
# new Function turns every schema producer into a browser-side execution seam.
exact(
    "vendor/schemastery/src/index.ts",
    """  if (typeof schema.callback === 'string') {
    try {
      // eslint-disable-next-line no-new-func
      schema.callback = new Function('return ' + schema.callback)()
    } catch {}
  }
""",
    """  if (typeof schema.callback === 'string') {
    schema.callback = undefined
  }
""",
)

manifest = {
    "source_commit": PINNED,
    "removed_rows": removed_rows,
    "removed_dependencies": removed_deps,
    "hardening": [
        "removed telemetry and feedback activation",
        "removed x-deepseek-harness-user-id and anonymous-id resolution from model requests",
        "blocked JavaScript tags in user/profile/--patch YAML",
        "disabled external profile plugin management",
        "disabled Cordis host/client dynamic evaluators",
        "removed the Cordis dynamic Remote namespace and forwarded events",
        "disabled workflow and code-runtime activation",
        "disabled automatic project .env loading",
        "removed MCP from CLI runtime closure",
        "removed the optional Pi-AI provider and its MCP/Google transitive closure",
        "upgraded js-yaml to 4.3.1 or newer",
        "disabled Schemastery string-callback rehydration",
    ],
}
(ROOT / "HARDENING-MANIFEST.json").write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({"removed_rows": len(removed_rows), "removed_dependencies": len(removed_deps)}, indent=2))
