"""Execute the bundled router in Node; assert geometry, not implementation wording."""
from pathlib import Path
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
CHROME = os.environ.get('C4_BROWSER') or shutil.which('chromium') or '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / 'assets/repo-flowmap/template.html'

# Only the browser state boundary is supplied; all geometry is production JavaScript.
HARNESS = r"""
const fs = require('fs'), vm = require('vm'), assert = require('assert/strict');
const html = fs.readFileSync(process.argv[1], 'utf8');
const source = html.slice(html.indexOf('  function portPoint('),
                          html.indexOf('  // 노드가 배치되는 순서'));
const constants = html.match(/  var PAD_X =[^\n]+\n  var ROUTE_CLEARANCE =[^\n]+\n  var ROUTE_CROSS_COST =[^\n]+/)[0];
function load(c4 = true) {
  const ctx = {DATA: {c4}, state: {compact: false},
               connectionEdit: () => ({}), isInternalStep: () => false};
  vm.createContext(ctx); vm.runInContext(constants + source, ctx); return ctx;
}
const c = load();
const node = (id, x, y, w=100, h=100) => ({id, x, y, w, h});
const layout = (...nodes) => ({pos: Object.fromEntries(nodes.map(n => [n.id,n])), width:1000, height:1000});
const vectors = {n:[0,-1], e:[1,0], s:[0,1], w:[-1,0]};
function check(route, lay) {
  const ps = route.points;
  assert.ok(ps && ps.length >= 2, 'missing safe route: ' + JSON.stringify(route.sides));
  ps.forEach(p => assert.ok(Number.isFinite(p.x) && Number.isFinite(p.y) && p.x >= 0 && p.y >= 0,
                            'route escapes canvas: ' + JSON.stringify(p)));
  for (const [p,q,side] of [[ps[0],ps[1],route.sides.from], [ps.at(-1),ps.at(-2),route.sides.to]]) {
    const [vx,vy] = vectors[side], dx=q.x-p.x, dy=q.y-p.y;
    assert.ok(Math.abs(dx*vy-dy*vx)<1e-6 && dx*vx+dy*vy>0,
              'reversed/diagonal terminal: ' + JSON.stringify({side,p,q}));
  }
  for (let i=1;i<ps.length;i++) {
    const p=ps[i-1], q=ps[i];
    assert.ok(Math.abs(p.x-q.x)<1e-6 || Math.abs(p.y-q.y)<1e-6, 'diagonal interior');
    for (const n of Object.values(lay.pos)) {
      const hit = Math.abs(p.x-q.x)<1e-6
        ? p.x>n.x+1e-6 && p.x<n.x+n.w-1e-6 && Math.max(p.y,q.y)>n.y+1e-6 && Math.min(p.y,q.y)<n.y+n.h-1e-6
        : p.y>n.y+1e-6 && p.y<n.y+n.h-1e-6 && Math.max(p.x,q.x)>n.x+1e-6 && Math.min(p.x,q.x)<n.x+n.w-1e-6;
      assert.ok(!hit, 'node penetration: '+JSON.stringify({p,q,n}));
    }
  }
}
function route(a,b,sides,lay=layout(a,b)) {
  const r={a,b,sides,mode:'curve',fromSlot:{index:0,total:1},toSlot:{index:0,total:1}};
  r.points=c.orthogonalRoutePoints(r,lay,[]); return r;
}
function build(steps,lay) { return c.buildEdgeRoutes({id:'probe',steps},lay); }
"""


@unittest.skipUnless(shutil.which('node'), 'Node required for actual bundled router')
class AnchorGeometryTests(unittest.TestCase):
    def run_js(self, body):
        result = subprocess.run(['node', '-e', HARNESS + body, str(TEMPLATE)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_many_slots_are_unique_on_every_face_even_with_different_projections(self):
        # Per-edge projection plus clamping must not merge independently assigned slots.
        self.run_js(r"""
const a=node('a',100,100);
for (const side of Object.keys(vectors)) for (const count of [8,12,32]) {
  const points=Array.from({length:count},(_,index)=>
    c.portPoint(a,side,{index,total:count},c.c4AnchorProjection(a,node('b',600+index*50,600+index*80))));
  assert.equal(new Set(points.map(p=>JSON.stringify(p))).size,count,side+' merged anchors');
  points.forEach(p=>assert.ok(p.x>=100 && p.x<=200 && p.y>=100 && p.y<=200));
}
for (const side of Object.keys(vectors)) {
  const others=Array.from({length:12},(_,i)=>node('b'+i,400+i*140,400));
  const lay=layout(a,...others);
  const rs=build(others.map(b=>({from:'a',to:b.id,fromSide:side,toSide:'n'})),lay);
  assert.equal(new Set(rs.map(r=>JSON.stringify(r.points && r.points[0]))).size,12,side+' merged built anchors');
}
""")

    def test_all_side_pairs_keep_both_normals_and_avoid_close_nodes(self):
        # The previous source-only Z fallback enters the target through its interior.
        self.run_js(r"""
const a=node('a',100,100);
for (const b of [node('b',208,150),node('b',201,150),node('b',400,400)]) {
  const lay=layout(a,b);
  for (const from of Object.keys(vectors)) for (const to of Object.keys(vectors)) {
    const r=route(a,b,{from,to},lay); check(r,lay);
    assert.ok(!/[C]/.test(c.routePath(r)), 'typed route must not become a cubic');
  }
}
""")

    def test_parallel_strands_do_not_reverse_terminals_or_enter_nodes(self):
        # A 32px strand shift used to send route 7 back into its source card.
        self.run_js(r"""
const a=node('a',100,100),b=node('b',400,300),lay=layout(a,b);
for (const count of [2,3,4,8,12,24]) {
  const rs=build(Array.from({length:count},()=>({from:'a',to:'b'})),lay);
  assert.equal(rs.length,count); rs.forEach(r=>check(r,lay));
}
""")

    def test_strand_collision_with_unrelated_node_is_rejected(self):
        self.run_js(r"""
const ns=Array.from({length:6},(_,i)=>node('n'+i,100+(i%3)*250,100+Math.floor(i/3)*240,140,120));
const lay=layout(...ns);
const pairs=[[1,5],[5,0],[3,2],[5,3],[1,3],[5,3],[3,4],[3,2],[1,5],[3,5]];
const rs=build(pairs.map(([a,b])=>({from:'n'+a,to:'n'+b})),lay);
rs.forEach(r=>check(r,lay));
""")

    def test_self_loops_have_distinct_ports_and_outward_normals(self):
        self.run_js(r"""
const a=node('a',100,100),lay=layout(a);
for (const side of Object.keys(vectors)) {
  const rs=build(Array.from({length:3},()=>({from:'a',to:'a',fromSide:side,toSide:side})),lay);
  const ports=[];
  rs.forEach(r=>{check(r,lay); ports.push(r.points[0],r.points.at(-1));
                assert.ok(!/C/.test(c.routePath(r)), 'self loop bypassed safe route');});
  assert.equal(new Set(ports.map(p=>JSON.stringify(p))).size,6);
}
""")

    def test_reverse_pairs_and_single_facing_edge_remain_safe(self):
        self.run_js(r"""
const a=node('a',100,100),b=node('b',400,100),lay=layout(a,b);
const rs=build([{from:'a',to:'b'},{from:'b',to:'a'}],lay);
rs.forEach(r=>check(r,lay)); assert.notEqual(c.routePath(rs[0]),c.routePath(rs[1]));
const single=build([{from:'a',to:'b'}],lay)[0]; check(single,lay);
assert.equal(c.routePath(single),'M 200 150 L 400 150');
""")

    def test_overlapped_terminals_do_not_fabricate_an_unsafe_path(self):
        self.run_js(r"""
const a=node('a',100,100),b=node('b',100,100),lay=layout(a,b);
const r=build([{from:'a',to:'b'}],lay)[0];
assert.ok(!r.points || !r.points.length, 'overlap must not fabricate a route');
assert.equal(c.routePath(r), '');
""")

    def test_route_safety_rejects_negative_canvas_coordinates_without_relaxing_other_checks(self):
        self.run_js(r"""
const a=node('a',100,100),b=node('b',400,100),lay=layout(a,b);
function candidate(points) {return {a,b,sides:{from:'n',to:'n'},clearance:6,
                                   points:points.map(([x,y])=>({x,y}))};}
const inside=candidate([[150,100],[150,80],[450,80],[450,100]]);
assert.equal(c.c4RouteIsSafe(inside,lay),true,'positive baseline must be safe');
for(const y of [-6,-0.000001]) {
  const above=candidate([[150,100],[150,y],[450,y],[450,100]]);
  assert.equal(c.c4RouteIsSafe(above,lay),false,'negative y must not be safe');
}
const left=candidate([[150,100],[150,80],[-6,80],[-6,50],[450,50],[450,100]]);
assert.equal(c.c4RouteIsSafe(left,lay),false,'negative x must not be safe');
const throughCard=candidate([[150,100],[150,110],[450,110],[450,100]]);
assert.equal(c.c4RouteIsSafe(throughCard,lay),false,'normal/card guards must remain');
// Zero is allowed; right/bottom may grow at final bbox/export, unlike top/left.
const expanded=candidate([[150,100],[150,0],[1100,0],[1100,80],[450,80],[450,100]]);
assert.equal(c.c4RouteIsSafe(expanded,lay),true,'do not impose fixed right/bottom bounds');
""")

    def test_dense_search_avoids_expanded_page_header_negative_grid_before_and_after_strands(self):
        self.run_js(r"""
const a=node('a',48,127,300,286),b=node('b',468,127,300,220);
const header=node('__pageHeader',0,0,860,95);
const lay={pos:{a,b,__pageHeader:header},width:860,height:573};
const steps=Array.from({length:8},(_,i)=>({from:i%2?'b':'a',to:i%2?'a':'b'}));
const rs=build(steps,lay),used=[];
// Check search itself, not just a validation-only fix that drops the bad path.
rs.forEach(r=>{
  const raw={...r};raw.points=c.orthogonalRoutePoints(raw,lay,used);
  check(raw,lay);c.rememberRouteSegments(raw.points,used);
});
rs.forEach(r=>check(r,lay));
""")

    def test_canvas_edge_outward_ports_return_no_unsafe_fallback(self):
        self.run_js(r"""
const a=node('a',0,100),b=node('b',0,400),lay=layout(a,b);
const r=build([{from:'a',to:'b',fromSide:'w',toSide:'w'}],lay)[0];
assert.ok(!r.points || !r.points.length,'outward west stubs at x=0 cannot fit');
assert.equal(c.routePath(r),'','no cubic or unchecked fallback');
""")

    def test_legacy_anchor_and_self_loop_behavior_is_unchanged(self):
        self.run_js(r"""
const legacy=load(false),a=node('a',100,100),b=node('b',400,100);
assert.equal(JSON.stringify(legacy.portPoint(a,'e',{index:0,total:3},{x:999,y:999})),JSON.stringify({x:200,y:125}));
const r=legacy.buildEdgeRoutes({id:'legacy',steps:[{from:'a',to:'a',fromSide:'n',toSide:'n'}]},layout(a))[0];
assert.equal(legacy.routePath(r),'M 133.33333333333331 100 C 106.33333333333331 78, 193.66666666666666 78, 166.66666666666666 100');
// The typed origin rule must not leak into legacy's unrestricted route grid.
const left=node('left',0,100),below=node('below',0,400);
const outside=legacy.buildEdgeRoutes({id:'legacy',steps:[{from:'left',to:'below',fromSide:'w',toSide:'w'}]},layout(left,below))[0];
assert.equal(JSON.stringify(outside.points),JSON.stringify([{x:0,y:150},{x:-10,y:150},{x:-10,y:450},{x:0,y:450}]));
""")


@unittest.skipUnless(sync_playwright and Path(CHROME).is_file() and shutil.which('node'),
                     'actual Chrome, Playwright and Node required')
class DenseAnchorBrowserTests(unittest.TestCase):
    """Real producer + file:// Chrome; no patched router or browser substitute."""
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(ROOT / 'scripts'))
        from generate_repo_flowmap_demo import generate
        cls.evidence = Path(os.environ['C4_DENSE_EVIDENCE']) if os.environ.get('C4_DENSE_EVIDENCE') else None
        if cls.evidence:
            cls.evidence.mkdir(parents=True, exist_ok=True)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.root = Path(cls.tmp.name)
        cls.fixtures = {}
        for count, reverse in ((7, True), (8, False), (8, True)):
            name = f'{count}-' + ('bidirectional' if reverse else 'unidirectional')
            root = cls.root / name
            generate(root, False)
            model_path = root / 'model/architecture-model.json'
            model = json.loads(model_path.read_text())
            view = next(v for v in model['views'] if v['id'] == 'ordering-context')
            base = next(r for r in model['relationships'] if r['id'] == 'customer-to-system')
            ids = []
            for i in range(count):
                relation = copy.deepcopy(base)
                relation['id'] = f'dense-context-relationship-{i+1}'
                if reverse and i % 2:
                    relation['sourceId'], relation['destinationId'] = base['destinationId'], base['sourceId']
                model['relationships'].append(relation)
                ids.append(relation['id'])
            view['relationshipIds'] = ids
            model_path.write_text(json.dumps(model, ensure_ascii=False))
            ledger_path = root / 'qa/evidence-ledger.json'
            ledger = json.loads(ledger_path.read_text())
            for claim in ledger['claims']:
                if claim['id'] in base['claimIds']:
                    claim['targetIds'].extend(ids)
            ledger_path.write_text(json.dumps(ledger, ensure_ascii=False))
            result = subprocess.run([sys.executable, str(ROOT / 'scripts/build_repo_flowmap.py'),
                '--root', str(root), '--model', 'model/architecture-model.json', '--view', 'ordering-context'],
                capture_output=True, text=True)
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            fixture = root / 'diagrams/ordering-context.flowmap.html'
            cls.fixtures[name] = (fixture, ids)
            if cls.evidence:
                shutil.copytree(root, cls.evidence / name, dirs_exist_ok=True)
                (cls.evidence / (name + '-producer.log')).write_text(result.stdout + result.stderr)

    def check_fixture(self, fixture, ids, name, expect_all_paths=False, expect_no_paths=False):
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=CHROME, headless=True)
            try:
                for width in (1440, 360):
                    with self.subTest(case=name, width=width):
                        page = browser.new_page(viewport={'width': width, 'height': 1000}, offline=True)
                        errors = []
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error' else None)
                        try:
                            page.goto(fixture.as_uri())
                            page.wait_for_function('window.repoFlowmap !== undefined')
                            page.evaluate('document.fonts.ready')
                            state = page.evaluate('''() => {
                              const map=document.querySelector('#map'),vp=document.querySelector('#vp');
                              const b=vp && vp.getBBox();
                              return {ready:repoFlowmap.ready(),error:map.dataset.renderError || null,
                                nodes:document.querySelectorAll('#vp .c4-node').length,
                                paths:[...document.querySelectorAll('#vp .c4-edge')].map(p=>p.dataset.relation),
                                rows:[...document.querySelectorAll('#vp .c4-relation-row')].map(p=>p.dataset.relation),
                                warning:document.querySelector('#vp .c4-route-warning')?.textContent || '',
                                bbox:b && {x:b.x,y:b.y,right:b.x+b.width,bottom:b.y+b.height},
                                width:+map.dataset.contentWidth,height:+map.dataset.contentHeight};
                            }''')
                            if self.evidence:
                                (self.evidence / f'{name}-{width}.json').write_text(json.dumps(state, ensure_ascii=False, indent=2))
                                page.screenshot(path=str(self.evidence / f'{name}-{width}.png'), full_page=True)
                            self.assertTrue(page.url.startswith('file:'))
                            self.assertTrue(state['ready'], state)
                            self.assertEqual(state['nodes'], 2)
                            self.assertEqual(state['rows'], ids, 'retain every full relationship ID')
                            self.assertGreaterEqual(state['bbox']['x'], 0)
                            self.assertGreaterEqual(state['bbox']['y'], 0)
                            self.assertLessEqual(state['bbox']['right'], state['width'])
                            self.assertLessEqual(state['bbox']['bottom'], state['height'])
                            if expect_all_paths:
                                self.assertEqual(state['paths'], ids, 'normal controls must not lose edges')
                            if expect_no_paths:
                                self.assertEqual(state['paths'], [], 'unsafe edges must be omitted, not drawn')
                            for relation_id in ids:
                                if relation_id not in state['paths']:
                                    self.assertIn('경고', state['warning'])
                                    self.assertIn('관계 ID: ' + relation_id, state['warning'])
                            with page.expect_download() as download:
                                page.locator('#download-svg').click()
                            exported = self.root / f'{name}-{width}.svg'
                            download.value.save_as(exported)
                            if self.evidence:
                                shutil.copyfile(exported, self.evidence / exported.name)
                            page.goto(exported.as_uri())
                            svg_state = page.evaluate('''() => {
                              const svg=document.documentElement,v=svg.viewBox.baseVal;
                              const b=svg.querySelector('.c4-view').getBBox();
                              return {nodes:svg.querySelectorAll('.c4-node').length,
                                rows:[...svg.querySelectorAll('.c4-relation-row')].map(p=>p.dataset.relation),
                                warning:svg.querySelector('.c4-route-warning')?.textContent || '',
                                paths:svg.querySelectorAll('.c4-edge').length,
                                parserErrors:document.querySelectorAll('parsererror').length,
                                inBounds:b.x>=0 && b.y>=0 && b.x+b.width<=v.width && b.y+b.height<=v.height};
                            }''')
                            self.assertEqual(svg_state['parserErrors'], 0)
                            self.assertEqual(svg_state['nodes'], 2)
                            self.assertEqual(svg_state['rows'], ids)
                            self.assertEqual(svg_state['paths'], len(state['paths']))
                            self.assertEqual(svg_state['warning'], state['warning'])
                            self.assertTrue(svg_state['inBounds'], svg_state)
                            self.assertEqual(errors, [])
                        finally:
                            page.close()
            finally:
                browser.close()

    def test_native_seven_bidirectional_and_eight_unidirectional_controls(self):
        for name in ('7-bidirectional', '8-unidirectional'):
            fixture, ids = self.fixtures[name]
            self.check_fixture(fixture, ids, name, expect_all_paths=True)

    def test_native_eight_bidirectional_keeps_diagram_legend_and_export(self):
        fixture, ids = self.fixtures['8-bidirectional']
        self.check_fixture(fixture, ids, '8-bidirectional')

    def test_canvas_impossible_ports_warn_per_full_id_and_keep_native_export(self):
        source_path, ids = self.fixtures['8-unidirectional']
        source = source_path.read_text()
        # Fault injection changes only layout and port input, never safety/search/export.
        anchor = '    return L;\n  }\n  function c4BoundaryMarkup'
        self.assertIn(anchor, source)
        source = source.replace(anchor, '''    var a=L.pos.customer,b=L.pos['ordering-system'];
    a.x=0;b.x=0;b.y=a.y+a.h+120;L.height=b.y+b.h+160;
    return L;
  }
  function c4BoundaryMarkup''', 1)
        source = source.replace('  function c4StaticMap(flow) {', '''  function c4StaticMap(flow) {
    flow.steps.forEach(function(s){s.fromSide='w';s.toSide='w';});''', 1)
        fixture = self.root / 'canvas-impossible.html'
        fixture.write_text(source)
        self.check_fixture(fixture, ids, 'canvas-impossible', expect_no_paths=True)


if __name__ == '__main__':
    unittest.main()
