"""Release planning uses real commit ancestry and mocked GitHub responses."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('release_automation', ROOT / 'scripts/release.py')
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)
from check_release_pr import validate_dispatch


def pr(number, sha, labels=('patch',), branch='feature', merged=True, repo='owner/project'):
    return dict(number=number, merge_commit_sha=sha, merged_at='now' if merged else None,
                labels=[{'name': name} for name in labels], base={'ref': 'main'},
                head={'ref': branch, 'repo': {'full_name': repo}})


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.previous = Path.cwd()
        os.chdir(self.temp.name)
        self.addCleanup(os.chdir, self.previous)
        self.git('init', '-q', '-b', 'main')
        self.git('config', 'user.email', 'test@example.com')
        self.git('config', 'user.name', 'Test')
        Path('package.json').write_text(json.dumps({'version': '0.9.2'}))
        self.base = self.commit('base')
        self.patch = self.commit('patch')
        self.minor = self.commit('minor')
        self.prs = [pr(1, self.base), pr(2, self.patch), pr(3, self.minor, ('minor',))]

    def git(self, *args):
        return subprocess.check_output(['git', *args], text=True).strip()

    def commit(self, content):
        Path('change.txt').write_text(content)
        self.git('add', '.')
        self.git('commit', '-qm', content)
        return self.git('rev-parse', 'HEAD')

    def plan(self):
        pending = release.pending_prs(self.prs, self.base, self.minor, 'owner/project')
        return release.make_plan(pending, 'v0.9.2', self.base, self.minor, '0.9.2')

    def test_aggregates_highest_label_with_one_increment(self):
        plan = self.plan()
        self.assertEqual(plan['version'], '0.10.0')
        self.assertEqual(plan['pull_requests'], [2, 3])
        self.prs[1]['labels'].append({'name': 'documentation'})
        self.prs[2]['labels'] = [{'name': 'major'}]
        self.assertEqual(self.plan()['version'], '1.0.0')

    def test_ignores_released_unmerged_and_unrelated_prs(self):
        self.git('switch', '-qc', 'other', self.base)
        unrelated = self.commit('unrelated')
        self.prs.extend([pr(4, unrelated, ()), pr(5, self.minor, (), merged=False)])
        self.assertEqual(self.plan()['pull_requests'], [2, 3])
        self.assertIsNone(release.make_plan([], 'v0.9.2', self.base, self.base, '0.9.2'))

    def test_release_branch_excluded_only_for_same_repository(self):
        self.prs.append(pr(4, self.minor, branch=release.BRANCH))
        self.assertEqual(self.plan()['pull_requests'], [2, 3])
        self.prs[-1]['head']['repo']['full_name'] = 'fork/project'
        self.assertEqual(self.plan()['pull_requests'], [2, 3, 4])

    def test_fails_for_unlabeled_or_conflicting_pending_pr(self):
        for labels in ([], [{'name': 'minor'}, {'name': 'patch'}]):
            self.prs[1]['labels'] = labels
            with self.assertRaisesRegex(ValueError, 'exactly one'):
                self.plan()

    def test_release_validation_rejects_stale_plan_wrong_version_and_extra_code(self):
        expected = self.plan()
        release_pr = pr(4, self.minor, ('minor',), release.BRANCH)
        release.validate_release(expected, expected, release.VERSION_FILES, '0.10.0', release_pr)
        stale = dict(expected, pull_requests=[2])
        for plan, files, version in ((stale, [], '0.10.0'), (expected, [], '0.9.3'),
                                      (expected, ['firmware/code.py'], '0.10.0')):
            with self.subTest(plan=plan, files=files, version=version), self.assertRaises(ValueError):
                release.validate_release(plan, expected, files, version, release_pr)
        release_pr['labels'] = [{'name': 'patch'}]
        with self.assertRaisesRegex(ValueError, 'label'):
            release.validate_release(expected, expected, [], '0.10.0', release_pr)

    def test_tag_creation_is_idempotent_and_never_moves_a_tag(self):
        calls = []
        class GitHub:
            def api(inner, path, method='GET', data=None):
                calls.append((path, method, data))
                return [] if method == 'GET' else None
        github = GitHub()
        release.ensure_tag(github, 'v0.9.3', self.minor)
        self.assertEqual(calls[-1], ('git/refs', 'POST', {'ref': 'refs/tags/v0.9.3', 'sha': self.minor}))
        self.git('tag', 'v0.9.3', self.minor)
        with patch.object(github, 'api', return_value=[{'ref': 'refs/tags/v0.9.3'}]):
            with patch.object(release, 'run', side_effect=['', self.minor]) as run:
                release.ensure_tag(github, 'v0.9.3', self.minor)
                self.assertEqual(run.call_count, 2)
            with patch.object(release, 'run', side_effect=['', self.base]):
                with self.assertRaisesRegex(ValueError, 'immutable'):
                    release.ensure_tag(github, 'v0.9.3', self.minor)

    def test_ci_gate_requires_each_check_from_github_actions(self):
        checks = [{'name': name, 'conclusion': 'success', 'app': {'slug': 'github-actions'}}
                  for name in release.CHECKS]
        class GitHub:
            def api(inner, path):
                return {'check_runs': checks}
        self.assertTrue(release.passed_checks(GitHub(), self.minor))
        checks[0]['conclusion'] = 'failure'
        self.assertFalse(release.passed_checks(GitHub(), self.minor))
        checks[0]['conclusion'] = 'success'
        checks[0]['app']['slug'] = 'other-app'
        self.assertFalse(release.passed_checks(GitHub(), self.minor))

    def test_dispatched_ci_rejects_stale_fork_closed_or_unlabeled_prs(self):
        candidate = pr(9, self.minor, branch=release.BRANCH)
        candidate['state'] = 'open'
        candidate['head']['sha'] = self.minor
        self.assertEqual(validate_dispatch(candidate, 'owner/project', self.minor), 'patch')
        for field, value in [('state', 'closed'), ('sha', self.base), ('repo', None),
                             ('repo', {'full_name': 'fork/project'}), ('ref', 'feature'), ('labels', [])]:
            changed = copy.deepcopy(candidate)
            if field in {'sha', 'repo', 'ref'}:
                changed['head'][field] = value
            else:
                changed[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                validate_dispatch(changed, 'owner/project', self.minor)

    def test_preparation_reuses_pr_and_rebuilds_from_main_without_compounding(self):
        remote_temp = tempfile.TemporaryDirectory()
        self.addCleanup(remote_temp.cleanup)
        remote = remote_temp.name
        self.git('init', '--bare', '-q', remote)
        self.git('remote', 'add', 'origin', remote)
        for name in release.VERSION_FILES:
            if name == release.PLAN:
                continue
            path = Path(name)
            path.parent.mkdir(parents=True, exist_ok=True)
            if name != 'package.json':
                path.write_text('fixture')
        self.git('add', '--', *[n for n in release.VERSION_FILES if n != release.PLAN])
        self.git('commit', '-qm', 'version fixture')
        source = self.git('rev-parse', 'HEAD')
        github_calls = []
        class GitHub:
            repo = 'owner/project'
            current = None
            def api(inner, path, method='GET', data=None):
                github_calls.append((path, method, data))
                if method == 'GET':
                    return [inner.current] if inner.current else []
                if path == 'pulls':
                    inner.current = dict(number=9, html_url='https://example/pr/9', labels=[])
                if path.startswith('issues/'):
                    inner.current['labels'] = [{'name': name} for name in data['labels']]
                return inner.current
        github = GitHub()
        pending = [pr(3, self.minor, ('minor',))]
        plan = release.make_plan(pending, 'v0.9.2', self.base, source, '0.9.2')
        real_run = release.run
        def execute(*args, **kwargs):
            if args[:2] == ('uv', 'run'):
                if '--set' in args:
                    Path('package.json').write_text(json.dumps({'version': args[-1]}))
                return ''
            if args[:3] == ('gh', 'auth', 'setup-git'):
                return ''
            return real_run(*args, **kwargs)
        with patch.object(release, 'run', side_effect=execute):
            release.prepare_pr(github, pending, plan)
            first_head = self.git('rev-parse', 'HEAD')
            self.assertEqual(release.at(first_head, release.PLAN), plan)
            release.prepare_pr(github, pending, plan)
            self.assertEqual(self.git('rev-parse', 'HEAD'), first_head)
            self.git('switch', '-q', 'main')
            updated_source = self.commit('new major change')
            pending.append(pr(4, updated_source, ('major',)))
            updated = release.make_plan(pending, 'v0.9.2', self.base, updated_source, '0.9.2')
            release.prepare_pr(github, pending, updated)
            self.assertEqual(json.loads(Path('package.json').read_text())['version'], '1.0.0')
            self.assertEqual(github.current['labels'], [{'name': 'major'}])
            self.assertEqual(self.git('rev-parse', 'HEAD^'), updated_source)
        self.assertEqual(sum(path == 'pulls' and method == 'POST' for path, method, data in github_calls), 1)
        self.assertEqual(sum('dispatches' in path for path, method, data in github_calls), 3)

    def test_merged_release_is_found_even_when_main_has_advanced(self):
        plan = self.plan()
        # Commit only the generated version files, as a release PR would.
        source = self.minor
        Path('package.json').write_text(json.dumps({'version': plan['version']}))
        Path('.github').mkdir()
        Path(release.PLAN).write_text(json.dumps(plan))
        self.git('add', '.')
        self.git('commit', '-qm', 'Release PR')
        merged_sha = self.git('rev-parse', 'HEAD')
        latest = self.commit('later feature')
        prs = self.prs + [pr(4, merged_sha, ('minor',), release.BRANCH), pr(5, latest)]
        self.git('tag', 'v0.9.2', self.base)
        class GitHub:
            repo = 'owner/project'
            def __init__(inner, repo):
                pass
            def api(inner, path, **kwargs):
                if path == 'git/ref/heads/main':
                    return {'object': {'sha': latest}}
                if path == 'releases/latest':
                    return {'tag_name': 'v0.9.2'}
                if path.startswith('pulls?'):
                    return prs
                raise AssertionError(path)
        output = str(Path('output.txt').resolve())
        with patch.object(release, 'GitHub', GitHub), patch.object(release, 'passed_checks', return_value=True), \
                patch.object(release, 'ensure_tag') as tag, \
                patch.dict(os.environ, GITHUB_REPOSITORY='owner/project', GITHUB_EVENT_NAME='push', GITHUB_OUTPUT=output):
            real_run = release.run
            def execute(*args, **kwargs):
                if args[:2] == ('uv', 'run'):
                    return ''
                return real_run(*args, **kwargs)
            with patch.object(release, 'run', side_effect=execute):
                release.main()
            tag.assert_called_once()
            self.assertEqual(tag.call_args.args[1:], ('v0.10.0', merged_sha))
        self.assertEqual(Path(output).read_text(), 'tag=v0.10.0\n')
        self.assertEqual(release.at(merged_sha, release.PLAN)['source_sha'], source)


if __name__ == '__main__':
    unittest.main()
