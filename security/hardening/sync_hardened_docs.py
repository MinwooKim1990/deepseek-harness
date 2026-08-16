#!/usr/bin/env python3
"""Synchronize user-facing CLI documentation with the hardened runtime policy."""

from __future__ import annotations

import sys
from pathlib import Path


def replace_once(root: Path, rel: str, old: str, new: str) -> None:
    path = root / rel
    text = path.read_text()
    if text.count(old) != 1:
        raise SystemExit(f"expected exactly one documentation anchor in {rel}: {old[:80]!r}")
    path.write_text(text.replace(old, new))


def replace_section(root: Path, rel: str, start: str, end: str, body: str) -> None:
    path = root / rel
    text = path.read_text()
    if text.count(start) != 1 or text.count(end) != 1:
        raise SystemExit(f"documentation section anchors drifted in {rel}: {start!r} .. {end!r}")
    prefix, rest = text.split(start, 1)
    _old, suffix = rest.split(end, 1)
    path.write_text(prefix + start + body + end + suffix)


def sync_hardened_docs(root: Path) -> None:
    replace_once(
        root, "apps/cli/README.md",
        "| `dsh plugin --profile <name> <pnpm args>` | Manage a profile's plugins by forwarding to pnpm in the profile directory. |",
        "| `dsh plugin --profile <name> ...` | Disabled in this hardened fork; exits 126 without running a package manager. |",
    )
    replace_once(
        root, "apps/cli/README.md",
        "The invoking directory is the default workspace root. The `web` and `headless` profiles auto-initialize on first use from shipped templates; any other profile must be created through `dsh plugin`.",
        "The invoking directory is the default workspace root. The `web` and `headless` profiles auto-initialize on first use from shipped templates. Missing custom profiles fail closed because external profile plugin management is disabled.",
    )
    replace_once(
        root, "apps/cli/README.md",
        "- then `--patch` overlays\n\nBundles named in `dsh.profile.bundles` resolve from the dsh installation first (`@deepseek-ai/dsh-base`, `@deepseek-ai/dsh-web-app`, `@deepseek-ai/dsh-headless`), then from the profile's own `node_modules`, where pnpm installs out-of-tree plugins.",
        "- then `--patch` overlays\n\nAll writable layers are data-only, id-targeted overrides. They cannot use executable YAML tags, insert plugin rows, or replace a row's module `name`.\n\nBundles named in `dsh.profile.bundles` resolve from the dsh installation first (`@deepseek-ai/dsh-base`, `@deepseek-ai/dsh-web-app`, `@deepseek-ai/dsh-headless`), then from an existing profile `node_modules`. This hardened CLI does not install or update out-of-tree bundles.",
    )

    replace_once(
        root, "apps/cli/README.zh.md",
        "| `dsh plugin --profile <name> <pnpm args>` | 通过在 profile 目录中转发给 pnpm 来管理该 profile 的插件。 |",
        "| `dsh plugin --profile <name> ...` | 此 hardened fork 已禁用；不会运行包管理器，并以 126 退出。 |",
    )
    replace_once(
        root, "apps/cli/README.zh.md",
        "运行命令时所在的目录将作为默认 workspace 根目录。`web` 和 `headless` profile 在首次使用时会从随附模板自动初始化；其他任何 profile 都必须通过 `dsh plugin` 创建。",
        "运行命令时所在的目录将作为默认 workspace 根目录。`web` 和 `headless` profile 在首次使用时会从随附模板自动初始化。由于外部 profile 插件管理已禁用，缺失的自定义 profile 会以 fail-closed 方式报错。",
    )
    replace_once(
        root, "apps/cli/README.zh.md",
        "- `--patch` 指定的覆盖层\n\n`dsh.profile.bundles` 中列出的组合包先从 dsh 安装目录解析（`@deepseek-ai/dsh-base`、`@deepseek-ai/dsh-web-app`、`@deepseek-ai/dsh-headless`），再从 profile 自身的 `node_modules` 解析；pnpm 会将树外插件安装到该目录。",
        "- `--patch` 指定的覆盖层\n\n所有可写层只能作为 data-only、按 id 定位的覆盖配置；不得使用可执行 YAML 标签、插入插件行或替换行的模块 `name`。\n\n`dsh.profile.bundles` 中列出的组合包先从 dsh 安装目录解析（`@deepseek-ai/dsh-base`、`@deepseek-ai/dsh-web-app`、`@deepseek-ai/dsh-headless`），再从既有的 profile `node_modules` 解析。此 hardened CLI 不安装或更新树外组合包。",
    )

    replace_once(
        root, "apps/cli/reference/README.md",
        "The `web` and `headless` profiles auto-initialize from shipped templates on first use (`web`: base + web-app; `headless`: base + headless). Any other missing profile fails loud with a hint to run `dsh plugin --profile <name> add <package>`.",
        "The `web` and `headless` profiles auto-initialize from shipped templates on first use (`web`: base + web-app; `headless`: base + headless). Any other missing profile fails loud; this hardened fork does not create custom profiles through package installation.",
    )
    replace_once(
        root, "apps/cli/reference/README.md",
        "`--dump-default-config` prints only the bundle layers; `--dump-config` adds the profile's `cordis.patch.yml`, the home-level `$DSH_HOME/cordis.patch.yml`, and `--patch` overlays. Both print comments naming the file that supplied each row and every overlay that changed it; `!!js` expressions remain unevaluated, and unmatched patch targets are reported on stderr. A dump never runs app command-line providers, so it shows the composed tree before any app argument is resolved and rejects an invocation that carries app arguments.",
        "`--dump-default-config` prints only the immutable bundle layers; `--dump-config` adds the profile's `cordis.patch.yml`, the home-level `$DSH_HOME/cordis.patch.yml`, and `--patch` overlays. Trusted bundle `!!js` expressions remain unevaluated in dumps, while writable layers reject every executable YAML tag. Writable layers may only override existing rows by id: `insert` and module `name` replacement fail closed. Unmatched patch targets are reported on stderr. A dump never runs app command-line providers, so it shows the composed tree before any app argument is resolved and rejects an invocation that carries app arguments.",
    )
    replace_section(
        root, "apps/cli/reference/README.md", "## Plugin management\n", "## Web alias",
        "\nExternal profile plugin management is disabled in this hardened fork. `dsh plugin --profile <name> ...` exits 126 without invoking pnpm or changing the profile. Only the shipped `web` and `headless` templates auto-initialize.\n\n",
    )
    replace_section(
        root, "apps/cli/reference/README.md", "## Shared deployment behavior\n", "## Source execution",
        "\nThe base bundle mounts the native DeepSeek adapter, settings and credential providers, and stable `web_search`. Provider credentials resolve from the inherited environment, `$DSH_HOME/.credentials.yaml`, then `$DSH_HOME/.env`. The invoking directory's `.env` is deliberately ignored, and the managed credential document is never materialized into `process.env`. Search uses `DEEPSEEK_API_KEY` and accepts `DEEPSEEK_SEARCH_BASE_URL`.\n\nSession telemetry, feedback upload, anonymous-user persistence, and the associated request header are removed from the production composition. Telemetry environment variables cannot re-enable those paths.\n\nThe production closure excludes dynamic Cordis, workflow/code-runtime, MCP, and Pi-AI packages. Writable patch layers cannot insert or replace plugin modules to restore them.\n\n",
    )

    replace_once(
        root, "apps/cli/reference/README.zh.md",
        "`web` 和 `headless` profile 首次使用时会从随附模板自动初始化（`web`：base + web-app；`headless`：base + headless）。其他缺失的 profile 会显式报错，并提示运行 `dsh plugin --profile <name> add <package>`。",
        "`web` 和 `headless` profile 首次使用时会从随附模板自动初始化（`web`：base + web-app；`headless`：base + headless）。其他缺失的 profile 会显式报错；此 hardened fork 不通过包安装创建自定义 profile。",
    )
    replace_once(
        root, "apps/cli/reference/README.zh.md",
        "`--dump-default-config` 只打印组合包各层；`--dump-config` 额外加上 profile 的 `cordis.patch.yml`、home 级的 `$DSH_HOME/cordis.patch.yml` 和 `--patch` overlay。两者都会打印注释，标明每行由哪个文件提供，以及哪些 overlay 修改过它；`!!js` 表达式保持未求值，找不到目标的 patch 会报告到 stderr。dump 操作不会运行应用的命令行参数提供方，因此展示的是解析任何应用参数之前的组合配置树；如果调用中包含应用参数，dump 会拒绝该调用。",
        "`--dump-default-config` 只打印不可变的组合包各层；`--dump-config` 额外加上 profile 的 `cordis.patch.yml`、home 级的 `$DSH_HOME/cordis.patch.yml` 和 `--patch` overlay。受信任组合包中的 `!!js` 在 dump 中保持未求值，而所有可写层都会拒绝可执行 YAML 标签。可写层只能按 id 覆盖既有行；`insert` 或替换模块 `name` 都会 fail closed。找不到目标的 patch 会报告到 stderr。dump 操作不会运行应用的命令行参数提供方，因此展示的是解析任何应用参数之前的组合配置树；如果调用中包含应用参数，dump 会拒绝该调用。",
    )
    replace_section(
        root, "apps/cli/reference/README.zh.md", "## 插件管理\n", "## Web 别名",
        "\n此 hardened fork 已禁用外部 profile 插件管理。`dsh plugin --profile <name> ...` 不会调用 pnpm 或修改 profile，并以 126 退出。只有随附的 `web` 与 `headless` 模板会自动初始化。\n\n",
    )
    replace_section(
        root, "apps/cli/reference/README.zh.md", "## 共享部署行为\n", "## 源码执行",
        "\n基础组合包挂载原生 DeepSeek 适配器、settings 与凭据提供方和稳定的 `web_search`。提供方凭据依次从继承环境、`$DSH_HOME/.credentials.yaml` 与 `$DSH_HOME/.env` 解析；调用目录的 `.env` 会被明确忽略，受管凭据文档也不会物化进 `process.env`。搜索使用 `DEEPSEEK_API_KEY` 并接受 `DEEPSEEK_SEARCH_BASE_URL`。\n\n生产组合已移除会话遥测、反馈上传、匿名用户标识持久化以及相关请求头；遥测环境变量无法重新启用这些路径。\n\n生产依赖闭包排除了动态 Cordis、workflow/code-runtime、MCP 和 Pi-AI 包。可写 patch 层不能通过插入或替换插件模块来恢复它们。\n\n",
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: sync_hardened_docs.py <source-root>")
    sync_hardened_docs(Path(sys.argv[1]).resolve())
