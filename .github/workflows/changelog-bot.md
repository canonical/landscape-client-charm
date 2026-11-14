---
# Weekly changelog PR bot (GitHub Agentic Workflow).
#
# This is the gh-aw SOURCE file. After editing, regenerate the compiled
# GitHub Actions workflow with:
#
#     gh aw compile changelog-bot
#
# and commit the generated `.github/workflows/changelog-bot.lock.yml` alongside it.

on:
  # Fire every Saturday at around 12:00 UTC.
  schedule: weekly on saturday around 12:00 UTC
  # Allow maintainers to trigger a run on demand.
  workflow_dispatch:

permissions:
  contents: read

# Run on the Canonical self-hosted runner fleet. The agent and
# threat-detection jobs need Docker/AWF and target the noble/amd64 labels;
# the framework and safe_outputs jobs use the slim self-hosted label.
runs-on: [self-hosted, noble, amd64]
runs-on-slim: self-hosted

# The default checkout is shallow (fetch-depth 1) with no tags, which makes the
# agent see only the latest commit. Fetch full history so it can scan the
# commit window and read the commit log. A second checkout fetches the
# documentation repo (all branches) for the shared release-notes PR; that repo
# is public, so the checkout needs no token (setting one here would also leak
# it onto the primary-repo checkout in the safe-output jobs).
checkout:
  - fetch-depth: 0
  - repository: canonical/landscape-documentation
    path: ./landscape-documentation
    fetch: ["*"]

engine:
  id: gemini
  # The native Gemini engine uses GEMINI_API_KEY directly and takes an exact
  # model id, avoiding the pi engine's model-grammar rejection of vendored
  # OpenRouter ids (github/gh-aw#77514). Gemini does not resolve gh-aw model
  # aliases, so this must be an exact id.
  model: gemini-3.5-flash
  env:
    GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}

network:
  allowed: [defaults]

# Shell access for inspecting history and formatting dates. The pi engine
# cannot allowlist individual commands, so bash is open; the AWF sandbox,
# network allowlist, and safe-output handlers still confine the run.
tools:
  bash: ["*"]
  edit:

# The agent never pushes directly; its file edits are turned into pull
# requests. gh-aw binds the whole safe_outputs job to a single credential for
# its git checkouts and pushes (github/gh-aw#77580). The default GITHUB_TOKEN
# cannot write to canonical/landscape-documentation, so the whole job uses
# LANDSCAPE_CHANGELOG_TOKEN, a fine-grained PAT with contents+pull-requests
# read/write on both this repo and canonical/landscape-documentation; it backs
# both the own-repo changelog PR and the release-notes push.
safe-outputs:
  github-token: ${{ secrets.LANDSCAPE_CHANGELOG_TOKEN }}
  runs-on: self-hosted
  threat-detection:
    engine: copilot
    runs-on: [self-hosted, noble, amd64]
  create-pull-request:
    title-prefix: "build: "
    labels: [changelog, automation]
    team-reviewers: [canonical/landscape]
    draft: false
    if-no-changes: ignore
    max: 1
    preserve-branch-name: true
    recreate-ref: true
    # The bot only ever edits CHANGELOG.md in this repo; the handler rejects
    # any other path outright. (gh-aw allowed-files filters by path only, not
    # diff hunk, so "insert one new dated section, never touch existing
    # sections" stays prompt-enforced.)
    allowed-files: ["CHANGELOG.md"]
  push-to-pull-request-branch:
    github-token: ${{ secrets.LANDSCAPE_CHANGELOG_TOKEN }}
    target: "*"
    target-repo: canonical/landscape-documentation
    required-labels: [changelog, automation]
    # Docs PR updates may only touch release-notes pages (including index.md).
    allowed-files: ["docs/reference/release-notes/*.md"]
    max: 1

# The self-hosted runner image ships a Node too old for gh-aw's runtime
# scripts ("Cannot find module 'node:fs'" in the activation job). Install a
# modern Node before activation runs.
jobs:
  activation:
    pre-steps:
      - name: Setup modern Node for gh-aw runtime
        uses: actions/setup-node@v4
        with:
          node-version: "24"
  # gh-aw's install_copilot_cli.sh uses --prefer-toolcache, which does not
  # land the binary on PATH on this self-hosted runner image, so the
  # threat-detection step exits 127. Install @github/copilot globally with
  # npm in a detection pre-step so the binary resolves.
  detection:
    pre-steps:
      - name: Install GitHub Copilot CLI
        run: |
          npm install -g @github/copilot@1.0.103
          copilot --version

# The self-hosted runner image lacks the Docker Compose plugin, so the AWF
# sandbox's "docker compose up -d" fails with "unknown shorthand flag: 'd' in
# -d" and the agent job exits 125. Install the plugin before the agent job's
# setup scripts.
steps:
  - name: Install Docker Compose plugin
    run: |
      if docker compose version >/dev/null 2>&1; then
        echo "Docker Compose plugin already present, skipping install."
        docker compose version
        exit 0
      fi
      COMPOSE_VERSION="v5.5.0"
      mkdir -p ~/.docker/cli-plugins
      curl -fsSL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64" \
        -o ~/.docker/cli-plugins/docker-compose
      chmod +x ~/.docker/cli-plugins/docker-compose
      docker compose version

# The runner image also ships a gh too old for "gh attestation verify",
# which the agent job's AWF install requires. Install a checksum-verified
# modern gh CLI before the agent job's setup scripts.
pre-steps:
  - name: Install modern gh CLI
    run: |
      GH_VERSION="2.83.1"
      GH_SHA256="1c5252d4ce3db07b51c01ff0b909583da6364ff3fdc06d0c2e75e62dc0380a34"
      tmp="$(mktemp -d)"
      curl -fsSL "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_amd64.tar.gz" -o "$tmp/gh.tgz"
      echo "${GH_SHA256}  $tmp/gh.tgz" | sha256sum -c -
      tar -xzf "$tmp/gh.tgz" -C "$tmp"
      install -m 0755 "$tmp/gh_${GH_VERSION}_linux_amd64/bin/gh" /usr/local/bin/gh
      rm -rf "$tmp"
      gh version
    env:
      GH_TOKEN: ${{ github.token }}
---

# Weekly changelog update

You maintain the changelog for the Landscape Client charm (the subordinate Juju charm that registers machines with Landscape). Your job is to draft a new dated changelog section summarizing recent user-facing changes and open a pull request with it.

## Hard prohibitions

- NEVER create, edit, or delete any file other than `CHANGELOG.md` in this repository. This is mechanically enforced by the pull-request handler: it rejects any patch touching another path.
- NEVER edit or delete an existing `CHANGELOG.md` section or entry, even one with problems. Flag problems in the `Changelog entries to review` section instead.

## Gather the commits

1. The changelog lives at `CHANGELOG.md` in the repository root. It may not exist yet; this bot creates it on the first run.
2. The scan window is time-based: list the commits from the last four weeks with `git log --since="4 weeks ago" --no-merges --pretty=%H%x09%s`. Do NOT anchor on release tags or on `CHANGELOG.md` commits: every push to `main` is published to Charmhub `latest/edge` and CI tags the commit once per platform as `<base>-<arch>-rev<N>` (older releases used legacy `rev<N>` tags), so the most recent tagged commit is almost always the tip of `main` and a tag anchor would leave an empty window. Four weeks against a weekly schedule gives three weeks of overlap with the previous run, so omissions are still caught; the deduplication rules below prevent double-filing.
3. Skip any commit whose subject has no trailing pull request reference ` (#1234)`. Such commits cannot carry the `(#<N>)` marker the deduplication relies on, so they can never be filed safely; if one looks user-facing, flag it in the review section below instead of adding a changelog entry for it.
4. Deduplicate the rest by pull request number. For each commit, extract its PR number `<N>` from the trailing ` (#1234)` reference in the subject. Skip the commit if `CHANGELOG.md` exists and already contains the exact reference `(#<N>)` anywhere (match the full number — `(#123` must not match `(#1234)`). Every entry this bot writes ends with its ` (#1234)` reference, so an existing mention means a previous run already covered that PR.

## Select user-facing commits only

Include only commits that a Landscape administrator would notice. Commit subjects follow conventional commits by convention but this is not enforced, so tolerate free-form subjects and judge those by their content:

- **Include**: `feat:`, `fix:`, `perf:`, and any breaking change (a `!` before the colon, e.g. `feat!:` / `fix!:`).
- **Maybe Include**: `refactor: ` commits, only if they are user-facing.
- **Exclude**: `chore:`, `ci:`, `test:`, `build:`, `docs:`, and `style:`, commits,
  plus anything that only touches tooling, tests, or CI, and any dependency bumps.

Breaking changes are not always flagged in the subject. For every selected commit, also inspect the full commit message with `git show -s --format=%B <sha>` and look for `BREAKING CHANGE:` or `BREAKING-CHANGE:` footers. A commit carrying such a footer is a breaking change even when its subject has no `!` — classify it as breaking and note the breaking nature in the docs island bullet.

Add each selected commit's subject line, including its type prefix and any `(LP: #NNNN)` Launchpad references, but excluding any `(scope)` after the type prefix. Proofread and correct any obvious spelling or grammar errors. Remove Jira issue references such as `LNDENG-5678` wherever they occur in the subject. Do **not** strip `(LP: #NNNN)` references, and do **not** strip the trailing ` (#1234)` pull request reference — it is the coverage marker later runs deduplicate against. If there are no user-facing commits in the window at all, stop and make no changes.

## Sort the commits

Group the commits by their type. Adhere to the following order.

- Breaking changes (a `!` in the subject or a `BREAKING CHANGE:`/`BREAKING-CHANGE:` footer)
- `feat`
- `fix`
- `perf`
- `refactor`

Within each group, maintain the relative ordering of the commits.

## Compose the new section

Charm releases are Charmhub revisions assigned at publish time, not versions declared in this repository, so changelog sections are dated rather than versioned.

If `CHANGELOG.md` does not exist yet, create it with exactly this header:

```
# Changelog

All notable user-facing changes to this charm are documented here, newest first.
```

Insert a new dated section directly under that header, before any existing sections, so the file stays newest-first:

```
## YYYY-MM-DD

### Features

- <subject> (#1234)
```

- Use `date +%F` for the section date (e.g. `2026-11-10`).
- Group entries under headings in this order: `### Breaking changes`, `### Features`, `### Fixes`, `### Performance`, `### Refactors`. Omit headings that have no entries.
- Each entry is a bullet beginning with `- ` and ending with the ` (#1234)` pull request reference described above.

## Review existing changelog entries

If `CHANGELOG.md` exists, review the entries in its newest sections (those added within the window) and the commits in the window for mismatches. Do NOT edit or delete anything. List every finding under a `Changelog entries to review` heading in the pull request body, one bullet per entry or commit with the reason and evidence; if no pull request is opened, report them in your run summary instead. Flagged items are excluded from the docs release-notes island.

- **User-facing commit with no pull request reference**: a commit skipped by the ` (#1234)` rule above that matches "Select user-facing commits". Propose the entry it would have gotten.
- **Existing changelog entry with no user impact**: find the commit behind the entry's `(#<N>)` reference (`git log --no-merges --grep="(#<N>)" -1 --format=%H`) and check `git show --name-only --format= <commit>`. Flag it if every touched path is a test (`tests/`), CI/tooling (`.github/`, `Makefile`, lint or build configuration), or docs file.
- **Fix for an unreleased regression**: for a selected `fix:` commit F, take the hunks F modified (`git show -U0 F`) and run `git blame --porcelain -L <start>,<end> F^ -- <file>` to find the commits that introduced those lines. If they all fall inside the window, the bug was never in a stable channel — do not add a changelog entry for it and flag the commit instead. A PR title or body that references another PR merged in the same window is supporting evidence. If blame results are mixed, still write the entry but flag it as "possible", not certain.

## Open the pull request

Open a pull request with the change. Use a title like `changelog update for <date>` (the `build: ` prefix is added automatically) and a body that lists the included commits, notes that only user-facing changes were selected, and includes the `Changelog entries to review` heading when anything was flagged. If no new section was needed, do not open an empty pull request — report any flagged entries in your run summary instead.

## Docs release notes (shared PR)

You also maintain one island of the user-facing release notes for the in-development Landscape release, drafted in ONE SHARED pull request against `canonical/landscape-documentation`. You own exactly one marked section (island) in that PR and NEVER open separate per-repo docs PRs beyond the shared one.

The shared docs PR (title `build: draft release notes for Landscape YY.MM`, labels `changelog` + `automation`, based on `develop`, the release-notes page pre-seeded with all eight islands) is created weekly — Fridays around 12:00 UTC — by the `release-notes-draft` workflow in `canonical/landscape-documentation`. Bots NEVER create it; you only ever push to its head branch.

The docs work happens in the separate `./landscape-documentation` checkout. The hard prohibitions above apply to this repository (landscape-client-charm) only; editing the release-notes page in the docs checkout is expected and allowed.

Your island content derives from ALL user-facing commits selected in the window above — not only the ones that produced new changelog entries: a PR whose entry already existed still belongs in the release notes. Rewrite those selected commits into docs-appropriate bullets, excluding any entries flagged in `Changelog entries to review`.

1. Determine the in-development Landscape release `YY.MM`: Landscape releases are `YY.04` and `YY.10`. From today's date, the in-development release is the next boundary strictly in the future (before April -> `YY.04`; before October -> `YY.10`; otherwise `(YY+1).04`). As of November 2026 this is **27.04** (betas are underway), so the target page is `docs/reference/release-notes/27.04-release-notes.md`.
2. Find the shared docs PR: use the GitHub tools to list open PRs in `canonical/landscape-documentation` with labels `changelog` and `automation` (title starts with `build: `). If one exists, this is THE docs PR — use it regardless of which `YY.MM` page it targets.
3. If a docs PR exists:
   - In the `./landscape-documentation` checkout, check out that PR's head branch (branches were fetched via the wildcard fetch at setup: `git checkout <branch>`). If the branch is not among the fetched refs, skip the docs work for this run — the agent has no credentials to fetch it.
   - Other Landscape bots push to this same shared branch, so the checkout (fetched at setup time) may be stale and another bot may push while you work. The agent environment has NO git credentials — `git fetch` fails here, so NEVER attempt to fetch or rebase. Work from the PR branch ref as fetched at setup; keep every edit strictly inside your own island markers so it applies cleanly over the other bots' island updates. `push_to_pull_request_branch` applies your patch to the branch's live tip in a credentialed job; if a concurrent push made it conflict, the delivery fails safely — do not retry, the next run redoes the work. NEVER force-push over another bot's commits.
   - Update ONLY your own island (see below). If the release-notes page for the in-development version does not exist on that branch, create it from the template below and add it to the toctree in `docs/reference/release-notes/index.md` (newest non-LTS page goes directly under the LTS entries, matching existing ordering).
   - Commit in the docs checkout and deliver via `push_to_pull_request_branch` with `pull_request_number` set to the docs PR number.
4. If no open docs PR with labels `changelog` + `automation` exists when you run, skip the docs work for this run entirely: make no changes in the `./landscape-documentation` checkout and NEVER create the shared PR — it is created centrally by the `release-notes-draft` workflow (see above), so a missing PR means the next weekly creation will cover the gap. (Your in-repo changelog work above is unaffected.)
5. If you have no user-facing changes this cycle, leave your island untouched; do not create or update the docs PR. (Your own-repo changelog PR logic is unaffected.)

### Your island

Island markers are HTML comments, invisible in rendered docs. Your slug is `landscape-client-charm` and your display name is `Landscape Client charm`. The full island set, in this fixed order:

1. `landscape-server` — Landscape Server
2. `landscape-client` — Landscape Client
3. `landscape-ui` — Web portal
4. `landscape-go` — Snaps (debarchive, outbox, task-handler services)
5. `landscape-server-operator` — Landscape Server charm
6. `landscape-client-charm` — Landscape Client charm
7. `landscape-debarchive-operator` — Debarchive charm
8. `landscape-task-handler-operator` — Task handler charm

Island format inside `## Additional updates`:

```markdown
<!-- changelog-bot:landscape-client-charm:start -->
### Landscape Client charm

#### Features
- <docs-appropriate bullet>

#### Fixes
- <docs-appropriate bullet>
<!-- changelog-bot:landscape-client-charm:end -->
```

Rules:

- BEFORE writing, read `.github/instructions/release-notes.instructions.md` and `.github/instructions/documentation.instructions.md` in the docs checkout and follow them (applicability: state self-hosted vs SaaS and the component; factual, non-promotional; do not invent benefits, migration steps, or breaking-change claims).
- Rewrite your selected commits into user-facing docs bullets: no conventional-commit prefixes, no `(scope)`, no `(#1234)`, no Jira keys. Keep Launchpad references but format them as `[LP: #NNNN](https://bugs.launchpad.net/landscape/+bug/NNNN)`. Write in the style of existing release notes (see any `docs/reference/release-notes/*.md` page): complete sentences, no trailing period inconsistency, admin-focused.
- Omit `#### Features` / `#### Fixes` when empty. If your island has no entries yet, put `(pending)` as the island body.
- NEVER edit outside your own island markers. Other sections belong to other bots.
- When creating the page, include ALL eight islands in the fixed order above (yours filled, the rest with `(pending)`), so later bot runs find their markers.

### New-page template

File `docs/reference/release-notes/YY.MM-release-notes.md` (dots in the filename, matching `26.10-release-notes.md`; anchor uses dashes):

```markdown
---
myst:
  html_meta:
    description: "Release notes for Landscape YY.MM. Draft; updated automatically until release."
---

(reference-release-notes-YY-MM)=
# YY.MM release notes

> Landscape Server YY.MM runs on Ubuntu 26.04 LTS Resolute Raccoon, 24.04 LTS Noble Numbat, or 22.04 LTS Jammy Jellyfish.

```{note}
This page is a draft maintained automatically until release.
```

## Highlights

(pending - written at release time)

## Additional updates

(eight islands here)

## Upgrade

(pending - written at release time)

## Bug fixes

(pending - written at release time)
```
