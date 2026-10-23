"""Prepare a version PR or tag its tested merge; run only from trusted main CI."""
import json
import os
from pathlib import Path
import subprocess

from version import bumped_version, project_version, semantic_label

BRANCH = 'automation/release'
PLAN = '.github/release-plan.json'
VERSION_FILES = [
    'package.json', 'package-lock.json', 'README.md', 'STATUS.md',
    'docs/build-guide/README.md', 'docs/build-guide/provenance.json',
    'docs/Halloween-LEDs-Build-Guide.pdf', PLAN,
]
CHECKS = {'Host tests', 'Browser tests', 'Workflow lint', 'Version consistency'}


def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs).strip()


class GitHub:
    def __init__(self, repo):
        self.repo = repo

    def api(self, path, method='GET', data=None, pages=False):
        args = ['gh', 'api', f'repos/{self.repo}/{path}', '--method', method]
        if pages:
            args += ['--paginate', '--slurp']
        if data is not None:
            args += ['--input', '-']
        result = run(*args, input=json.dumps(data) if data is not None else None)
        value = json.loads(result) if result else None
        return [item for page in value for item in page] if pages else value


def ancestor(base, commit):
    result = subprocess.run(['git', 'merge-base', '--is-ancestor', base, commit], capture_output=True)
    if result.returncode not in (0, 1):
        raise ValueError(f'Cannot establish ancestry for {commit}')
    return result.returncode == 0


def at(commit, path):
    return json.loads(run('git', 'show', f'{commit}:{path}'))


def release_pr(pr, repo):
    return pr['head']['ref'] == BRANCH and pr['head']['repo'] is not None and pr['head']['repo']['full_name'] == repo


def pending_prs(prs, base, head, repo):
    result = []
    for pr in prs:
        sha = pr['merge_commit_sha']
        if (pr['merged_at'] and pr['base']['ref'] == 'main' and not release_pr(pr, repo)
                and sha != base and ancestor(base, sha) and ancestor(sha, head)):
            semantic_label(label['name'] for label in pr['labels'])
            result.append(pr)
    return sorted(result, key=lambda pr: pr['number'])


def make_plan(prs, base_tag, base_sha, source_sha, base_version):
    amounts = [semantic_label(label['name'] for label in pr['labels']) for pr in prs]
    if not amounts:
        return None
    bump = max(amounts, key={'patch': 0, 'minor': 1, 'major': 2}.__getitem__)
    return dict(base_tag=base_tag, base_sha=base_sha, source_sha=source_sha,
                version=bumped_version(base_version, bump), bump=bump,
                pull_requests=[pr['number'] for pr in prs])


def validate_release(plan, expected, changed, version, pr):
    if expected is None or plan != expected:
        raise ValueError('Release plan does not match the pending PRs and their version labels')
    if version != plan['version']:
        raise ValueError('Release version does not match its plan')
    if semantic_label(label['name'] for label in pr['labels']) != plan['bump']:
        raise ValueError('Release PR label does not match its plan')
    unexpected = set(changed) - set(VERSION_FILES)
    if unexpected:
        raise ValueError(f'Release PR includes non-version changes: {sorted(unexpected)}')


def ensure_tag(github, tag, sha):
    refs = github.api('git/matching-refs/tags/' + tag)
    exact = [ref for ref in refs if ref['ref'] == 'refs/tags/' + tag]
    if exact:
        # git resolves annotated and lightweight tags to the same commit.
        run('git', 'fetch', 'origin', 'tag', tag)
        if run('git', 'rev-parse', f'{tag}^{{commit}}') != sha:
            raise ValueError(f'{tag} already points to another commit; tags are immutable')
    else:
        github.api('git/refs', 'POST', {'ref': 'refs/tags/' + tag, 'sha': sha})


def dispatch_ci(github, pr):
    github.api('actions/workflows/ci.yml/dispatches', 'POST', {
        'ref': BRANCH, 'inputs': {'release_pr': str(pr['number'])},
    })


def label_pr(github, pr, bump):
    labels = [item['name'] for item in pr['labels'] if item['name'] not in {'patch', 'minor', 'major'}]
    github.api(f'issues/{pr["number"]}/labels', 'PUT', {'labels': labels + [bump]})


def prepare_pr(github, prs, plan):
    open_prs = github.api(f'pulls?state=open&base=main&head={github.repo.split("/")[0]}:{BRANCH}')
    existing = open_prs[0] if open_prs else None
    if existing:
        remote = run('git', 'ls-remote', 'origin', f'refs/heads/{BRANCH}').split()[0]
        run('git', 'fetch', 'origin', BRANCH)
        if at(remote, PLAN) == plan:
            print(f'Release PR #{existing["number"]} is already current.')
            label_pr(github, existing, plan['bump'])
            dispatch_ci(github, existing)  # Also recovers failures after PR creation.
            return
    else:
        remote_refs = run('git', 'ls-remote', 'origin', f'refs/heads/{BRANCH}').split()
        remote = remote_refs[0] if remote_refs else ''

    run('git', 'switch', '-C', BRANCH, plan['source_sha'])
    run('uv', 'run', 'scripts/version.py', '--set', plan['version'])
    Path(PLAN).parent.mkdir(parents=True, exist_ok=True)
    Path(PLAN).write_text(json.dumps(plan, indent=2) + '\n')
    run('uv', 'run', 'scripts/version.py', '--check')
    run('git', 'config', 'user.name', 'github-actions[bot]')
    run('git', 'config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
    run('git', 'add', '--', *VERSION_FILES)
    run('git', 'commit', '-m', f'Prepare v{plan["version"]}')
    run('gh', 'auth', 'setup-git')
    run('git', 'push', f'--force-with-lease=refs/heads/{BRANCH}:{remote}', 'origin', f'HEAD:refs/heads/{BRANCH}')
    title = f'Release v{plan["version"]}'
    included = '\n'.join(f'- #{pr["number"]}' for pr in prs)
    body = (f'## Summary\n\nPrepare **v{plan["version"]}** using the largest pending increment: '
            f'`{plan["bump"]}`.\n\n```text\nmerge this PR → main CI passes → tag → published release\n```\n\n'
            f'Included PRs:\n\n{included}\n\n## Evidence\n\n'
            '- **Before:** merged changes were not tagged.\n'
            '  **After:** package metadata, current documentation and the rebuilt PDF use the planned version; '
            'the version consistency check passed. All required CI checks must pass before merging.\n\n'
            '## Merge Danger\n\n**Door:** two-way\n\n'
            'Version changes can be revised before merging. After publication, tags remain immutable.\n\n'
            '**Blast Radius:** releases\n\n'
            'Merging this PR authorizes publication after main CI passes. Hardware qualification remains explicit in STATUS.md.\n')
    payload = dict(title=title, body=body)
    if existing:
        pr = github.api(f'pulls/{existing["number"]}', 'PATCH', payload)
    else:
        pr = github.api('pulls', 'POST', dict(payload, head=BRANCH, base='main'))
    # Remove stale semantic labels when the accumulated increment changes.
    label_pr(github, pr, plan['bump'])
    dispatch_ci(github, pr)
    print(f'Prepared {pr["html_url"]}')


def passed_checks(github, sha):
    checks = github.api(f'commits/{sha}/check-runs?per_page=100&filter=latest')['check_runs']
    latest = {}
    for check in checks:
        if check['app']['slug'] == 'github-actions':
            latest.setdefault(check['name'], check['conclusion'])
    return all(latest.get(name) == 'success' for name in CHECKS)


def main():
    github = GitHub(os.environ['GITHUB_REPOSITORY'])
    head = run('git', 'rev-parse', 'HEAD')
    main_sha = github.api('git/ref/heads/main')['object']['sha']
    if subprocess.run(['git', 'cat-file', '-e', main_sha], capture_output=True).returncode:
        run('git', 'fetch', 'origin', main_sha)
    if not ancestor(head, main_sha):
        raise ValueError('Release automation only accepts commits from main')
    # Dispatch recovery must meet the same test gate as the CI caller.
    if os.environ['GITHUB_EVENT_NAME'] == 'workflow_dispatch':
        if not passed_checks(github, head):
            raise ValueError('All four required CI checks must pass before release preparation')
    baseline = github.api('releases/latest')['tag_name']
    base_sha = run('git', 'rev-parse', f'{baseline}^{{commit}}')
    if not ancestor(base_sha, head):
        print('This run predates the latest release; nothing to do.')
        return
    base_version = at(base_sha, 'package.json')['version']
    prs = github.api('pulls?state=closed&base=main&per_page=100', pages=True)
    merged_release = [pr for pr in prs if pr['merged_at'] and release_pr(pr, github.repo)
                      and pr['merge_commit_sha'] != base_sha
                      and ancestor(base_sha, pr['merge_commit_sha'])
                      and ancestor(pr['merge_commit_sha'], head)]
    if merged_release:
        if len(merged_release) != 1:
            raise ValueError('Expected at most one unpublished release PR')
        release_sha = merged_release[0]['merge_commit_sha']
        if not passed_checks(github, release_sha):
            print('The release merge is still waiting for all four CI checks to pass.')
            return
        plan = at(release_sha, PLAN)
        source = plan['source_sha']
        if not ancestor(base_sha, source) or not ancestor(source, release_sha):
            raise ValueError('Release source must follow the previous release on main')
        pending = pending_prs(prs, base_sha, source, github.repo)
        expected = make_plan(pending, baseline, base_sha, source, base_version)
        changed = run('git', 'diff', '--name-only', source, release_sha).splitlines()
        validate_release(plan, expected, changed, at(release_sha, 'package.json')['version'], merged_release[0])
        run('git', 'switch', '--detach', release_sha)
        run('uv', 'run', 'scripts/version.py', '--check')
        tag = 'v' + plan['version']
        ensure_tag(github, tag, release_sha)
        with Path(os.environ['GITHUB_OUTPUT']).open('a') as output:
            output.write(f'tag={tag}\n')
        print(f'Tested release merge is ready to publish: {tag}')
        return
    if head != main_sha:
        print('Newer main changes exist; their CI run will update the release PR.')
        return
    if project_version(Path.cwd()) != base_version:
        print('A version change is awaiting publication; leaving the release PR unchanged.')
        return
    pending = pending_prs(prs, base_sha, head, github.repo)
    plan = make_plan(pending, baseline, base_sha, head, base_version)
    if plan:
        prepare_pr(github, pending, plan)
    else:
        print('No unreleased PRs; nothing to do.')


if __name__ == '__main__':
    main()
