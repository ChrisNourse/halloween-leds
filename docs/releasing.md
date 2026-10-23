# Publishing a release

[Project status](../STATUS.md) records what builders can use and which hardware checks remain. Update it when measured results or known limitations change. GitHub Releases records what changed between versions.

## Generated release notes

Pushing a version tag runs [the release workflow](../.github/workflows/release.yml). It checks version consistency across package metadata, current documentation and the PDF, verifies that the tag matches the package version, then publishes a release containing:

- An optional version introduction from `docs/releases/<tag>.md`. The first release has [an introductory summary](releases/v0.9.0.md) because it has no earlier public release to compare against.
- The project status captured from that exact tag.
- GitHub-generated changes, contributors and a changelog link.
- The committed build-guide PDF and a complete source ZIP, including CAD, STLs and license notices.

Plain `vX.Y.Z` tags, including `v0.x.y`, are published as regular releases and marked **Latest**. Experimental hardware status remains explicit in the included project status; the GitHub pre-release flag is not a hardware qualification claim. Suffixed tags are marked as pre-releases and do not replace Latest. The version tool currently supports only plain `X.Y.Z` versions. The workflow leaves published releases unchanged and reports an existing draft as an error requiring recovery. It can also be run from the Actions page with an existing tag if a run needs retrying.

GitHub's [generated release notes](https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes) summarize merged pull requests. Use descriptive PR titles and these optional labels:

| Labels | Release-note category |
| --- | --- |
| `hardware`, `cad` | Hardware and print files |
| `firmware`, `web` | Firmware and browser controls |
| `documentation` | Build guide and documentation |
| `bug` | Fixes |
| Unlabeled or other labels | Other changes |
| `skip-release-notes` | Excluded |

Labels are configured in [.github/release.yml](../.github/release.yml); create them in GitHub when needed. A PR matching multiple categories appears in the first matching category. Direct commits may not appear as individual entries in the generated summary; describe significant direct changes in the optional version introduction or the release notes. Hardware qualification requires measured results and is not inferred from code changes.

## Release steps

1. Give each ordinary PR exactly one `patch`, `minor` or `major` label and merge it after the required checks pass. Keep the current version unchanged in ordinary PRs.
2. After all four main CI checks pass, automation opens or updates a single **Release vX.Y.Z** PR from `automation/release`. It collects merged PRs since the latest published release and applies the largest increment once. For example, two patches and one minor produce one minor release.
3. Review that release PR’s included PR list, version changes, rebuilt PDF and current hardware status. All four required checks run explicitly on its current head, even though GitHub’s built-in token created the PR. New merged changes update the release PR; the generated branch is replaced from main, so put substantive edits in ordinary PRs rather than editing the generated branch.
4. Merge the release PR. Once all four CI checks pass on its main merge commit, automation creates the matching tag and publishes the release with generated notes and downloads. No local tagging command is needed. A normal feature PR does not itself publish a release.
5. Verify the published release and Latest badge. Any changes merged during publication are collected into the next release PR after their checks pass.

Automation uses GitHub’s built-in repository token, with `contents: write`, `pull-requests: write` and `actions: write` scoped to release preparation. The repository setting **Allow GitHub Actions to create and approve pull requests** must be enabled so the bot can create PRs; the workflow does not approve or merge them. Main keeps its existing PR and CI requirements. No personal token or additional secret is needed.

The [release automation workflow](../.github/workflows/release-automation.yml) can be run manually on `main` to retry preparation or publication after fixing a failure. Manual recovery requires all four checks to have passed on that commit. Retries reuse the same release plan, validate existing tags instead of moving them, and leave published releases unchanged. If a failed upload leaves a draft, repair or delete that draft before retrying publication; automation reports the draft rather than treating it as published.

The tag-triggered publishing workflow and its manual existing-tag input remain available for recovery. Normally the release automation calls that workflow directly: tags created with the built-in token do not reliably trigger another workflow. Existing historical tags remain immutable.

Use patch releases for compatible corrections and minor releases for additions. Call out changes affecting connector pinouts, power wiring or printed-part compatibility in the notes. Hardware qualification still requires measured results, and v1.0.0 remains reserved for the qualified build. Do not use a `major` label before the project is ready for that milestone.

## Version management

Every PR must carry exactly one `patch`, `minor` or `major` label. The required `Version consistency` job fails for missing or conflicting labels and reruns when labels are added or removed. Other labels still control the release-note categories above. Automation reads these labels after merge and uses the largest pending increment to prepare one release PR. The generated release PR carries that same increment label and a committed `.github/release-plan.json` recording its source, baseline and included PRs. Publication verifies the plan against the merged PRs and refuses unrelated changes in the release PR.

`package.json` is the authoritative current version. The release PR runs the version tool automatically; the commands below are for local inspection or manual recovery. The [version tool](../scripts/version.py) updates its version, both project entries in `package-lock.json`, the current-version fields in the README and status, the guide's source README and provenance, and the generated PDF:

```sh
uv run scripts/version.py --bump patch
```

Use `minor` or `major` for a larger increment. For an explicit version, use `uv run scripts/version.py --set 0.9.2`. Versions use `X.Y.Z` form; version-zero releases are published as regular GitHub releases while their documentation continues to describe experimental hardware status. To repair generated references after manually changing `package.json`, run `--set` with that same version.

Verify without writing files:

```sh
uv run scripts/version.py --check
```

The required `Version consistency` CI job checks current version fields, PDF title/subject and every page footer. Release publication runs the same check. The PDF generator reads the version from `package.json`; it contains no independent version literal.

Historical release notes under `docs/releases/`, old tags and releases, example commands and the v1.0.0 qualification target are intentionally preserved. The tool changes designated current-version fields rather than replacing all version strings. A change to the location or wording of those fields must update the tool's field definitions; a missing or duplicated field fails the check.
