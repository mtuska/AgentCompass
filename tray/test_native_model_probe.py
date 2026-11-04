"""Read-only discovery protocol and UI regressions."""
import io
import json
import os
import sys
from pathlib import Path
from unittest import mock
sys.path.insert(0, str(Path(__file__).parent))
import native_model_probe as probe
import model_catalog
import router_data
from test_router_data_models import settings


def protocol(messages, family):
    stdout = io.StringIO(''.join(json.dumps(m)+'\n' for m in messages))
    stdin = io.StringIO()
    stdin.close = lambda: None
    child = mock.Mock(stdout=stdout, stdin=stdin)
    with mock.patch.object(probe.subprocess, 'Popen', return_value=child):
        result = probe.protocol_models('fixture-cli', family)
    child.terminate.assert_called_once()
    child.wait.assert_called_once()
    return result, [json.loads(line) for line in stdin.getvalue().splitlines()]


def test_codex_pagination_lists_models_without_starting_a_thread():
    rows, sent = protocol([
        {'id':1,'result':{}},
        {'id':2,'result':{'data':[{'id':'one','displayName':'One'}], 'nextCursor':'page2'}},
        {'id':2,'result':{'data':[{'id':'two'},{'id':'hidden','hidden':True}], 'nextCursor':None}},
    ], 'codex')
    assert [r['id'] for r in rows] == ['one','two']
    assert [m['method'] for m in sent] == ['initialize','initialized','model/list','model/list']
    assert sent[-1]['params'] == {'cursor':'page2'}


def test_claude_resolved_models_and_no_user_message():
    rows, sent = protocol([{'type':'control_response','response':{
        'subtype':'success','request_id':'models','response':{'models':[
            {'value':'default','resolvedModel':'claude-one','displayName':'Default'},
            {'value':'one','resolvedModel':'claude-one','displayName':'One'},
        ]}}}], 'claude')
    assert rows == [{'id':'claude-one','label':'One'}]
    assert len(sent)==1 and sent[0]['request']=={'subtype':'initialize'}


def test_native_text_parsers_ignore_status_lines():
    assert probe.text_models('Fetching models...\ngemini-test-high\tGemini Test (High)\n', 'antigravity-resilient') == [
        {'id':'gemini-test-high','label':'Gemini Test (High)'}]
    assert probe.text_models('Default model: grok-one\n  * grok-one (default)\n  - grok-two\n', 'grok') == [
        {'id':'grok-one','label':'grok-one'}, {'id':'grok-two','label':'grok-two'}]


def test_quota_exhausted_account_remains_in_model_settings(tmp_path, monkeypatch):
    settings(tmp_path, monkeypatch)
    allocator = router_data.modules()[0]
    accounts=allocator.load_accounts()
    accounts['_discovery']={'accounts':{'codex':{'status':'quota_exhausted','family':'codex'}},
                            'launchers':{'codex':{'status':'ready'}}}
    for b in accounts['accounts']['codex']['bundles'].values():
        b['discovery_unavailable']=True
    monkeypatch.setattr(router_data,'_cached_accounts',lambda _:accounts)
    rows=router_data.harness_model_rows()
    assert any(r['harness']=='codex' and r['models'] for r in rows)


def test_native_probe_uses_owned_timeout_and_strips_session_identity(monkeypatch):
    monkeypatch.setenv('CLAUDECODE','1')
    with mock.patch.object(model_catalog.shutil,'which',return_value='/bin/claude'), mock.patch.object(
            model_catalog.owned_process,'run',return_value=mock.Mock(returncode=0,stdout='[{"id":"one"}]')) as run:
        assert model_catalog.query_native({'provider':'claude'}) == [{'id':'one'}]
    assert run.call_args.kwargs['timeout']==model_catalog.QUERY_TIMEOUT
    assert 'CLAUDECODE' not in run.call_args.kwargs['env']
