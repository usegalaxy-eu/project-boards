# project-boards

Keeps the usegalaxy-eu GitHub project boards up to date, so each group's board shows its real work without people adding cards by hand.

## Why

We want the [Dev Tasks board](https://github.com/orgs/usegalaxy-eu/projects/24) to be the place where you can see what each of us is working on. Today cards are added by hand, so a lot is missing: when this was set up, more than 70 open PRs and issues of the team were not on the board. GitHub's built-in auto-add can't fill the gap: our plan allows only one auto-add rule (one repo), it can't filter by author, and it only picks up new or updated items.

The work is also spread over many repos (galaxyproject, usegalaxy-eu, ...), and not all of it is dev work. Ops repos belong to the [Admin Tasks board](https://github.com/orgs/usegalaxy-eu/projects/2), tool repos to a future Tools board. So one config file decides which repo goes to which board, and other groups can add their board to it.

## What it does

Every hour, `sync.py`:

1. Finds the open PRs written by the people in `boards.yml`, and the open issues and PRs assigned to them, updated in the last 90 days.
2. Picks the board for each one from its repo (see below).
3. Adds it to that board if it is not there yet.
4. On boards with `mode: status`, moves PRs: draft PRs to "In progress", ready PRs to "In review". It only moves a card that has no status or is in Backlog or In progress, so a card someone moved to Blocked or Ready stays where it is.

It never closes anything and never sets Done; each board's own "Item closed" and "Pull request merged" rules do that. It leaves archived cards alone. To keep an item off a board, archive its card: a deleted card comes back on the next run.

## Which repo goes where

Each repo goes to the first board in `boards.yml` whose patterns match it. Right now:

- Admin Tasks: the ops repos (`infrastructure*`, `ansible-*`, `vgcn*`, `pulsar-*`, `operations`, ...). Mode `off` until the admins decide, so nothing is added there yet.
- Tools: `bgruening/galaxytools`, `usegalaxy-eu-tools`, the `docker-*` interactive tool images, ... Mode `off`, the board does not exist yet.
- Dev Tasks: everything else in `galaxyproject/*` and `usegalaxy-eu/*`. Mode `status`.

A board that is `off` still claims its repos, so for example an `ansible-*` PR never lands on Dev Tasks. Repos outside our two orgs are only synced when listed by name. Never synced: the `skip_repos` list (tools-iuc, which the Tool Developers SIG board adds itself, `usegalaxy-eu/issues`, and the paper repos) and people's own personal repos.

## Add your group's board

Edit `boards.yml` in a PR: add your board, the repos that belong to it, and pick a mode:

- `off`: nothing happens, but the repos are kept off other boards
- `add`: only add missing cards
- `status`: add missing cards and move PRs between the statuses you list

Add people to `people` if their work should be synced. The next run picks up the change.

## Run it

Locally, as a dry run (it only prints what it would change):

```bash
GITHUB_TOKEN=$(gh auth token) uv run sync.py
```

Add `--apply` to make the changes. Tests: `uv run --with pyyaml -m unittest`. You only need [uv](https://docs.astral.sh/uv/); it brings Python and PyYAML.

In GitHub Actions it uses the [galaxy-eu-project-boards](https://github.com/apps/galaxy-eu-project-boards) app (variable `APP_CLIENT_ID`, secret `APP_PRIVATE_KEY`). The app can only edit org project boards and read issues and PRs; it has no write access to any repo. Scheduled runs are dry runs until the repo variable `APPLY` is set to `true`, and each run lists what it would change in its summary. You can also run it by hand from the Actions tab, with or without "apply" ticked.
