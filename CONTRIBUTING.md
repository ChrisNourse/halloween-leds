# Contributing

All updates to `main` go through pull requests, including documentation, CAD and workflow changes. Create a topic branch from the current `main`, commit and push your changes there, then open a PR targeting `main`. Merge the PR through GitHub; preserve branch protection rather than pushing directly or using an administrator bypass.

`main` requires a PR for everyone, including administrators. Force-pushes and branch deletion are blocked, and review conversations must be resolved before merging. An additional approving reviewer is optional so the maintainer can merge their own PRs. The `Host tests`, `Browser tests`, `Workflow lint` and `Version consistency` checks must pass, with the branch up to date with `main`.

The [CI workflow](.github/workflows/ci.yml) runs on every PR, including stacked PRs, and after merges to `main`. Browser failures include a downloadable HTML report and traces, retained for seven days. These checks run host simulations and browser tests; hardware qualification still requires measurements on the assembled device.

Every PR requires **exactly one** of the `patch`, `minor` or `major` labels. The required `Version consistency` job checks this on PR creation, code updates and label changes. Missing or conflicting version labels fail the check; other labels may be added freely. Choose `patch` for compatible corrections, `minor` for compatible additions, and `major` for incompatible changes. Version-zero releases still follow this project convention, with v1.0.0 reserved for the qualified build.

Use descriptive PR titles: they become entries in generated release notes. Add the relevant labels listed in [the release process](docs/releasing.md#generated-release-notes).

Run checks appropriate to your changes using the [development instructions](README.md#project-layout-and-development), and describe validation and any remaining limitations in the PR. For hardware changes, record measured results separately from digital checks and update [project status](STATUS.md) when qualification changes.

Prepare releases from changes that have been merged into `main`. Follow [the release process](docs/releasing.md); existing release tags remain unchanged.

For version changes, use `uv run scripts/version.py --bump patch` (or `minor` / `major`, matching the selected label) to update `package.json`, synchronize current documentation and metadata, and rebuild the PDF. Labels classify the intended increment; they do not currently run the bump command automatically. Use `uv run scripts/version.py --check` to verify versions without changing files. See [version management](docs/releasing.md#version-management) for explicit version selection and historical references.
