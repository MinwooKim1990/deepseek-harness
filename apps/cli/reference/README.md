# `dsh` CLI behavior reference

English | [中文](README.zh.md)

This reference defines the profile, web-alias, plugin-management, and config-dump command modes. Argv is parsed once through [`src/args.ts`](../src/args.ts), and [`src/bin.ts`](../src/bin.ts) dynamically imports only the selected runner.

## Profile boot

`dsh --profile <name>` boots the profile at `$DSH_HOME/profiles/<name>`. The effective tree is composed over an empty root by applying, in order: each bundle patch named in the profile manifest's `dsh.profile.bundles` list, the profile's own `cordis.patch.yml`, the home-level `$DSH_HOME/cordis.patch.yml` (machine-local preferences shared by every profile, so it outranks the per-profile layer), and each `--patch <path>` overlay in argv order. Later layers win per row; a patch replaces the targeted row's complete `config` value rather than deep-merging keys, and may insert new rows. A parse, schema, resolution, or plugin boot failure is reported and exits nonzero. SIGINT and SIGTERM dispose the mounted root before exit.

Bundle names resolve from the dsh installation first, then from the profile directory. In-box bundles (`@deepseek-ai/dsh-base`, `@deepseek-ai/dsh-web-app`, `@deepseek-ai/dsh-headless`) therefore always come from the same installation as the running `dsh`; out-of-tree bundles come from the profile's pnpm-managed `node_modules`. A bare plugin `name` in any patch row resolves through the profile directory's Node parent-walk, which reaches the maintained installation fallback `$DSH_HOME/profiles/node_modules` (one symlink per package the installation's app and bundles depend on, healed on every launch).

The `web` and `headless` profiles auto-initialize from shipped templates on first use (`web`: base + web-app; `headless`: base + headless). Any other missing profile fails loud; this hardened fork does not create custom profiles through package installation.

### App arguments

The launcher's flags come first and end at the first token it does not recognize; everything from there on is handed to the booted profile verbatim through `ctx.cmdlineArgs`, where any injected app plugin may parse it ([`dsh-cmdline`](../../../packages/boot/cmdline/README.md)). `dsh --profile web --port 8080` therefore reaches the web app's `--port`, `dsh --profile web --help` prints that app's help and boots nothing, and `dsh --help` (no profile to hand it to) prints the launcher's own. `-V`/`--version` prints the launcher's version when it appears before the app-argument boundary.

A composition mounts once. An ordinary plugin injects `cmdlineArgs`, parses this app's arguments, and provides what it resolved as a service; each row configured from flags injects that service, and Loader waits for it before evaluating the row's config (`port: !!js ctx.webStartup.port ?? 3080`). A flag therefore beats the value written beside it. This precedence requires the row to retain that expression; a user patch that replaces the whole `config` with literals removes the runtime read. Help and rejected arguments request exit — nonzero for a rejection, 0 for help — without activating rows that depend on the provider's service. A live `cordis.patch.yml` edit re-evaluates expressions against services that are still up, so it cannot reset a served port.

Launcher flags must come before app arguments, and the launcher's parser consumes one `--`: an app argument that must arrive as a literal `--` needs `-- --`. A first app argument equal to `web` or `plugin` selects that subcommand instead. `ctx.cmdlineArgs.get()` is a shared immutable read: multiple plugins may parse the same snapshot, while a profile with no reader ignores its app arguments.

The shipped apps own these command lines:

| Profile | Arguments |
|---|---|
| `web` | `--host`, `--port`, repeatable `--trusted-host` |
| `headless` | the task text, as the positional argument |

A one-shot task (`dsh --profile headless "run the tests"`) creates one fresh persisted Agent through the core registry, submits the task, waits for quiescence, and flushes the Session before deriving the last non-empty assistant text and final `turn/end` reason from its durable interval. It prints the text on stdout and exits 0 for `completed`, else 1. An invocation with no task is a usage error from that app. The shipped headless profile mounts no ApiProxy, Host, HTTP server, Web runtime, or browser client; a successful run writes nothing to stderr and opens no listening port.

Inspect the composed tree without booting it:

```sh
dsh --profile web --dump-default-config
dsh --profile web --patch ./extra.yml --dump-config
```

`--dump-default-config` prints only the immutable bundle layers; `--dump-config` adds the profile's `cordis.patch.yml`, the home-level `$DSH_HOME/cordis.patch.yml`, and `--patch` overlays. Trusted bundle `!!js` expressions remain unevaluated in dumps, while writable layers reject every executable YAML tag. Writable layers may only override existing rows by id: `insert` and module `name` replacement fail closed. Unmatched patch targets are reported on stderr. A dump never runs app command-line providers, so it shows the composed tree before any app argument is resolved and rejects an invocation that carries app arguments.

## Plugin management

External profile plugin management is disabled in this hardened fork. `dsh plugin --profile <name> ...` exits 126 without invoking pnpm or changing the profile. Only the shipped `web` and `headless` templates auto-initialize.

## Web alias

`dsh web` is a hardcoded alias for `--profile web`; the flags after it belong to the web app, whose ordinary bundle provider parses them. `--host` and `--port` override the composed values of the rows that carry them, and repeatable `--trusted-host` contributes invocation authorities through `ctx.webRuntime.trustedHosts` (a deployment expression concatenates its own authorities). The client-plugin HMR receiver is always mounted and stays idle until a separate `pnpm run dev:web` watcher rebuilds client bundles.

```sh
dsh web
dsh web --patch ./extra.cordis.yml
dsh web --dump-config
dsh web --help
```

The production Web runner needs built package and frontend artifacts (`pnpm run build`). It serves `http://127.0.0.1:3080` by default. The CLI intentionally does not support `--host 0.0.0.0` yet and exits with a usage error; `--trusted-host` adds named authorities accepted by the `/api` browser-trust fence.

Process shutdown gives the plugin tree up to five seconds to dispose. The first `SIGINT`/`SIGTERM` starts that graceful drain — `SIGTERM` is a supervisor's ordinary stop request and exits 0 on every surface, `SIGINT` reports 130; a second signal forces immediate exit. If one-shot normal completion is already stuck in disposal, the first `Ctrl+C` is the escalation and exits immediately instead of being swallowed.

All modes treat the invoking directory as the default workspace root, load applicable `AGENTS.md` or `CLAUDE.md` instructions with a 65,536-byte render budget, and use an in-memory SQLite session content index. Every profile boot watches valid edits of both `cordis.patch.yml` layers (profile and home) and reapplies them transactionally; a one-shot surface exits through its bounded shutdown, which disposes the watchers.

New sessions default to the `workspace-write` permission preset. Bash and filesystem mutations are restricted to the session workspace and platform temporary roots; reads, network access, and process visibility are not confined. `DSH_PERMISSION_MODE` changes the process fallback. Stored General-settings permissions affect later Web sessions, not an already-open one.

`DSH_TOOLS_MODE` selects `native`, `code`, or `both` for the process; another value fails at boot. The shipped `minimal` agent preset keeps that deployment presentation, fixes the complete system prompt to `You are a helpful software engineer assistant.`, and composes only persistent `bash` plus `str_replace_editor`. Select 极简模式 when creating a Web session; every other prompt section and model-facing plugin remains absent from that agent while the shared browser, workspace, persistence, sandbox, and permission host stays in place.

## Shared deployment behavior

The base bundle mounts the native DeepSeek adapter, settings and credential providers, and stable `web_search`. Provider credentials resolve from the inherited environment, `$DSH_HOME/.credentials.yaml`, then `$DSH_HOME/.env`. The invoking directory's `.env` is deliberately ignored, and the managed credential document is never materialized into `process.env`. Search uses `DEEPSEEK_API_KEY` and accepts `DEEPSEEK_SEARCH_BASE_URL`.

Session telemetry, feedback upload, anonymous-user persistence, and the associated request header are removed from the production composition. Telemetry environment variables cannot re-enable those paths.

The production closure excludes dynamic Cordis, workflow/code-runtime, MCP, and Pi-AI packages. Writable patch layers cannot insert or replace plugin modules to restore them.

## Source execution

From the repository root, run `pnpm run build` separately after a fresh checkout and whenever artifacts need updating, then use `pnpm dsh <args...>`. The `package.json` script launches `apps/cli/src/bin.ts` with `node --import tsx/esm` without building and forwards every argument. Missing Typert host artifacts fail profile boot through module-resolution errors without a build instruction. Once those host artifacts exist, missing frontend or client-plugin bundles fail at startup with an instruction to run `pnpm run build`. The launcher does not check freshness, so existing stale bundles can run older browser code until rebuilt. The process inherits the launch environment; set `NODE_USE_ENV_PROXY=1` when a supporting Node version must honor `HTTP_PROXY` and `HTTPS_PROXY`. The installed form launches the built `apps/cli/lib/bin.js` without rebuilding the repository.
