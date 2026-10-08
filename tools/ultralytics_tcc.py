"""Safe first-stage Platform automation; no paid launch or dataset mutation.

Commands intentionally remain read-only until the final dataset and enforceable
billing controls exist. Credentials are accepted only from the process environment.
The API schema is checked before authenticated requests; no response URLs/tokens
are printed. Never interpret a successful access check as import verification.
"""
import argparse
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from finalize_tcc_dataset import inspect, usage_report
from pathlib import Path

BASE = 'https://platform.ultralytics.com'
NAME = re.compile(r'^[a-z0-9]+(?:-[a-z0-9]+)*$')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        # Never forward Authorization to redirected API or storage hosts.
        return None


class Platform:
    def __init__(self, key=None):
        self.key = key if key is not None else os.environ.get('ULTRALYTICS_API_KEY', '')
        if not re.fullmatch(r'ul_[0-9a-f]{40}', self.key):
            raise ValueError('Provide an Ultralytics key (ul_ followed by 40 hexadecimal characters) through the local environment or secure access dialog')
        self.opener = build_opener(NoRedirect())
        self.schema = self._get('/openapi.json', authenticated=False)
        if not isinstance(self.schema.get('paths'), dict):
            raise ValueError('Invalid official OpenAPI contract')

    def _get(self, path, authenticated=True):
        headers = {'Accept': 'application/json'}
        if authenticated:
            headers['Authorization'] = 'Bearer '+self.key
        request = Request(BASE+path, headers=headers)
        try:
            with self.opener.open(request, timeout=30) as response:
                return json.load(response)
        except HTTPError as exc:
            # Provider messages/URLs may contain signed credentials. Do not log.
            raise ValueError(f'Platform HTTP {exc.code}; no operation retried') from None
        except (URLError, TimeoutError, json.JSONDecodeError):
            raise ValueError('Platform unavailable or invalid JSON; no operation retried') from None

    def get(self, route, **names):
        if 'get' not in self.schema['paths'].get(route, {}):
            raise ValueError('GET operation absent from official OpenAPI contract')
        path = route
        for name, value in names.items():
            if not NAME.fullmatch(value):
                raise ValueError('Invalid Platform resource name')
            path = path.replace('{'+name+'}', value)
        if '{' in path:
            raise ValueError('Missing resource name')
        return self._get(path)


def dataset_preflight(manifests, registry, usage='private'):
    records = []
    for filename in manifests:
        manifest = Path(filename).resolve()
        for line in manifest.read_text(encoding='utf-8-sig').splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            path = Path(record['path'])
            record['path'] = str(path if path.is_absolute() else manifest.parent/path)
            records.append(record)
    sources = json.loads(Path(registry).read_text(encoding='utf-8-sig'))
    errors = inspect(records, sources, usage=usage)
    return {'status': 'NOT_FINAL' if errors else 'LOCAL_FINAL_CRITERIA_PASS',
            'images': len(records), 'groups': len({r['group'] for r in records}),
            'blockers': errors, 'platform_import_verified': False, 'job_launched': False,
            'usage_policy': usage_report(records, sources, usage)}


def access_report(client, owner):
    client.get('/api/account/summary')
    client.get('/api/billing/usage-summary')
    datasets = client.get('/api/datasets/{owner}', owner=owner)
    return {'authenticated': True, 'workspace': owner,
            'dataset_read_access': True, 'billing_read_access': True,
            'datasets_returned': len(datasets['datasets']),
            'write_permission_verified': False, 'job_launched': False,
            'notice': 'Read access does not prove editor permission, import identity, or a safe cost cap.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    pre = sub.add_parser('preflight', help='Offline final-dataset audit, no credentials/network')
    pre.add_argument('--manifest', action='append', required=True)
    pre.add_argument('--registry', required=True)
    pre.add_argument('--usage', choices=['private', 'redistributable'], default='private')
    access = sub.add_parser('check-access', help='Read identity/workspace/billing, never print credentials')
    access.add_argument('--owner', required=True)
    status = sub.add_parser('status', help='One read-only training progress check, not a billing watchdog')
    status.add_argument('--owner', required=True)
    status.add_argument('--project', required=True)
    status.add_argument('--model', required=True)
    for command in ('import', 'train', 'export'):
        sub.add_parser(command, help='Blocked until remaining implementation and safety gates pass')
    args = parser.parse_args()
    if args.command == 'preflight':
        report = dataset_preflight(args.manifest, args.registry, args.usage)
        print(json.dumps(report, indent=2))
        return 2 if report['blockers'] else 0
    if args.command in {'import', 'train', 'export'}:
        print(json.dumps({'status': 'BLOCKED', 'job_launched': False,
                          'reason': 'Final dataset, authenticated import, billing exposure control and resumable mutation workflow not yet verified. No remote mutation performed.'}))
        return 2
    client = Platform()
    if args.command == 'check-access':
        report = access_report(client, args.owner)
    else:
        response = client.get('/api/models/{owner}/{project}/{model}/training',
                              owner=args.owner, project=args.project, model=args.model)
        job = response.get('job')
        report = {'job': None} if job is None else {
            'id': job['id'], 'status': job['status'],
            'progress': job['progress'], 'job_launched': False}
    print(json.dumps(report, indent=2))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
