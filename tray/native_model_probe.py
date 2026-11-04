"""Read model metadata through native CLIs without creating a conversation or sending a prompt.

Executed inside owned_process's bounded process group/job. The protocol subprocess
is always reaped; the outer owner also cleans descendants on timeout.
"""
import json
import re
import subprocess
import sys


def normalize(rows, family):
    models = {}
    for row in rows:
        if not isinstance(row, dict) or row.get('hidden'):
            continue
        key = row.get('resolvedModel') or row.get('id') or row.get('value')
        if isinstance(key, str) and key and key != 'default':
            models[key] = {'id': key, 'label': row.get('displayName') or row.get('label') or key}
    return list(models.values())


def text_models(text, family):
    rows = []
    for line in text.splitlines():
        if family == 'antigravity-resilient':
            columns = line.strip().split('\t', 1)
            if len(columns) == 2 and re.fullmatch(r'[\w.-]+', columns[0]):
                rows.append({'id': columns[0], 'label': columns[1]})
        elif family == 'grok':
            match = re.fullmatch(r'\s*[*-]\s+(\S+)(?:\s+\(default\))?\s*', line)
            if match:
                rows.append({'id': match[1], 'label': match[1]})
    return rows


def protocol_models(binary, family):
    command = ([binary, 'app-server'] if family == 'codex' else
               [binary, '--verbose', '--print', '--input-format', 'stream-json', '--output-format', 'stream-json',
                '--no-session-persistence', '--strict-mcp-config', '--mcp-config', '{"mcpServers":{}}',
                '--settings', '{"disableAllHooks":true}'])
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, text=True, encoding='utf-8')
    def send(value):
        process.stdin.write(json.dumps(value) + '\n')
        process.stdin.flush()
    try:
        if family == 'codex':
            send({'id': 1, 'method': 'initialize', 'params': {
                'clientInfo': {'name': 'agentcompass-model-discovery', 'version': '1'}, 'capabilities': {}}})
        else:
            send({'type': 'control_request', 'request_id': 'models', 'request': {'subtype': 'initialize'}})
        models = []
        cursors = set()
        while True:
            line = process.stdout.readline(2 * 1024 * 1024 + 1)
            if not line or len(line) > 2 * 1024 * 1024:
                raise ValueError('Native model protocol ended without a model list')
            message = json.loads(line)
            if family == 'codex':
                if message.get('error'):
                    raise ValueError('Native model protocol returned an error')
                if message.get('id') == 1:
                    send({'method': 'initialized'})
                    send({'id': 2, 'method': 'model/list', 'params': {}})
                if message.get('id') == 2:
                    result = message.get('result') or {}
                    rows = result.get('data')
                    if not isinstance(rows, list):
                        raise ValueError('Invalid Codex model list')
                    models.extend(normalize(rows, family))
                    cursor = result.get('nextCursor')
                    if not cursor:
                        return models
                    if cursor in cursors:
                        raise ValueError('Repeated model pagination cursor')
                    cursors.add(cursor)
                    send({'id': 2, 'method': 'model/list', 'params': {'cursor': cursor}})
            elif message.get('type') == 'control_response':
                response = message.get('response') or {}
                if response.get('request_id') != 'models':
                    continue
                rows = (response.get('response') or {}).get('models')
                if response.get('subtype') != 'success' or not isinstance(rows, list):
                    raise ValueError('Invalid Claude model list')
                return normalize(rows, family)
    finally:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        process.stdin.close()
        process.stdout.close()


def main():
    family, binary = sys.argv[1:]
    if family in ('codex', 'claude'):
        rows = protocol_models(binary, family)
    else:
        result = subprocess.run([binary, 'models'], capture_output=True, text=True, encoding='utf-8', check=True)
        rows = text_models(result.stdout, family)
    if not rows:
        raise ValueError('Native CLI returned no models')
    print(json.dumps(rows))


if __name__ == '__main__':
    main()
