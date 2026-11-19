# project-boards

Keeps the usegalaxy-eu GitHub project boards up to date, so each group's board shows its real work without people adding cards by hand.

Every hour, `sync.py` looks for open PRs written by the people in `boards.yml` and for open issues or PRs assigned to them. It adds each one to the board that its repo belongs to, and on boards that allow it, it sets the status of PRs: draft PRs go to "In progress", ready PRs to "In review".

It never closes anything and never sets Done; each board's own "Item closed" and "Pull request merged" rules do that. It leaves cards alone that someone moved by hand (for example to Blocked) or archived.

## Add your group's board

Edit `boards.yml` in a PR: add your board, the repos that belong to it, and pick a mode:

- `off`: nothing happens, but the repos are kept off other boards
- `add`: only add missing cards
- `status`: add missing cards and move PRs between the statuses you list

Add people to `people` if their work should be synced.

## Run it

Locally, as a dry run (it only prints what it would change):

```bash
GITHUB_TOKEN=$(gh auth token) python3 sync.py
```

Add `--apply` to make the changes. Tests: `python3 -m unittest`.

In GitHub Actions it uses the [galaxy-eu-project-boards](https://github.com/apps/galaxy-eu-project-boards) app (variable `APP_CLIENT_ID`, secret `APP_PRIVATE_KEY`). Scheduled runs are dry runs until the repo variable `APPLY` is set to `true`; you can also run it by hand from the Actions tab with "apply" ticked.
