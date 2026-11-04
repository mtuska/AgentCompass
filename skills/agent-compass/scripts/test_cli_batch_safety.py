"""Real subprocess dispatch tests; no provider credentials or live workers required."""
import json
import os
from pathlib import Path
import sys
import time
from types import SimpleNamespace
from unittest.mock import patch

import allocator
import cli_worker
import roll
import usage_core


def test_unknown_and_argon_limits_survive_explicit_draws():
    payload = {'status': 'SUCCESS', 'command': {'name': 'usage', 'data': {'groups': [{'buckets': [
        {'id': 'gemini-weekly', 'remaining_fraction': 1},
        {'id': 'gemini-argon-wtu-weekly', 'remaining_fraction': 0},
        {'id': 'future-limit', 'remaining_fraction': .2},
    ]}]}}}
    windows = {w.id: vars(w) for w in usage_core._parse_antigravity_usage(payload)}
    assert windows['gemini-argon-wtu-weekly']['used_pct'] == 100
    account = {'accounts': {'a': {'windows': {'gemini-weekly': {}}}}}
    for draws in ([], ['gemini-weekly']):
        bundle = {'account': 'a', 'model': 'gemini-4-argon', 'draws': draws}
        pools = allocator.bundle_pools(bundle, account, windows)
        assert 'gemini-argon-wtu-weekly' in pools and 'future-limit' in pools
        assert 'gemini-argon-wtu-weekly' not in allocator.bundle_pools(
            {**bundle, 'model': 'gemini-flash'}, account, windows)


def test_seven_parallel_cli_workers_have_isolated_artifacts_and_receipts(tmp_path, monkeypatch):
    fake = tmp_path / 'fake.py'
    fake.write_text('''import json, sys, time
from pathlib import Path
text = sys.stdin.read()
time.sleep(.15)
report = dict(status='completed', summary='checked', deliverable=text.splitlines()[0], verification='fixture')
Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text(json.dumps(report))
print(json.dumps(report))
''')
    monkeypatch.setenv('ROUTER_STATE_DIR', str(tmp_path))
    monkeypatch.setattr(roll, 'CLI_RUNS_DIR', tmp_path / 'runs')
    monkeypatch.setattr(roll, 'provider_definition', lambda *a, **k: ('codex', {}))
    monkeypatch.setattr(roll, 'cli_command', lambda *a: [sys.executable, str(fake)])
    judge = SimpleNamespace(subscription_env=lambda: dict(os.environ))
    results = []
    for i in range(7):
        result, code = roll.cli(SimpleNamespace(wait=0, execution_mode='read-only'),
            {'parent_id': 'fixture-parent', 'parent_host': 'native', 'parent_address': 'fixture-inbox'},
            {'provider': 'codex', 'account': 'fixture', 'model': 'fixture'}, f'job-{i}', judge)
        assert code == 0
        results.append(result['worker'])
    assert len({w['output'] for w in results}) == 7
    deadline = time.monotonic() + 20
    for i, worker in enumerate(results):
        receipt = Path(worker['receipt'])
        while time.monotonic() < deadline:
            data = json.loads(receipt.read_text()) if receipt.exists() else {}
            if data.get('status') in ('completed', 'blocked', 'failed'):
                break
            time.sleep(.02)
        assert data['status'] == 'completed', data
        assert data['report']['deliverable'] == f'job-{i}'
        launch = json.loads((receipt.parent / 'launch.json').read_text())
        assert launch['argv'][launch['argv'].index('--sandbox') + 1] == 'read-only'
        assert '--ignore-user-config' in launch['argv']
        assert not any('dangerously' in x for x in launch['argv'])
        os.waitpid(worker['pid'], 0)


def test_zero_exit_intro_is_failed_and_quota_failure_is_latched(tmp_path, monkeypatch):
    monkeypatch.setenv('ROUTER_STATE_DIR', str(tmp_path))
    for label, program in [('intro', 'print("I will investigate.")'),
                           ('quota', 'import sys; print("Individual quota reached", file=sys.stderr)')]:
        folder = tmp_path / label
        folder.mkdir()
        (folder / 'brief.md').write_text('test')
        (folder / 'launch.json').write_text(json.dumps(dict(argv=[sys.executable, '-c', program],
            cwd=str(tmp_path), stdin=True, account='fixture', mode='read-only')))
        assert cli_worker.run(folder) == 1
        assert json.loads((folder / 'result.json').read_text())['status'] == 'failed'
    latch = json.loads((tmp_path / 'quota-exhaustion.json').read_text())
    assert 'fixture' in latch['accounts']


def test_unsupported_readonly_adapter_does_not_launch(tmp_path):
    with patch.object(roll, 'provider_definition', return_value=('antigravity-resilient', {})), \
         patch.object(roll.subprocess, 'Popen', side_effect=AssertionError('must not launch')):
        result, code = roll.cli(SimpleNamespace(wait=0, execution_mode='read-only'),
            {'parent_id': 'p', 'parent_host': 'native', 'parent_address': 'p'},
            {'provider': 'antigravity', 'model': 'argon'}, 'Inspect source',
            SimpleNamespace(subscription_env=lambda: {}))
    assert code == 2 and not result['launched']
