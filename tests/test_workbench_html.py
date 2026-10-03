"""Offline shell contract and JavaScript syntax; browser QA checks interactions."""
from pathlib import Path
import re
import shutil
import subprocess
import credit_agreement_extractor


def test_shell_has_actual_run_controls_and_no_inline_source_execution():
    path = Path(credit_agreement_extractor.__file__).with_name('workbench.html')
    assert path.exists(), 'The real pipeline workbench shell is missing'
    html = path.read_text()
    for identifier in ('document-select', 'classification-model', 'extraction-model',
                       'classification-effort', 'extraction-effort', 'debug', 'start',
                       'run-select', 'rail', 'inspector', 'source-pdf'):
        assert f'id="{identifier}"' in html
    assert '/api/runs' in html and '/snapshots/' in html
    assert 'innerHTML' not in html
    assert 'Illustrative preview' not in html
    assert 'epoch' in html  # stale run-switch responses are guarded


def test_shell_script_parses_in_node():
    path = Path(credit_agreement_extractor.__file__).with_name('workbench.html')
    assert path.exists(), 'The real pipeline workbench shell is missing'
    node = shutil.which('node')
    if not node:
        return
    script = re.findall(r'<script>(.*?)</script>', path.read_text(), re.S)[0]
    result = subprocess.run([node, '--check'], input=script, text=True, capture_output=True)
    assert result.returncode == 0, result.stderr


def test_history_layout_and_live_event_revision_are_explicit():
    node = shutil.which('node')
    if not node:
        return
    path = Path(credit_agreement_extractor.__file__).with_name('workbench.html')
    script=path.read_text()
    functions=[]
    for name in ('historicalLayout', 'inspectorRevision'):
        matches=re.findall(r'^function '+name+r'\(.*$',script,re.M)
        assert matches, f'{name} is required to avoid stale/mislabelled trace views'
        functions.append(matches[0])
    program='\n'.join(functions)+'''\n
    if(!historicalLayout({status:'historical',pipeline_layout:null}))throw Error('old layout');
    if(historicalLayout({status:'historical',pipeline_layout:'stage-b-v2'}))throw Error('new layout');
    if(historicalLayout({status:'running'}))throw Error('current job');
    const a={events:[],snapshots:[],job:{status:'running'}};
    const b={events:[{stage:'B2',event:'batch_attempt'}],snapshots:[],job:{status:'running'}};
    if(inspectorRevision(a,'run','B2','events')===inspectorRevision(b,'run','B2','events'))throw Error('stale events');
    '''
    result=subprocess.run([node,'-'],input=program,text=True,capture_output=True)
    assert result.returncode==0,result.stderr
