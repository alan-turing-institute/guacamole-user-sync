# Plan

## Release the connection-permission fix as v0.7.1

**Goal:** version-bump and publish the fix implemented in
`specs/2480-guacamole-connections-dissapear/03-fix-recovery.md` as
`guacamole-user-sync` Docker image release **v0.7.1**.

## 1. Version bump

Per `specs/tech_stack.md`, the package version is derived from
`guacamole_user_sync/__about__.py` (`[tool.hatch.version] path =
"guacamole_user_sync/__about__.py"`), and Docker images are published by
`.github/workflows/publish_docker.yaml` on pushes to `main` and on `v*` git
tags (via `docker/metadata-action`, which derives image tags from the git
tag). Two files need updating, in the same PR as the fix:

- `guacamole_user_sync/__about__.py`: `__version__ = "0.7.1"`.
- `tests/test_about.py`: `assert version == "0.7.1"`.

No other file hardcodes the version (checked: `pyproject.toml` uses
`dynamic = ["version"]`; the README's install snippet is already
parameterised as `$(version you want to use)`; there is no `CHANGELOG.md` in
this repo).

## 2. Release step (manual, after merge — do not automate)

Tag the merge commit `v0.7.1` and push the tag, which triggers
`publish_docker.yaml` to build and publish
`ghcr.io/alan-turing-institute/guacamole-user-sync:0.7.1` (and update
`:latest`). Creating/pushing a release tag is a repo-visible,
hard-to-reverse action — confirm with the user before running `git tag` /
`git push --tags`, following the existing tagging convention seen in
`git tag` history (`v0.3.0` … `v0.7.0`).

## 3. Verification

Before tagging, confirm:

- `hatch run test:all` and `hatch run lint:all` are green on the merge
  commit (per `specs/coding-guidelines.md`), including the
  `03-fix-recovery.md` changes.
- The PR that merged the fix called out the new required env vars
  (`GUACAMOLE_ADMIN_GROUP_NAME`, `GUACAMOLE_USER_GROUP_NAME`) and the
  connection-permission enforcement behaviour change, so deployers know to
  update their environment before upgrading to v0.7.1.

After tagging and pushing, confirm the `publish_docker.yaml` workflow run
succeeds and that `ghcr.io/alan-turing-institute/guacamole-user-sync:0.7.1`
is visible in the package registry.
