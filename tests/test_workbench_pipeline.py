"""Exercise real A/B/D boundaries through the controller without paid inference."""
import json
import time

from credit_agreement_extractor.workbench import Workbench
from credit_agreement_extractor.llm import LlmResponse, MODEL_ROUTES


def test_real_stage_chain_from_controller_to_readable_result(tmp_path, monkeypatch):
    from credit_agreement_extractor import runner
    from credit_agreement_extractor.conversion import convert_document
    from test_conversion import RecordingConverter
    from test_optional_hierarchy import OfflineClient
    corpus=tmp_path/'raw_documents/pdf'
    corpus.mkdir(parents=True)
    source=corpus/'offline-test.pdf'
    original=b'%PDF-1.4 public offline test'
    source.write_bytes(original)
    monkeypatch.setattr(runner,'convert_document',lambda path,**kw:
                        convert_document(path,converter=RecordingConverter(),**kw))
    class CombinedOfflineClient:
        def complete(self, system, request, **options):
            if 'output_schema' not in request:
                return OfflineClient().complete(system,request,**options)
            payload={'parties':[{'party_id':'p1','name':'Example Borrower, LLC',
                'roles':['borrower'],'status':'supported','evidence_item_ids':['#/texts/1']}],
                'relationships':[],'facilities':[],'interest':[],
                'issues':['Offline plumbing test; not an extraction accuracy evaluation.']}
            return LlmResponse(json.dumps(payload),options['model'],MODEL_ROUTES[options['model']],{},0,{})
    def pipeline(path,**options):
        return runner.run_pipeline(path,client=CombinedOfflineClient(),**options)
    with_owner=Workbench(tmp_path,pipeline=pipeline)
    job=with_owner.start_job({'document_id':source.name})
    for _ in range(300):
        data=with_owner.run_data(job['run_id'])
        if data['job']['status']!='running':
            break
        time.sleep(.01)
    assert data['job']['status']=='completed',data['job']
    assert {'A1','A8','A11','B1','B2','B3','B4','B5','D1','D2','D3','D4'} <= {
        event.get('stage') for event in data['events']}
    assert data['result']['source_evidence']['#/texts/1']['text']
    assert data['result']['parties'][0]['name']=='Example Borrower, LLC'
    assert source.read_bytes()==original
    assert 'Example Borrower' in with_owner.review(job['run_id'])
    with_owner.close()
