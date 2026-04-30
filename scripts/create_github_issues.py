#!/usr/bin/env python3
import os
import sys
import json
import urllib.request
import urllib.error

def post_issue(repo, token, issue):
    url = f"https://api.github.com/repos/{repo}/issues"
    data = json.dumps(issue).encode('utf-8')
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Authorization', f'token {token}')
    req.add_header('Accept', 'application/vnd.github+json')
    req.add_header('User-Agent', 'p3_xdei-issue-creator')
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req) as resp:
            resp_data = json.load(resp)
            return resp_data
    except urllib.error.HTTPError as e:
        try:
            err = e.read().decode('utf-8')
            return {'error': e.code, 'message': err}
        except Exception:
            return {'error': e.code, 'message': str(e)}

def main():
    if 'GH_TOKEN' not in os.environ:
        print('GH_TOKEN environment variable not set', file=sys.stderr)
        sys.exit(2)
    token = os.environ['GH_TOKEN']
    if len(sys.argv) < 2:
        print('Usage: create_github_issues.py owner/repo', file=sys.stderr)
        sys.exit(2)
    repo = sys.argv[1]
    issues_path = os.path.join(os.path.dirname(__file__), 'issues.json')
    if not os.path.exists(issues_path):
        print('issues.json not found', file=sys.stderr)
        sys.exit(2)
    with open(issues_path, 'r') as f:
        issues = json.load(f)

    created = []
    for i, issue in enumerate(issues, start=1):
        print(f'Creating issue {i}/{len(issues)}: {issue.get("title")}', flush=True)
        resp = post_issue(repo, token, issue)
        if resp is None:
            print('No response for issue', issue.get('title'))
            continue
        if 'html_url' in resp:
            print('CREATED:', resp['html_url'])
            created.append(resp['html_url'])
        else:
            print('ERROR creating issue:', resp)

    print('\nSummary:')
    print(f'{len(created)}/{len(issues)} issues created')
    for url in created:
        print(url)

if __name__ == '__main__':
    main()
