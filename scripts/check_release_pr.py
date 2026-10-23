"""Validate a dispatched release PR without trusting workflow inputs as shell code."""
import json
import os
import subprocess

from version import semantic_label


def validate_dispatch(pr, repo, sha):
    if (pr['state'] != 'open' or pr['head']['sha'] != sha
            or pr['head']['ref'] != 'automation/release'
            or pr['head']['repo'] is None or pr['head']['repo']['full_name'] != repo
            or pr['base']['ref'] != 'main'):
        raise ValueError('Dispatch must target the current head of the open release PR')
    return semantic_label(label['name'] for label in pr['labels'])


def main():
    number = os.environ['RELEASE_PR']
    if not number.isdecimal():
        raise ValueError('Expected a numeric release PR')
    repo = os.environ['GITHUB_REPOSITORY']
    pr = json.loads(subprocess.check_output(['gh', 'api', f'repos/{repo}/pulls/{number}'], text=True))
    print('Release PR version label:', validate_dispatch(pr, repo, os.environ['GITHUB_SHA']))


if __name__ == '__main__':
    main()
