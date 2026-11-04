"""Own one CLI child, preserve its artifacts, and publish an atomic completion receipt."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

REPORT_SCHEMA = {
    'type': 'object', 'additionalProperties': False,
    'required': ['status', 'summary', 'deliverable', 'verification'],
    'properties': {
        'status': {'type': 'string', 'enum': ['completed', 'blocked', 'failed']},
        'summary': {'type': 'string'}, 'deliverable': {'type': 'string'},
        'verification': {'type': 'string'},
    },
}
REPORT_CONTRACT = '''

Final report contract: Return one JSON object with status (completed, blocked, or failed),
summary, deliverable, and verification, all strings. Put the actual requested plan or
answer in deliverable, not an announcement that work will start. State what you checked
in verification; distinguish untested recommendations. If you cannot finish, use blocked
or failed and explain why. For read-only work return artifacts in this response; do not
write project files. The coordinator saves this response outside the project.
'''


def publish(path, value):
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    temporary.replace(path)


def report_from(path):
    text = path.read_text(encoding='utf-8', errors='replace').strip()
    if text.startswith('```') and text.endswith('```'):
        text = '\n'.join(text.splitlines()[1:-1])
    report = json.loads(text)
    if not isinstance(report, dict) or set(report) != set(REPORT_SCHEMA['required']):
        raise ValueError('Final response does not match the report contract')
    if any(not isinstance(value, str) for value in report.values()):
        raise ValueError('Report values must be strings')
    if report['status'] not in ('completed', 'blocked', 'failed'):
        raise ValueError('Invalid report status')
    if not report['summary'].strip():
        raise ValueError('Missing report summary')
    if report['status'] == 'completed' and any(not report[key].strip() for key in ('deliverable', 'verification')):
        raise ValueError('Completed report has no deliverable or verification')
    return report


def run(folder):
    folder = Path(folder)
    spec = json.loads((folder / 'launch.json').read_text())
    receipt = {'status': 'starting', 'supervisor_pid': os.getpid(), 'mode': spec['mode'],
               'account': spec.get('account'), 'started_at': time.time(),
               'validation': 'worker report only; coordinator must assess correctness'}
    path = folder / 'result.json'
    publish(path, receipt)
    child = None
    def stop(signum, frame):
        if child is not None and child.poll() is None:
            child.terminate()
        raise InterruptedError(f'Supervisor received signal {signum}')
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        with (folder / 'brief.md').open('rb') as brief, (folder / 'output.txt').open('wb') as output, (folder / 'stderr.txt').open('wb') as error:
            child = subprocess.Popen(spec['argv'], cwd=spec['cwd'],
                                     stdin=brief if spec['stdin'] else subprocess.DEVNULL,
                                     stdout=output, stderr=error)
            receipt.update(status='running', pid=child.pid)
            publish(path, receipt)
            code = child.wait()
        receipt['exit_code'] = code
        import quota_exhaustion
        exhausted = False
        for filename in ('stderr.txt', 'output.txt'):
            with (folder / filename).open(errors='replace') as stream:
                for line in stream:
                    if spec.get('account') and quota_exhaustion.record(spec['account'], line,
                            source='cli:' + folder.name):
                        exhausted = True
        if code or exhausted:
            receipt.update(status='failed', error='quota exhausted' if exhausted else f'CLI exited {code}')
        else:
            final = folder / 'final.json'
            report = report_from(final if final.exists() else folder / 'output.txt')
            receipt.update(status=report['status'], report=report)
    except Exception as exc:
        receipt.update(status='failed', error=str(exc))
    finally:
        if child is not None and child.poll() is None:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        receipt['finished_at'] = time.time()
        publish(path, receipt)
    return 0 if receipt['status'] == 'completed' else 1


if __name__ == '__main__':
    if len(sys.argv) == 3 and sys.argv[1] == 'status':
        receipt = Path(sys.argv[2]) / 'result.json'
        print(receipt.read_text() if receipt.exists() else json.dumps({'status': 'starting'}))
    else:
        sys.exit(run(sys.argv[1]))
