# Preparing a release

[Project status](../STATUS.md) records what builders can use and which hardware checks remain. Update it when measured results or known limitations change. GitHub Releases records what changed between versions.

## Generated release notes

Pushing a version tag runs [the release workflow](../.github/workflows/release.yml). It checks version consistency across package metadata, current documentation and the PDF, verifies that the tag matches the package version, then creates a **draft** release containing:

- An optional version introduction from `docs/releases/<tag>.md`. The first release has [an introductory summary](releases/v0.9.0.md) because it has no earlier public release to compare against.
- The project status captured from that exact tag.
- GitHub-generated changes, contributors and a changelog link.
- The committed build-guide PDF and a complete source ZIP, including CAD, STLs and license notices.

Version-zero and suffixed tags are marked as pre-releases. The workflow leaves an existing draft or published release unchanged. It can also be run from the Actions page with an existing tag if a run needs retrying.

GitHub's [generated release notes](https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes) summarize merged pull requests. Use descriptive PR titles and these optional labels:

| Labels | Release-note category |
| --- | --- |
| `hardware`, `cad` | Hardware and print files |
| `firmware`, `web` | Firmware and browser controls |
| `documentation` | Build guide and documentation |
| `bug` | Fixes |
| Unlabeled or other labels | Other changes |
| `skip-release-notes` | Excluded |

Labels are configured in [.github/release.yml](../.github/release.yml); create them in GitHub when needed. A PR matching multiple categories appears in the first matching category. Direct commits may not appear as individual entries in the generated summary; describe significant direct changes in the optional version introduction or the release draft. Hardware qualification requires measured results and is not inferred from code changes.

## Release steps

1. Choose the next release version with the [version command](#version-management). Use patch increments for compatible corrections; PR numbers do not determine the version, and multiple PRs can be included in one release.
2. Run the host and browser checks from the [development instructions](../README.md#project-layout-and-development); the PR must also pass all four required CI jobs. Confirm the CAD, STLs, guide, BOM and wiring describe the same build.
3. Commit and push release changes on a topic branch, then open and merge a PR into `main` following [the contribution workflow](../CONTRIBUTING.md). Use the intended public Git author identity.
4. Create an annotated version tag on the merged commit in `main` and push it. For example, the initial release used:

   ```sh
   git tag -a v0.9.0 -m "v0.9.0 — experimental"
   git push origin v0.9.0
   ```

5. Open the generated draft under GitHub Releases, check its notes and downloads, and publish it when ready.

The workflow prepares a draft; publishing is a separate action. It requires GitHub Actions with the repository token's `contents: write` permission for the draft-release job. No additional secret is needed. The workflow operates on the repository and existing version tags on GitHub.

Use patch releases for compatible corrections and minor releases for additions. Call out changes affecting connector pinouts, power wiring or printed-part compatibility in the notes. Keep released tags immutable and make a new release for subsequent changes.

## Version management

`package.json` is the authoritative current version. The [version tool](../scripts/version.py) updates its version, both project entries in `package-lock.json`, the current-version fields in the README and status, the guide's source README and provenance, and the generated PDF:

```sh
uv run scripts/version.py --bump patch
```

Use `minor` or `major` for a larger increment. For an explicit version, use `uv run scripts/version.py --set 0.9.2`. Versions use `X.Y.Z` form; version-zero releases are still marked experimental/pre-release by the release workflow. To repair generated references after manually changing `package.json`, run `--set` with that same version.

Verify without writing files:

```sh
uv run scripts/version.py --check
```

The required `Version consistency` CI job checks current version fields, PDF title/subject and every page footer. Release drafts run the same check. The PDF generator reads the version from `package.json`; it contains no independent version literal.

Historical release notes under `docs/releases/`, old tags and releases, example commands and the v1.0.0 qualification target are intentionally preserved. The tool changes designated current-version fields rather than replacing all version strings. A change to the location or wording of those fields must update the tool's field definitions; a missing or duplicated field fails the check.
