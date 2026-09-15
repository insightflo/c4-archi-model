#!/usr/bin/env python3
"""Generate synthetic, evidence-labelled C4 samples through the native repo-flowmap.

This fixture authoring script is not repository analysis. Class members and deployment
placements are explicitly invented sample facts, not inferred real implementation.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

SKILL=Path(__file__).resolve().parents[1]
NOW='2026-09-15T00:00:00Z'
CLAIM='CL-DEMO'

def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def make_model() -> dict:
    model=json.loads((SKILL/'examples/ordering-system.architecture-model.json').read_text())
    model['metadata'].update(title='Repo-flowmap 의미별 보기 · 가상 샘플',description='전부 설명용 가상 모델입니다. 클래스·메서드·배치와 추가 호출은 실제 저장소에서 추출한 사실이 아닙니다.',modelRevision='demo-fork-1',generatorVersion='repo-flowmap-c4-fork/1',generatedAt=NOW,sourceSnapshotId='snapshot-rfm-demo')
    def element(id,typ,name,parent=None,tech=None,description=None,instance=None,unresolved=False,details=None):
        e={'id':id,'type':typ,'name':name,'description':description or name+'의 가상 샘플 책임을 설명한다.','technology':tech,'parentId':parent,'environment':'설명용 환경' if typ in {'deploymentNode','infrastructureNode'} else None,'tags':['synthetic-sample'],'derivation':'unresolved' if unresolved else 'explicit','confidence':'UNVERIFIED' if unresolved else 'DOC_ONLY','rationale':'시각 표현 검증용으로 저작한 예시이며 운영 사실이 아니다.','claimIds':[CLAIM],'instanceOfId':instance}
        if details is not None:e['codeDetails']=details
        model['elements'].append(e);return e
    def rel(id,a,b,desc,kind=None,**kw):
        r={'id':id,'sourceId':a,'destinationId':b,'description':desc,'technology':kw.pop('technology',None),'interactionStyle':'unknown','derivation':'explicit','confidence':'DOC_ONLY','rationale':'명시적으로 저작한 가상 관계.','claimIds':[CLAIM]}
        if kind:r['codeRelation']={'kind':kind,'claimIds':[CLAIM],**kw}
        model['relationships'].append(r);return r
    def view(id,typ,title,scope,eids,rids,steps=None):
        v={'id':id,'type':typ,'title':title,'scopeId':scope,'environment':None,'description':'의미별 도형과 경로를 검증하는 가상 샘플이다.','question':title+'에서 무엇을 구별할 수 있는가?','notShown':['실제 코드 분석 또는 운영 검증이 아님'],'elementIds':eids,'relationshipIds':rids,'steps':steps or [],'nextViewIds':[],'claimIds':[CLAIM]};model['views'].append(v);return v
    element('order-controller','component','주문 요청 접수 컴포넌트','order-api','Python')
    element('order-service','component','주문 규칙 처리 컴포넌트','order-api','Python')
    element('order-repository','component','주문 저장 컴포넌트','order-api','SQL')
    rel('controller-service','order-controller','order-service','입력된 주문을 검증하고 처리한다.')
    rel('service-repository','order-service','order-repository','검증한 주문을 저장하도록 요청한다.')
    view('ordering-components','component','구조 · Component: API 내부 책임','order-api',['order-controller','order-service','order-repository'],['controller-service','service-repository'])
    def member(s):return {'declaration':s,'claimIds':[CLAIM]}
    defs=[('entity','Entity','class',['# id: UUID'],['+ identity(): UUID']),
          ('order-class','Order · 주문 객체','class',['- status: OrderStatus','- items: List<LineItem>'],['+ addItem(item: LineItem): void','+ validateOrderBeforeSaving(): ValidationResult']),
          ('line-item','LineItem · 주문 항목','class',['- quantity: int','- price: Decimal'],['+ subtotal(): Decimal']),
          ('repository-interface','OrderRepository','interface',[],['+ save(order: Order): void']),
          ('sql-repository','SqlOrderRepository','class',['- connection: Connection'],['+ save(order: Order): void']),
          ('audit-log','AuditLog','class',None,['+ record(message: str): void'])]
    for id,name,kind,attrs,methods in defs:
        element(id,'codeElement',name,'order-service','Python',details={'kind':kind,'attributes':None if attrs is None else [member(s) for s in attrs],'methods':[member(s) for s in methods]})
    classrels=[rel('order-entity','order-class','entity','Order는 Entity의 식별자 동작을 상속한다.','inheritance'),
               rel('sql-interface','sql-repository','repository-interface','저장 인터페이스를 구현한다.','realization'),
               rel('order-items','order-class','line-item','주문이 주문 항목의 생명주기를 소유한다.','composition',sourceMultiplicity='1',destinationMultiplicity='1..*'),
               rel('order-audit','order-class','audit-log','처리 결과 기록에 일시적으로 의존한다.','dependency'),
               rel('sql-order','sql-repository','order-class','저장소가 주문 객체를 참조한다.','association')]
    view('ordering-classes','code','클래스 · UML (명시적으로 저작한 가상 샘플)','order-service',[d[0] for d in defs],[r['id'] for r in classrels])
    # Last participant + very long Korean self message is an intentional regression.
    long='배송 준비 작업자는 고객에게 제공할 주문 상태와 항목별 재고 확인 결과를 다시 확인하고 내부 검증 결과를 기록한다. '+('마지막 참가자의 자기호출 긴 한국어 라벨이 오른쪽 경계를 넘어 잘리지 않아야 한다. '*3)
    r1=rel('demo-customer-api','customer','order-api','주문 접수를 요청한다.',technology='HTTPS / JSON')
    r2=rel('demo-api-worker','order-api','fulfilment-worker','주문 처리 작업을 전달한다.',technology='내부 호출')
    r3=rel('demo-worker-self','fulfilment-worker','fulfilment-worker',long)
    ordered=[r1['id'],r2['id'],r3['id'],r2['id'],r3['id']]
    steps=[{'id':f'demo-step-{i+1}','order':i+1,'relationshipId':rid,'kind':'interaction','condition':None,'note':'가상 샘플의 반복 호출' if i>=3 else None,'claimIds':[CLAIM]} for i,rid in enumerate(ordered)]
    view('ordering-sequence','dynamic','시퀀스 · 반복 호출과 마지막 참가자의 자기호출','ordering-system',['customer','order-api','fulfilment-worker'],[r1['id'],r2['id'],r3['id']],steps)
    element('demo-environment','deploymentNode','설명용 환경 · 리전은 미확정',unresolved=True)
    element('app-host','deploymentNode','애플리케이션 실행 호스트','demo-environment','Linux')
    element('data-host','deploymentNode','데이터 실행 호스트','demo-environment','Linux')
    element('api-instance','infrastructureNode','API 인스턴스 A','app-host','Python',instance='order-api')
    element('worker-instance','infrastructureNode','작업자 인스턴스 A','app-host','Python',instance='fulfilment-worker')
    element('db-instance','infrastructureNode','데이터베이스 인스턴스 A','data-host','PostgreSQL',instance='order-database')
    rel('instance-api-db','api-instance','db-instance','주문 레코드를 저장한다.',technology='SQL')
    rel('instance-api-worker','api-instance','worker-instance','작업 실행을 요청한다.')
    view('ordering-deployment','deployment','배치 · 인스턴스와 미확정 경계',None,['demo-environment','app-host','data-host','api-instance','worker-instance','db-instance'],['instance-api-db','instance-api-worker'])
    return model


def generate(root: Path, render=True) -> None:
    if root.exists() and any(root.iterdir()):raise ValueError('demo destination must be empty; never overwrite user data')
    root.mkdir(parents=True,exist_ok=True)
    shutil.copytree(SKILL/'examples',root/'examples')
    model=make_model();write(root/'model/architecture-model.json',model)
    # Archive authored facts first, then bind an explicitly synthetic documentation claim.
    facts={'notice':'가상 샘플: 실제 저장소 코드·배치에서 추출하지 않았습니다.','elements':model['elements'],'relationships':model['relationships'],'views':model['views']}
    write(root/'sources/synthetic-facts.json',facts)
    digest='sha256:'+hashlib.sha256((root/'sources/synthetic-facts.json').read_bytes()).hexdigest()
    ledger=json.loads((SKILL/'examples/ordering-system.evidence-ledger.json').read_text());ledger.update(modelRevision=model['metadata']['modelRevision'],generatedAt=NOW)
    ledger['snapshot'].update(id='snapshot-rfm-demo',capturedAt=NOW);ledger['snapshot']['sourceIds'].append('S-DEMO')
    source={'id':'S-DEMO','name':'직접 저작한 가상 샘플','kind':'design-doc','location':'sources/synthetic-facts.json','version':'fork-demo-1','readScope':'전체 가상 사실','limitations':['실제 저장소에서 추출한 사실이 아니다.'],'immutableRef':digest,'contentHash':digest,'capturedAt':NOW}
    ledger['sources'].append(source)
    ledger['claims'].append({'id':CLAIM,'statement':'추가 클래스 멤버·관계 종류·반복 호출·배치 위치는 렌더러 검증용으로 직접 저작한 가상 사실이다.','targetIds':[e['id'] for e in model['elements'] if CLAIM in e['claimIds']]+[r['id'] for r in model['relationships'] if CLAIM in r['claimIds']]+[v['id'] for v in model['views'] if CLAIM in v['claimIds']],'derivation':'explicit','confidence':'DOC_ONLY','supports':[{'sourceId':'S-DEMO','locator':'elements / relationships / views','excerpt':None,'evidenceClass':'documentation','capturedAt':NOW,'immutableRef':digest,'contentHash':digest}],'contradictions':[],'usedBy':[],'notes':['가상 샘플임을 HTML에 표시한다.']})
    write(root/'qa/evidence-ledger.json',ledger)
    session=json.loads((SKILL/'examples/ordering-system.architecture-session.json').read_text());session['sourceSnapshotId']='snapshot-rfm-demo'
    write(root/'model/architecture-session.json',session)
    for name,dest in [('coverage','coverage'),('human-understanding','human-understanding')]:
        d=json.loads((SKILL/f'examples/ordering-system.{name}.json').read_text())
        if 'modelRevision' in d:d['modelRevision']=model['metadata']['modelRevision']
        if name=='human-understanding':
            d['result']='NOT_RUN';d['method']='not-run';d['simulated']=False;d['testedAt']=None;d['questions']=[];d['limitations']=['가상 데모의 실제 사람 이해도 검사는 실행하지 않았다.']
        write(root/f'qa/{dest}.json',d)
    report=json.loads((SKILL/'examples/html-report-data.example.json').read_text())
    report['build'].update(sessionPath='model/architecture-session.json',canonicalModelPath='model/architecture-model.json',evidenceLedgerPath='qa/evidence-ledger.json',coveragePath='qa/coverage.json',understandingPath='qa/human-understanding.json',expectedFiles=[])
    report['overview'].update(problem='구조·객체 상세·시간 순서·배치가 같은 카드처럼 보이는 문제를 구분한다.',oneSentence='기존 repo-flowmap 렌더러 내부에 보기별 배치와 도형을 확장했다. 이 보고서는 전부 가상 샘플이며, 실제 프로젝트 코드 분석 결과가 아니다.',scopeSummary='가상 Context/Container/Component, UML class, sequence, deployment. 실제 사람 이해도와 전체 운영 환경 검증은 미실행.',readingOrder=['구조: 유형과 포함 경계','클래스: 이름/속성/메서드','시퀀스: 위에서 아래 시간순','배치: 경계/인스턴스/대상'],claimIds=[CLAIM])
    vids=['ordering-context','ordering-container','ordering-components','ordering-classes','ordering-sequence','ordering-deployment']
    report['diagrams']=[]
    for vid in vids:
        v=next(v for v in model['views'] if v['id']==vid)
        report['diagrams'].append({'id':'diagram-'+vid,'viewId':vid,'assetPath':f'diagrams/{vid}.flowmap.html','dataUri':None,'mimeType':'text/html','required':True,'printAssetPath':None,'presentation':{'intro':v['title']+' · 가상 샘플','readingTips':['1 또는 100% 버튼으로 읽고 드래그로 이동한다.','정적 구조의 관계 번호는 순서가 아닌 참조 번호다.'] if v['type']!='dynamic' else ['참가자와 생명선, 위에서 아래로 증가하는 메시지 번호를 읽는다.','반복·자기호출을 서로 다른 단계로 표시한다.'],'notShown':v['notShown'],'nextViewIds':[],'caption':'repo-flowmap 로컬 포크 · '+v['type'],'alt':v['title']}})
    write(root/'html/report-data.json',report)
    (root/'HANDOFF.md').write_text('# repo-flowmap fork demonstration\n\n가상 샘플입니다. 클래스와 배치는 실제 코드에서 추출하지 않았습니다.\n'+
                                  'printAssetPath는 브라우저 실제 SVG 추출이 성공하면 연결할 수 있습니다. null은 인쇄 그림 미제공입니다.\n'+
                                  'file:// 진입, 브라우저 검사와 실제 사람 이해도는 실행 로그를 따릅니다.\n',encoding='utf-8')
    if render:
        for vid in vids:
            subprocess.run([sys.executable,str(SKILL/'scripts/build_repo_flowmap.py'),'--root',str(root),'--model','model/architecture-model.json','--view',vid],check=True)
        subprocess.run([sys.executable,str(SKILL/'scripts/build_html_report.py'),'--root',str(root),'--data','html/report-data.json','--template',str(SKILL/'assets/html-report-template.html'),'--output',str(root/'index.html')],check=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0]);p.add_argument('--output',type=Path,required=True);p.add_argument('--inputs-only',action='store_true');a=p.parse_args();generate(a.output.resolve(),not a.inputs_only)
