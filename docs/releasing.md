# Preparing a release

[Project status](../STATUS.md) records what builders can use and which hardware checks remain. Update it when measured results or known limitations change. GitHub Releases records what changed between versions.

## Generated release notes

Pushing a version tag runs [the release workflow](../.github/workflows/release.yml). It checks that the tag matches `package.json` and `package-lock.json`, then creates a **draft** release containing:

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

1. Update the package version, lockfile, README, status and guide edition. Rebuild the guide when its source changes.
2. Run the host and browser checks from the [development instructions](../README.md#project-layout-and-development). Confirm the CAD, STLs, guide, BOM and wiring describe the same build.
3. Commit and push the source, including the release workflow and configuration. Use the intended public Git author identity.
4. Create an annotated version tag on that commit and push it. For the initial release:

   ```sh
   git tag -a v0.9.0 -m "v0.9.0 — experimental"
   git push origin v0.9.0
   ```

5. Open the generated draft under GitHub Releases, check its notes and downloads, and publish it when ready.

The workflow prepares a draft; publishing is a separate action. It requires GitHub Actions with the repository token's `contents: write` permission for the draft-release job. No additional secret is needed. The workflow operates on the repository and existing version tags on GitHub.

Use patch releases for compatible corrections and minor releases for additions. Call out changes affecting connector pinouts, power wiring or printed-part compatibility in the notes. Keep released tags immutable and make a new release for subsequent changes.
