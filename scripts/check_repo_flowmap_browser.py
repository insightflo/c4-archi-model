#!/usr/bin/env python3
"""Browser acceptance of generated native flowmap HTML (optional Playwright).

file:// is the default. --transport injected-test tests the exact HTML bytes using
set_content and is explicitly NOT a successful file:// test. No renderer is mocked.
The QA directory must be new and outside the report package; no source is changed.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse
import json
from pathlib import Path
import shutil
from html.parser import HTMLParser


class FlowDataParser(HTMLParser):
    """Read native renderer input, independently of its rendered SVG nodes."""
    def __init__(self):
        super().__init__(); self.active = False; self.parts = []
    def handle_starttag(self, tag, attrs):
        if tag == 'script': self.active = dict(attrs).get('id') == 'flow-data'
    def handle_endtag(self, tag):
        if tag == 'script': self.active = False
    def handle_data(self, data):
        if self.active: self.parts.append(data)


def read_flow_data(path: Path) -> dict:
    parser = FlowDataParser(); parser.feed(path.read_text(encoding='utf-8-sig'))
    return json.loads(''.join(parser.parts))


# W2 기하 검사(A10 연결 오독·D8 라벨 가림) 결과 필드와 판정 헬퍼.
# record()와 테스트가 같은 기준을 공유한다. 임계값·예외의 근거는 GEOMETRY 안 주석에 있다.
GEOMETRY_CHECK_KEYS = ('clipped', 'textOverlaps', 'nodeOverflow', 'pathTextCollisions', 'pathNodeCollisions')
NEAR_CONNECTION_KEY = 'nearConnectionMimics'
LABEL_OCCLUSION_KEY = 'labelOcclusions'


def geometry_clean(g: dict) -> bool:
    return bool(g.get('ready')) and not any(g.get(k) for k in GEOMETRY_CHECK_KEYS)


def near_connection_clean(g: dict) -> bool:
    return bool(g.get('ready')) and not g[NEAR_CONNECTION_KEY]


def label_occlusion_clean(g: dict) -> bool:
    return bool(g.get('ready')) and not g[LABEL_OCCLUSION_KEY]


def sequence_checks(geometry: dict, steps: list[dict]) -> tuple[bool, bool]:
    expected = [{'id': s['id'], 'order': s['order']} for s in steps]
    expected_self = [s['id'] for s in steps if s['from'] == s['to']]
    actual_self = [s['id'] for s in geometry['self']]
    vb = list(map(float, geometry['exportedViewBox'].split()))
    return (geometry['messages'] == expected,
            actual_self == expected_self and all(
                s['box']['x'] >= vb[0] and s['box']['y'] >= vb[1]
                and s['box']['right'] <= vb[0] + vb[2]
                and s['box']['bottom'] <= vb[1] + vb[3]
                and s['labelRight'] < vb[0] + vb[2] - 10
                for s in geometry['self']))

GEOMETRY = r"""() => {
 const map=document.querySelector('#map'),vp=map.querySelector('#vp');
 const box=e=>{const b=e.getBBox();return {x:b.x,y:b.y,w:b.width,h:b.height,right:b.x+b.width,bottom:b.y+b.height}};
 const texts=[...vp.querySelectorAll('text.c4-text')].map(e=>({e,b:box(e),text:e.textContent}));
 const width=+map.dataset.contentWidth,height=+map.dataset.contentHeight;
 const clipped=texts.filter(t=>t.b.x < -0.1 || t.b.y < -0.1 || t.b.right>width || t.b.bottom>height).map(t=>({text:t.text,box:t.b}));
 const overlap=(a,b,p=0)=>a.x<b.right-p&&a.right>b.x+p&&a.y<b.bottom-p&&a.bottom>b.y+p;
 const textOverlaps=[];
 for(let i=0;i<texts.length;i++)for(let j=i+1;j<texts.length;j++)if(overlap(texts[i].b,texts[j].b,0.8))textOverlaps.push([texts[i].text,texts[j].text]);
 const nodeOverflow=[];
 for(const n of vp.querySelectorAll('.c4-node')){const body=box(n.querySelector('.c4-body'));for(const t of n.querySelectorAll('text.c4-text')){const b=box(t);if(b.x<body.x||b.right>body.right||b.y<body.y||b.bottom>body.bottom)nodeOverflow.push({node:n.dataset.node,text:t.textContent,box:b,body});}}
 const pathTextCollisions=[],pathNodeCollisions=[];
 for(const path of vp.querySelectorAll('path.c4-edge,path.c4-message-line')){
  const length=path.getTotalLength();
  const bodies=[...vp.querySelectorAll('.c4-body')].map(box);
  for(let s=3;s<length-3;s+=4){const p=path.getPointAtLength(s);
   const hit=texts.find(t=>p.x>t.b.x-1&&p.x<t.b.right+1&&p.y>t.b.y-1&&p.y<t.b.bottom+1);
   if(hit){pathTextCollisions.push({relationship:path.dataset.relation,text:hit.text,point:{x:p.x,y:p.y}});break;}
   if(bodies.some(b=>p.x>b.x+3&&p.x<b.right-3&&p.y>b.y+3&&p.y<b.bottom-3)){pathNodeCollisions.push(path.dataset.relation);break;}
  }
 }
 const self=[...vp.querySelectorAll('.c4-message[data-self="true"]')].map(e=>({id:e.dataset.stepId,order:+e.dataset.order,box:box(e),labelRight:Math.max(...[...e.querySelectorAll('text.c4-text')].map(t=>box(t).right))}));
 const exported=new DOMParser().parseFromString(window.repoFlowmap.exportSvg(),'image/svg+xml').documentElement;

 // ── W2 공유 기하 기반: A10(연결처럼 보이는 근접선)과 D8(그리는 순서 라벨 가림)이 같이 쓴다 ──
 // 임계값(조정할 때는 아래 근거를 함께 다시 본다):
 //  NEAR_LINK_PX 2.5 — 선 중심이 무관 노드 경계에 이 거리 안이면 실선(1.8~3px 굵기)이
 //    시각적으로 닿아 붙는다. 정상 라우팅은 ROUTE_CLEARANCE(6) 복도를 유지하므로 그
 //    절반 이하인 이 값은 온전한 배치과 겹치지 않는다.
 //  SHARED_CORRIDOR_PX 2 — 같은 노드 쌍을 잇는 다른 관계와 한 몸으로 겹쳐 보이는 거리.
 //    그 구간은 실제 연결이 존재하는 공유 복도이므로 예외(b).
 //  BADGE_OCCUPY_PX 13 — 배지 원(반지름 12 + 테두리 1.7/2)이 점유한 지점은 관계 번호로
 //    안내되고 있으므로 예외(d).
 //  ENDPOINT_SNAP_PX 3 — flow-data에 없는 관계의 실제 끝점을 경로 시작·끝 좌표로
 //    찾을 때 쓰는 끌림 거리(모델 우선, 좌표는 보강).
 //  LABEL_INSIDE_FRACTION 0.3 — 라벨 면적이 노드 안에 이 비율 이상 들어가고 노드가
 //    나중에 그려졌으면 실제 가림(hard). 미만은 배경 경계 겹침(soft).
 //  SOFT_OVERLAP_PX 0.5 — 이 깊이 미만 겹침은 측정 오차로 본다.
 // 예외 목록(모델·태그 근거):
 //  (a) 관계의 실제 양끝 노드(flow-data step의 from/to, 없으면 경로 끝점 스냅)
 //  (b) 같은 노드 쌍 관계와 겹치는 공유 경로 구간
 //  (c) 시퀀스 라이프라인(.c4-lifeline)은 검사 대상이 아니다 — 참여자 아래로 이어지는
 //      것이 의도라 모델 근거 예외로 둔다(대상 선택자가 애초에 c4-edge/c4-message-line뿐).
 //  (d) 배지가 이미 점유한 지점(번호로 안내됨)
 //  (e) 노드 rect는 실제 .c4-body만 본다 — component mark가 노드 왼쪽 밖 8px
 //      삐져나온 것 등 시각적 돌기를 노드 rect로 계산하지 않는다(오탐 방지).
 const NEAR_LINK_PX=2.5,SHARED_CORRIDOR_PX=2,BADGE_OCCUPY_PX=13,ENDPOINT_SNAP_PX=3,LABEL_INSIDE_FRACTION=0.3,SOFT_OVERLAP_PX=0.5;
 const relPairs={};
 try{const fd=document.getElementById('flow-data');if(fd){(JSON.parse(fd.textContent).flows||[]).forEach(f=>(f.steps||[]).forEach(s=>{if(s.relationshipId&&s.from&&s.to)(relPairs[s.relationshipId]=relPairs[s.relationshipId]||[]).push([s.from,s.to]);}));}}catch(err){}
 const nodeCards=[...vp.querySelectorAll('.c4-node')].map(n=>{const body=n.querySelector('.c4-body');if(!body)return null;const cs=getComputedStyle(body);return {id:n.dataset.canonicalId||n.dataset.node,g:n,body:box(body),marks:[...n.querySelectorAll('.c4-component-mark,.c4-instance-mark,.c4-tab,.c4-person')].map(m=>({kind:(m.getAttribute('class')||'').trim(),b:box(m)})),fillOpaque:cs.fill!=='none'&&cs.fill!=='rgba(0, 0, 0, 0)'&&parseFloat(cs.fillOpacity||'1')>0.9&&parseFloat(cs.opacity||'1')>0.9};}).filter(Boolean);
 const samplePath=p=>{const len=p.getTotalLength(),out=[];if(!(len>0))return out;out.push(p.getPointAtLength(0));for(let s=2;s<len;s+=2)out.push(p.getPointAtLength(s));out.push(p.getPointAtLength(len));return out;};
 const edgePaths=[...vp.querySelectorAll('path.c4-edge,path.c4-message-line')].map(p=>({rel:p.dataset.relation||'',pts:samplePath(p)}));
 const distPointRect=(pt,r)=>Math.hypot(Math.max(r.x-pt.x,0,pt.x-r.right),Math.max(r.y-pt.y,0,pt.y-r.bottom));
 const distRectRect=(a,b)=>Math.hypot(Math.max(b.x-a.right,0,a.x-b.right),Math.max(b.y-a.bottom,0,a.y-b.bottom));
 const interSize=(a,b)=>({w:Math.min(a.right,b.right)-Math.max(a.x,b.x),h:Math.min(a.bottom,b.bottom)-Math.max(a.y,b.y)});
 const interArea=(a,b)=>Math.max(0,Math.min(a.right,b.right)-Math.max(a.x,b.x))*Math.max(0,Math.min(a.bottom,b.bottom)-Math.max(a.y,b.y));
 const areaOf=a=>Math.max(a.w*a.h,1e-6);
 const unionOf=bs=>bs.length?{x:Math.min(...bs.map(b=>b.x)),y:Math.min(...bs.map(b=>b.y)),right:Math.max(...bs.map(b=>b.right)),bottom:Math.max(...bs.map(b=>b.bottom)),w:Math.max(...bs.map(b=>b.right))-Math.min(...bs.map(b=>b.x)),h:Math.max(...bs.map(b=>b.bottom))-Math.min(...bs.map(b=>b.y))}:null;
 const samePair=(ra,rb)=>ra!==rb&&(relPairs[ra]||[]).some(pa=>(relPairs[rb]||[]).some(pb=>(pb[0]===pa[0]&&pb[1]===pa[1])||(pb[0]===pa[1]&&pb[1]===pa[0])));
 const badges=[...vp.querySelectorAll('g.badge')].map(b=>{const bb=box(b);return {x:bb.x+bb.w/2,y:bb.y+bb.h/2};});
 const endsOf=rel=>{const ids=new Set();const pairs=relPairs[rel]||[];pairs.forEach(pr=>{ids.add(pr[0]);ids.add(pr[1]);});
  // 모델 끝점이 있으면 그것만 쓴다. 좌표 스냅은 flow-data에 없는 관계의
  // 보강일 뿐이며, 모델과 함께 쓰면 노드가 경로 위로 이동한 변이 상황에서
  // 무관 노드를 끝점으로 끌어들여 검사를 무력화한다.
  if(pairs.length)return ids;
  const ep=edgePaths.find(e=>e.rel===rel);if(ep&&ep.pts.length>1)nodeCards.forEach(n=>{[ep.pts[0],ep.pts[ep.pts.length-1]].forEach(q=>{if(distPointRect(q,n.body)<=ENDPOINT_SNAP_PX)ids.add(n.id);});});return ids;};

 // A10 — 연결처럼 보이는 근접선. 관계(선)·관계 라벨 각각에서 무관한 노드에 닿아 보이는 곳만 남긴다.
 const nearConnectionMimics=[];
 const mimicBest=new Map();
 const keepMimic=(key,entry)=>{const prev=mimicBest.get(key);if(!prev||entry.distance<prev.distance)mimicBest.set(key,entry);};
 edgePaths.forEach(e=>{const ends=endsOf(e.rel);
  for(const q of e.pts)for(const n of nodeCards){
   if(ends.has(n.id))continue; // (a)
   const d=distPointRect(q,n.body);if(d>NEAR_LINK_PX)continue;
   if(edgePaths.some(o=>o!==e&&samePair(o.rel,e.rel)&&o.pts.some(r=>Math.hypot(r.x-q.x,r.y-q.y)<=SHARED_CORRIDOR_PX)))continue; // (b)
   if(badges.some(b=>Math.hypot(b.x-q.x,b.y-q.y)<=BADGE_OCCUPY_PX))continue; // (d)
   keepMimic('line|'+e.rel+'|'+n.id,{kind:'line',relation:e.rel,node:n.id,distance:d,point:{x:+q.x.toFixed(1),y:+q.y.toFixed(1)}});
  }});
 [...vp.querySelectorAll('g.c4-message')].forEach(m=>{
  const line=m.querySelector('path.c4-message-line');
  const rel=line?line.dataset.relation:'';
  const ends=endsOf(rel);
  const lb=unionOf([...m.querySelectorAll('rect.c4-label-bg,text.c4-message-label')].map(box));
  if(!lb)return;
  nodeCards.forEach(n=>{if(ends.has(n.id))return;const d=distRectRect(lb,n.body);
   if(d<=NEAR_LINK_PX)keepMimic('label|'+m.dataset.stepId+'|'+n.id,{kind:'label',relation:rel,step:m.dataset.stepId,node:n.id,distance:d});});
 });
 mimicBest.forEach(v=>{v.distance=+v.distance.toFixed(2);nearConnectionMimics.push(v);});

 // D8 — 그리는 순서 기반 라벨 가림. 화면 DOM과 내보낸 SVG에서 같은 로직을 쓴다.
 // 좌표는 화면 getBBox(로컬 좌표 = 내보내기 viewBox 좌표)를 쓰고, 문서 순서만 내보내기
 // 문서에서 따로 확인한다(내보내기가 순서를 바꾸는 회귀를 잡는다).
 const labelOcclusions=[];
 const FOLLOWING=Node.DOCUMENT_POSITION_FOLLOWING;
 const screenLabels=[...vp.querySelectorAll('rect.c4-label-bg,text.c4-message-label')];
 const screenNodes=[...vp.querySelectorAll('.c4-node')];
 const exportLabels=exported.querySelectorAll('rect.c4-label-bg,text.c4-message-label');
 const exportNodes=exported.querySelectorAll('.c4-node');
 const exportPaired=exportLabels.length===screenLabels.length&&exportNodes.length===screenNodes.length;
 const stepOf=el=>{const m=el.closest?el.closest('g.c4-message'):null;return m?(m.dataset?m.dataset.stepId:m.getAttribute&&m.getAttribute('data-step-id')):null;};
 screenLabels.forEach((el,li)=>{
  const eb=box(el),owner=el.closest?el.closest('g.c4-message'):null;
  const textUnion=owner?unionOf([...owner.querySelectorAll('text.c4-message-label')].map(box)):eb;
  const isText=el.classList&&el.classList.contains('c4-message-label');
  screenNodes.forEach((ng,ni)=>{
   const card=nodeCards.find(c=>c.g===ng);if(!card)return;
   const nodeAfter=!!(el.compareDocumentPosition(ng)&FOLLOWING);
   const exportAfter=exportPaired&&!!(exportLabels[li].compareDocumentPosition(exportNodes[ni])&FOLLOWING);
   const it=interSize(eb,card.body);
   const bodyOverlap=it.w>SOFT_OVERLAP_PX&&it.h>SOFT_OVERLAP_PX;
   if(bodyOverlap){
    const inside=isText?interArea(textUnion,card.body)/areaOf(textUnion):0;
    const kind=isText&&inside>=LABEL_INSIDE_FRACTION&&card.fillOpaque?'hard-text':'soft-border';
    const detail={overlap:{w:+it.w.toFixed(1),h:+it.h.toFixed(1)},insideFraction:+inside.toFixed(2)};
    if(nodeAfter)labelOcclusions.push(Object.assign({where:'screen',kind:kind,step:stepOf(el),node:card.id},detail));
    if(exportAfter)labelOcclusions.push(Object.assign({where:'export',kind:kind,step:stepOf(el),node:card.id},detail));
   }else{
    for(const mk of card.marks){const mi=interSize(eb,mk.b);
     if(mi.w>SOFT_OVERLAP_PX&&mi.h>SOFT_OVERLAP_PX&&nodeAfter)labelOcclusions.push({where:'screen',kind:'mark',mark:mk.kind,step:stepOf(el),node:card.id,overlap:{w:+mi.w.toFixed(1),h:+mi.h.toFixed(1)}});
    }
   }
  });
 });
 if(screenLabels.length&&!exportPaired)labelOcclusions.push({where:'export',kind:'structure-mismatch',detail:'exported SVG label/node counts differ from screen DOM'});

 return {ready:window.repoFlowmap.ready(),renderError:map.dataset.renderError||null,kind:map.dataset.viewKind,viewId:map.dataset.viewId,
  width,height,bbox:box(vp),clipped,textOverlaps,nodeOverflow,pathTextCollisions,pathNodeCollisions,
  nearConnectionMimics,labelOcclusions,
  nodes:[...vp.querySelectorAll('.c4-node')].map(e=>e.dataset.canonicalId),boundaries:[...vp.querySelectorAll('.c4-boundary')].map(e=>e.dataset.boundary),
  messages:[...vp.querySelectorAll('.c4-message')].map(e=>({id:e.dataset.stepId,order:+e.dataset.order})),self,
  textCount:texts.length,documentWidth:document.documentElement.scrollWidth,viewport:innerWidth,
  exportedViewBox:exported.getAttribute('viewBox'),exportedWidth:exported.getAttribute('width'),
  uml:[...vp.querySelectorAll('.c4-edge')].map(e=>({kind:e.dataset.kind,from:getComputedStyle(e).markerStart,to:getComputedStyle(e).markerEnd,dash:getComputedStyle(e).strokeDasharray}))};
}"""


def pan_background(page, frame) -> dict:
    """Drag a visible, hit-tested empty stage point using real mouse input.

    Frame DOM coordinates are local; Playwright bounding boxes and mouse input
    use the outer page viewport. Never start on nodes, edges or UI controls.
    A missing background or a camera that does not move remains a failure.
    """
    stage = frame.locator('#stage').bounding_box()
    if not stage:
        raise RuntimeError('Pan stage has no visible bounding box')
    viewport = page.evaluate('({width:innerWidth,height:innerHeight})')
    candidates = frame.evaluate('''({stage, viewport}) => {
      const local=document.querySelector('#stage').getBoundingClientRect();
      const sx=stage.width/local.width, sy=stage.height/local.height;
      const points=[];
      for(let y=Math.min(stage.y+stage.height-12,viewport.height-12); y>=Math.max(stage.y+52,52); y-=16)
        for(let x=Math.max(stage.x+12,12); x<=Math.min(stage.x+stage.width-66,viewport.width-66); x+=16){
          const hit=document.elementFromPoint(local.x+(x-stage.x)/sx,local.y+(y-stage.y)/sy);
          if(hit && (hit.id==='map'||hit.id==='stage')) points.push({x,y,target:hit.id});
        }
      return points;
    }''', {'stage': stage, 'viewport': viewport})
    owner = None if frame == page else frame.frame_element()
    for point in candidates:
        visible = page.evaluate('''({point,owner}) => {
          const hit=document.elementFromPoint(point.x,point.y);
          return owner ? hit===owner : hit && (hit.id==='map'||hit.id==='stage');
        }''', {'point': point, 'owner': owner})
        if visible:
            break
    else:
        raise RuntimeError('No visible hit-tested empty background for pan')
    before = frame.evaluate('repoFlowmap.state().camera')
    x, y = point['x'], point['y']
    page.mouse.move(x,y); page.mouse.down()
    try:
        page.mouse.move(x+54,y-40,steps=8)
    finally:
        page.mouse.up()
    page.wait_for_timeout(100)
    return {**point, 'before': before, 'after': frame.evaluate('repoFlowmap.state().camera')}


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--chromium',default=None)
    p.add_argument('--transport',choices=['file','injected-test'],default='file')
    p.add_argument('--legacy-html',type=Path,help='optional actually generated untyped native HTML for compatibility UI checks')
    a=p.parse_args();root=a.root.resolve();out=a.output.resolve()
    if out.exists() or out.is_relative_to(root):p.error('--output must be a NEW directory outside --root')
    report=json.loads((root/'html/report-data.json').read_text())
    diagrams=report['diagrams'];out.mkdir(parents=True)
    inputs = {}
    for diagram in diagrams:
        try: inputs[diagram['viewId']] = read_flow_data(root / diagram['assetPath'])
        except (OSError, ValueError): pass  # The browser records incompatible/missing assets as failures.
    results=[]
    def record(name,ok=None,detail=None,status=None):
        item={'name':name,'status':status or ('PASS' if ok else 'FAIL'),'detail':detail}
        results.append(item);print(f'[{item["status"]}] {name}',flush=True)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        record('browser',detail='Playwright not installed',status='NOT_RUN')
        (out/'results.json').write_text(json.dumps(results,indent=2));return 2
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=a.chromium or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
        context=browser.new_context(offline=True,viewport={'width':1440,'height':1000},accept_downloads=True)
        requests=[]
        def block(route):requests.append(route.request.url);route.abort()
        context.route('http://**/*',block);context.route('https://**/*',block)
        def load(page,path):
            if a.transport=='file':page.goto(path.as_uri(),wait_until='load',timeout=15000)
            else:page.set_content(path.read_text(encoding='utf-8-sig'),wait_until='load')
        # Actual generated paths, not a hello-world substitute. File-policy failures
        # are NOT_RUN and do not automatically switch transport.
        if a.transport=='file':
            for name,path in [(f'generated-{d["viewId"]}',root/d['assetPath']) for d in diagrams] + [('generated-report',root/'index.html')]:
                page=context.new_page()
                try:load(page,path);record(name+'-file-url',page.url.startswith('file:'),page.url)
                except Exception as exc:record(name+'-file-url',detail=str(exc),status='NOT_RUN' if 'ERR_BLOCKED_BY_ADMINISTRATOR' in str(exc) else 'FAIL')
                page.close()
            if any(r['status']!='PASS' for r in results):
                browser.close();data={'transport':a.transport,'results':results,'fileUrlVerified':False}
                (out/'results.json').write_text(json.dumps(data,ensure_ascii=False,indent=2));return 2
        for width in (1440,360):
            for diagram in diagrams:
                vid=diagram['viewId'];page=context.new_page();page.set_viewport_size({'width':width,'height':1000});errors=[]
                page.on('pageerror',lambda e:errors.append(str(e)))
                try:
                    load(page,root/diagram['assetPath']);page.evaluate('document.fonts.ready')
                    page.wait_for_function('window.repoFlowmap && document.querySelector("#map").dataset.renderStatus',timeout=10000)
                    g=page.evaluate(GEOMETRY)
                    (out/f'{vid}-{width}-geometry.json').write_text(json.dumps(g,ensure_ascii=False,indent=2))
                    record(f'{vid}/{width}/geometry',geometry_clean(g),g)
                    record(f'{vid}/{width}/near-connection-mimics',near_connection_clean(g),g[NEAR_CONNECTION_KEY])
                    record(f'{vid}/{width}/label-occlusion',label_occlusion_clean(g),g[LABEL_OCCLUSION_KEY])
                    record(f'{vid}/{width}/viewport',g['documentWidth']<=width+1,{'scrollWidth':g['documentWidth'],'viewport':width})
                    source=inputs[vid];view_type=source['c4']['view']['type']
                    record(f'{vid}/{width}/view-type',g['kind']==source['c4']['mode'] and g['viewId']==vid,{'viewType':view_type,'kind':g['kind']})
                    if view_type=='dynamic':
                        steps=source['flows'][0]['steps']
                        ordered,self_ok=sequence_checks(g,steps)
                        record(f'{vid}/{width}/sequence-order',ordered,g['messages'])
                        record(f'{vid}/{width}/self-within-export',self_ok,{'expectedSelfCount':sum(s['from']==s['to'] for s in steps),'self':g['self'],'exportedViewBox':g['exportedViewBox']})
                    if g['kind']=='class':
                        marker_checks={
                            'inheritance':lambda e:'c4-triangle' in e['to'],
                            'realization':lambda e:'c4-triangle' in e['to'] and e['dash']!='none',
                            'composition':lambda e:'c4-diamond' in e['from'],
                            'association':lambda e:e['to']=='none',
                            'dependency':lambda e:'c4-open' in e['to'] and e['dash']!='none',
                        }
                        expected_kinds=[s['relationship']['codeRelation']['kind'] for s in source['flows'][0]['steps']]
                        ok=[e['kind'] for e in g['uml']]==expected_kinds and all(marker_checks.get(e['kind'],lambda e:False)(e) for e in g['uml'])
                        record(f'{vid}/{width}/UML-markers',ok,g['uml'])
                    page.screenshot(path=str(out/f'{vid}-{width}-readable.png'),full_page=True)
                    before=page.evaluate('repoFlowmap.state().camera.k');page.locator('#zin').click();page.wait_for_timeout(350)
                    after=page.evaluate('repoFlowmap.state().camera.k');record(f'{vid}/{width}/zoom',after>before,{'before':before,'after':after})
                    page.locator('#zfit').click();page.wait_for_timeout(350)
                    obscured=page.evaluate('''()=>{const controls=[...document.querySelectorAll('#hint,.zoomctl,.desktop-context')].map(e=>e.getBoundingClientRect()).filter(b=>b.width&&b.height);return [...document.querySelectorAll('#vp text.c4-text')].filter(e=>{const b=e.getBoundingClientRect();return controls.some(c=>b.x<c.right&&b.right>c.x&&b.y<c.bottom&&b.bottom>c.y)}).map(e=>e.textContent)}''')
                    record(f'{vid}/{width}/fit-toolbar-clearance',not obscured,obscured)
                    page.screenshot(path=str(out/f'{vid}-{width}-fit.png'),full_page=True)
                    pan=pan_background(page,page);before=pan['before'];after=pan['after']
                    record(f'{vid}/{width}/pan',abs(after['tx']-before['tx'])>20 or abs(after['ty']-before['ty'])>20,pan)
                    page.locator('#theme').click();page.wait_for_timeout(100)
                    record(f'{vid}/{width}/runtime-errors',not errors,errors)
                except Exception as exc:record(f'{vid}/{width}/exception',False,str(exc))
                page.close()
        # Report uses its actual generated srcdoc bytes; sandbox stays allow-scripts.
        for width in (1440,360):
            page=context.new_page();page.set_viewport_size({'width':width,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            try:
                load(page,root/'index.html');page.locator('#diagrams').scroll_into_view_if_needed()
                for i,diagram in enumerate(diagrams):
                    vid=diagram['viewId'];page.locator('#diagram-tabs [role=tab]').nth(i).click()
                    handle=page.locator('#diagram-panels iframe').nth(i);handle.scroll_into_view_if_needed()
                    frame=handle.element_handle().content_frame();frame.wait_for_function('window.repoFlowmap && window.repoFlowmap.ready()',timeout=15000);frame.evaluate('document.fonts.ready')
                    data=frame.evaluate('({state:repoFlowmap.state(),scroll:document.documentElement.scrollWidth,width:innerWidth})')
                    record(f'report/{width}/{vid}/iframe',data['state']['viewId']==vid and data['scroll']<=data['width']+1 and handle.get_attribute('sandbox')=='allow-scripts',data)
                    card=handle.locator('xpath=ancestor::*[contains(concat(" ",normalize-space(@class)," ")," diagram-card ")][1]')
                    before=frame.evaluate('repoFlowmap.state().camera.k');w=handle.bounding_box()['width']
                    card.locator('[data-zoom=in]').click();page.wait_for_timeout(400)
                    after=frame.evaluate('repoFlowmap.state().camera.k')
                    record(f'report/{width}/{vid}/zoom-bridge',after>before and abs(handle.bounding_box()['width']-w)<1,{'before':before,'after':after})
                    pan=pan_background(page,frame);before_pan=pan['before'];after_pan=pan['after']
                    record(f'report/{width}/{vid}/iframe-pan',abs(after_pan['tx']-before_pan['tx'])>20 or abs(after_pan['ty']-before_pan['ty'])>20,pan)
                    if inputs.get(vid,{}).get('c4',{}).get('mode')=='class':page.screenshot(path=str(out/f'report-class-{width}.png'),full_page=False)
                # Fullscreen native viewport and message bridge, not frame CSS zoom.
                card.locator('[data-full]').click();dialog=page.locator('#dialog-embed').element_handle().content_frame();dialog.wait_for_function('window.repoFlowmap && window.repoFlowmap.ready()')
                before=dialog.evaluate('repoFlowmap.state().camera.k');page.locator('#dialog-plus').click();page.wait_for_timeout(350)
                record(f'report/{width}/fullscreen',dialog.evaluate('repoFlowmap.state().camera.k')>before and page.locator('#diagram-dialog').evaluate('(d)=>d.open'))
                page.locator('#dialog-close').click()
                page.emulate_media(media='print');page.wait_for_timeout(200)
                imgs=page.locator('.diagram-print-img').evaluate_all('(xs)=>xs.map(e=>({width:e.naturalWidth,height:e.naturalHeight,display:getComputedStyle(e).display}))')
                record(f'report/{width}/print-SVG',len(imgs)==len(diagrams) and all(e['width']>0 and e['height']>0 and e['display']!='none' for e in imgs),imgs)
                record(f'report/{width}/runtime-errors',not errors,errors)
            except Exception as exc:record(f'report/{width}/exception',False,str(exc))
            page.close()
        if a.legacy_html:
            page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
            try:
                load(page,a.legacy_html.resolve());page.evaluate('document.fonts.ready')
                page.locator('.fbtn').first.click();page.wait_for_timeout(350)
                record('legacy/flow-selection',page.evaluate('repoFlowmap.state().flow') is not None,page.evaluate('repoFlowmap.state()'))
                before=page.locator('#compact').get_attribute('aria-pressed');page.locator('#compact').click()
                record('legacy/compact-filter',page.locator('#compact').get_attribute('aria-pressed')!=before)
                page.locator('#edit-connections').click()
                record('legacy/manual-port-edit',page.locator('#edit-connections').get_attribute('aria-pressed')=='true' and page.locator('circle.port').count()>0,{'ports':page.locator('circle.port').count()})
                page.locator('#edit-connections').click();before=page.evaluate('repoFlowmap.state().camera.k');page.locator('#zin').click();page.wait_for_timeout(350)
                record('legacy/zoom',page.evaluate('repoFlowmap.state().camera.k')>before)
                before=page.locator('html').get_attribute('data-theme');page.locator('#theme').click()
                record('legacy/theme',page.locator('html').get_attribute('data-theme')!=before)
                with page.expect_download(timeout=10000) as event:page.locator('#download-svg').click()
                event.value.save_as(out/'legacy-native-download.svg')
                record('legacy/native-SVG-download',(out/'legacy-native-download.svg').stat().st_size>1000)
                record('legacy/runtime-errors',not errors,errors)
                page.screenshot(path=str(out/'legacy-native.png'),full_page=True)
            except Exception as exc:record('legacy/exception',False,str(exc))
            page.close()
        record('offline/no-external-runtime-requests',not requests,requests)
        browser.close()
    record('actual-file-url' if a.transport=='injected-test' else 'cross-browser-and-print-pagination',detail='Injected transport is not file:// verification' if a.transport=='injected-test' else 'Not exercised by this script',status='NOT_RUN')
    data={'transport':a.transport,'fileUrlVerified':a.transport=='file','results':results,'counts':{k:sum(r['status']==k for r in results) for k in ('PASS','FAIL','NOT_RUN')}}
    (out/'results.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
    print(json.dumps(data['counts']));return 1 if data['counts']['FAIL'] else 0

if __name__=='__main__':raise SystemExit(main())
