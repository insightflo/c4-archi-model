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
  const nodes=[...vp.querySelectorAll('.c4-body')].map(box);
  for(let s=3;s<length-3;s+=4){const p=path.getPointAtLength(s);
   const hit=texts.find(t=>p.x>t.b.x-1&&p.x<t.b.right+1&&p.y>t.b.y-1&&p.y<t.b.bottom+1);
   if(hit){pathTextCollisions.push({relationship:path.dataset.relation,text:hit.text,point:{x:p.x,y:p.y}});break;}
   if(nodes.some(b=>p.x>b.x+3&&p.x<b.right-3&&p.y>b.y+3&&p.y<b.bottom-3)){pathNodeCollisions.push(path.dataset.relation);break;}
  }
 }
 const self=[...vp.querySelectorAll('.c4-message[data-self="true"]')].map(e=>({id:e.dataset.stepId,order:+e.dataset.order,box:box(e),labelRight:Math.max(...[...e.querySelectorAll('text.c4-text')].map(t=>box(t).right))}));
 const exported=new DOMParser().parseFromString(window.repoFlowmap.exportSvg(),'image/svg+xml').documentElement;
 return {ready:window.repoFlowmap.ready(),renderError:map.dataset.renderError||null,kind:map.dataset.viewKind,viewId:map.dataset.viewId,
  width,height,bbox:box(vp),clipped,textOverlaps,nodeOverflow,pathTextCollisions,pathNodeCollisions,
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
                    record(f'{vid}/{width}/geometry',g['ready'] and not any(g[k] for k in ('clipped','textOverlaps','nodeOverflow','pathTextCollisions','pathNodeCollisions')),g)
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
