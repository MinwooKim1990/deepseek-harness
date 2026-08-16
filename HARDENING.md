# DeepSeek Harness — hardened branch

This public fork tracks [`deepseek-ai/deepseek-harness`](https://github.com/deepseek-ai/deepseek-harness) while maintaining a reduced-risk `hardened` branch.

> This is defensive hardening, not an allegation that upstream contains a malicious backdoor. The branch removes optional telemetry, identifiers, dynamic-code and extension surfaces that are outside this fork's intended threat model.

## Audited baseline

- Upstream branch: `master`
- Baseline commit: `47f943859bef60e4160492346772ded9b24f765a`
- Upstream version at audit: `0.1.0-rc.5`

## Security changes

- Removes telemetry and command-feedback activation.
- Removes the stable anonymous installation ID and `x-deepseek-harness-user-id` model-request header.
- Blocks executable `!!js` tags in user profile and `--patch` YAML.
- Restricts writable profile/home/`--patch` layers to data-only, id-targeted overrides; plugin insertion and module-name replacement fail closed.
- Disables external profile package installation/update.
- Disables Cordis host/client dynamic package evaluation.
- Removes the Cordis dynamic Remote namespace and forwarded events from the web production closure.
- Disables workflow, code-runtime, MCP, Ralph and optional Pi-AI activation in production bundles.
- Stops loading `.env` from the invoking project directory; only inherited environment and `$DSH_HOME/.env` remain.
- Disables Schemastery string-callback rehydration through `new Function`.
- Updates `js-yaml` to the fixed `^4.3.1` range.
- Keeps removed packages out of production manifests; test-only compatibility dependencies remain dev-only.

The exact invariant list is checked by [`security/hardening/verify_hardened.py`](security/hardening/verify_hardened.py).

## Verification

```bash
corepack pnpm install --frozen-lockfile
python3 security/hardening/verify_hardened.py .
corepack pnpm run verify-doc-graphs
corepack pnpm build
node apps/cli/lib/bin.js --version
```

The `Hardened Guard` GitHub workflow runs these checks on every `hardened` push and pull request.

## Keeping current with upstream

`master` remains the clean fork branch. Security changes live on `hardened`.

```bash
git fetch upstream
git checkout master
git merge --ff-only upstream/master
git push origin master

git checkout hardened
git merge master
corepack pnpm install --lockfile-only --ignore-scripts
python3 security/hardening/verify_hardened.py .
python3 security/hardening/check_runtime_closure.py .
corepack pnpm install --frozen-lockfile
corepack pnpm run gen-doc-graphs
corepack pnpm run verify-doc-graphs
corepack pnpm build
git push origin hardened
```

A weekly workflow checks whether `hardened` is behind upstream. Upstream changes touching guarded surfaces must be reviewed and reconciled rather than automatically accepted.

## Reapplying or auditing the patch

The deterministic scripts used for the audited baseline are under [`security/hardening/`](security/hardening/). `harden_source.py` is intentionally pinned to the audited commit and must be reviewed and repinned before use against a newer upstream commit.
