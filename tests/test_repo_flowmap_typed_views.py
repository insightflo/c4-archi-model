"""Native fork regression tests: real Node builds, canonical gates and write safety."""
from __future__ import annotations
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1];SCRIPTS=ROOT/'scripts';sys.path.insert(0,str(SCRIPTS))
from generate_repo_flowmap_demo import generate, make_model
from build_repo_flowmap import assert_distinct_paths
from repo_flowmap_adapter import project
from c4_validation import validate_model
from validate_diagram_inputs import run as dia
from validate_render_receipts import run as rcp
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    sync_playwright = None
ANCHOR_CHROME = os.environ.get('C4_BROWSER') or shutil.which('chromium') or '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'

@unittest.skipUnless(shutil.which('node'),'Node required; actual native builds not mocked')
class NativeTypedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.seed_tmp=tempfile.TemporaryDirectory();cls.seed=Path(cls.seed_tmp.name)/'demo';generate(cls.seed,False)
        cls.vids=['ordering-context','ordering-container','ordering-components','ordering-classes','ordering-sequence','ordering-deployment']
        for vid in cls.vids:
            p=subprocess.run([sys.executable,str(SCRIPTS/'build_repo_flowmap.py'),'--root',str(cls.seed),'--model','model/architecture-model.json','--view',vid],capture_output=True,text=True)
            if p.returncode:raise RuntimeError(p.stderr)
    @classmethod
    def tearDownClass(cls):cls.seed_tmp.cleanup()
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)/'demo';shutil.copytree(self.seed,self.root)
        self.model=self.root/'model/architecture-model.json';self.ledger=self.root/'qa/evidence-ledger.json'
    def tearDown(self):self.tmp.cleanup()
    def build(self,vid='ordering-context',*args):
        return subprocess.run([sys.executable,str(SCRIPTS/'build_repo_flowmap.py'),'--root',str(self.root),'--model','model/architecture-model.json','--view',vid,*args],capture_output=True,text=True)
    def load(self,rel):return json.loads((self.root/rel).read_text())
    def save(self,rel,d):
        p=self.root/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n')
    def snapshot(self):return {str(p.relative_to(self.root)):p.read_bytes() for p in self.root.rglob('*') if p.is_file()}
    def strict(self):
        return subprocess.run([sys.executable,str(SCRIPTS/'build_html_report.py'),'--root',str(self.root),'--data','html/report-data.json','--template',str(ROOT/'assets/html-report-template.html'),'--output',str(self.root/'index.html')],capture_output=True,text=True)
    def test_50_report_skill_dependencies_collision_matrix(self):
        # Never aim destructive regression probes at the real skill installation.
        skill = Path(self.tmp.name) / 'skill'
        shutil.copytree(ROOT, skill, ignore=shutil.ignore_patterns('__pycache__'))
        def report(*options):
            return subprocess.run([
                sys.executable, str(SCRIPTS / 'build_html_report.py'),
                '--root', str(self.root), '--data', 'html/report-data.json',
                '--skill-root', str(skill),
                '--template', str(skill / 'assets/html-report-template.html'),
                '--output', str(self.root / 'index.html'), *options,
            ], capture_output=True, text=True)
        baseline = report()
        self.assertEqual(baseline.returncode, 0, baseline.stderr + baseline.stdout)
        self.assertTrue((self.root / 'index.html').is_file())
        dependencies = [
            'references/architecture-model.schema.json',
            'assets/repo-flowmap/template.html',
            'scripts/build_repo_flowmap.py',
            'SKILL.md', 'manifest.json', 'VERSION',
        ]
        for rel in dependencies:
            for option in ('--output', '--validation-output'):
                for alias in ('direct', 'hardlink'):
                    with self.subTest(dependency=rel, option=option, alias=alias):
                        source = skill / rel
                        original = source.read_bytes()
                        target = source if alias == 'direct' else Path(self.tmp.name) / 'alias-output'
                        if alias == 'hardlink':
                            target.hardlink_to(source)
                        before = self.snapshot()
                        try:
                            result = report(option, str(target))
                            # Assert integrity independently, even when exit/diagnostic are wrong.
                            checks = (result.returncode != 0, 'path collision' in result.stderr,
                                      source.read_bytes() == original, before == self.snapshot())
                            self.assertEqual(checks, (True, True, True, True), result.stderr + result.stdout)
                        finally:
                            if alias == 'hardlink':
                                target.unlink()
                            source.write_bytes(original)
                            for name, content in before.items():
                                (self.root / name).write_bytes(content)

    def test_01_all_six_real_native_builds_pass_dia_rcp_strict(self):
        self.assertFalse(dia(self.root,self.model).errors);self.assertFalse(rcp(self.root,self.root/'html/report-data.json',model_path=self.model).errors)
        p=self.strict();self.assertEqual(p.returncode,0,p.stderr+p.stdout)
    def test_02_no_parallel_renderer_or_external_graphics(self):
        self.assertFalse((SCRIPTS/'c4_semantic.py').exists());self.assertFalse((SCRIPTS/'build_c4_diagram.py').exists())
        html=(self.root/'diagrams/ordering-context.flowmap.html').read_text()
        self.assertIn('function renderMap()',html);self.assertIn('function buildEdgeRoutes(',html)
        self.assertIn('/* FLOWMAP_JSON */', (ROOT/'assets/repo-flowmap/template.html').read_text())
        self.assertNotIn('/* FLOWMAP_JSON */',html)
    def test_03_modes_visibly_have_different_native_drawing_branches(self):
        expected=['structure','structure','structure','class','sequence','deployment']
        for vid,mode in zip(self.vids,expected):self.assertEqual(self.load(f'diagrams/{vid}.flowmap.json')['c4']['mode'],mode)
    def test_04_class_members_exact_and_evidence_linked(self):
        d=self.load('diagrams/ordering-classes.flowmap.json');model=self.load('model/architecture-model.json')
        for n in d['nodes']:self.assertEqual(n['element'],next(e for e in model['elements'] if e['id']==n['id']))
        self.assertTrue(all(r['relationship']['codeRelation']['claimIds'] for r in d['flows'][0]['steps']))
    def test_05_sequence_repetition_and_last_self_are_preserved(self):
        d=self.load('diagrams/ordering-sequence.flowmap.json');steps=d['flows'][0]['steps']
        self.assertEqual([s['order'] for s in steps],[1,2,3,4,5]);self.assertEqual(steps[1]['relationshipId'],steps[3]['relationshipId'])
        self.assertEqual(steps[-1]['from'],d['nodes'][-1]['id']);self.assertEqual(steps[-1]['kind'],'self');self.assertGreater(len(steps[-1]['call']),130)
        self.assertFalse(any('async' in s or 'return' in s or 'alt' in s for s in steps))
    def test_06_model_step_storage_order_not_display_order(self):
        m=self.load('model/architecture-model.json');v=next(v for v in m['views'] if v['id']=='ordering-sequence');v['steps'].reverse();self.save('model/architecture-model.json',m)
        p=self.build('ordering-sequence');self.assertEqual(p.returncode,0,p.stderr)
        self.assertEqual([s['order'] for s in self.load('diagrams/ordering-sequence.flowmap.json')['flows'][0]['steps']],[1,2,3,4,5])
    def test_07_missing_class_details_explicitly_fails(self):
        m=self.load('model/architecture-model.json');next(e for e in m['elements'] if e['id']=='order-class').pop('codeDetails');self.save('model/architecture-model.json',m)
        p=self.build('ordering-classes');self.assertNotEqual(p.returncode,0);self.assertIn('codeDetails',p.stderr)
    def test_08_unknown_member_claim_fails(self):
        m=self.load('model/architecture-model.json');next(e for e in m['elements'] if e['id']=='entity')['codeDetails']['attributes'][0]['claimIds']=['UNKNOWN'];self.save('model/architecture-model.json',m)
        self.assertNotEqual(self.build('ordering-classes').returncode,0)
    def test_09_empty_member_claims_fail_schema(self):
        m=self.load('model/architecture-model.json');next(e for e in m['elements'] if e['id']=='entity')['codeDetails']['attributes'][0]['claimIds']=[]
        self.assertTrue(validate_model(m,ROOT/'references/architecture-model.schema.json').errors)
    def test_10_unsupported_class_kind_fails(self):
        m=self.load('model/architecture-model.json');next(e for e in m['elements'] if e['id']=='entity')['codeDetails']['kind']='function';self.save('model/architecture-model.json',m)
        self.assertNotEqual(self.build('ordering-classes').returncode,0)
    def test_11_missing_uml_relation_kind_fails(self):
        m=self.load('model/architecture-model.json');next(r for r in m['relationships'] if r['id']=='order-entity').pop('codeRelation');self.save('model/architecture-model.json',m)
        self.assertNotEqual(self.build('ordering-classes').returncode,0)
    def test_12_dependency_multiplicity_not_silently_accepted(self):
        m=self.load('model/architecture-model.json');next(r for r in m['relationships'] if r['id']=='order-audit')['codeRelation']['sourceMultiplicity']='1'
        self.assertTrue(validate_model(m,ROOT/'references/architecture-model.schema.json').errors)
    def test_13_realization_target_requires_interface(self):
        m=self.load('model/architecture-model.json');next(e for e in m['elements'] if e['id']=='repository-interface')['codeDetails']['kind']='class'
        self.assertTrue(validate_model(m,ROOT/'references/architecture-model.schema.json').errors)
    def test_14_dynamic_unsupported_fragments_fail(self):
        self.assertEqual(self.build('ordering-sequence').returncode,0)
        for kind in ('decision','failure','recovery'):
            m=self.load('model/architecture-model.json');next(v for v in m['views'] if v['id']=='ordering-sequence')['steps'][0]['kind']=kind;self.save('model/architecture-model.json',m)
            result=self.build('ordering-sequence')
            self.assertNotEqual(result.returncode,0)
            self.assertIn('fragments are not supported',result.stderr)
    def test_15_logical_deployment_explicit_presentation(self):
        m=self.load('model/architecture-model.json');next(v for v in m['views'] if v['id']=='ordering-deployment')['elementIds'].append('order-api');self.save('model/architecture-model.json',m)
        result=self.build('ordering-deployment')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.load('diagrams/ordering-deployment.flowmap.json')['c4']['deploymentPresentation'],'logical-placement')
    def test_16_cyclic_boundary_fails_before_renderer(self):
        m=self.load('model/architecture-model.json');next(e for e in m['elements'] if e['id']=='demo-environment')['parentId']='app-host';self.save('model/architecture-model.json',m)
        self.assertNotEqual(self.build('ordering-deployment').returncode,0)
    def test_17_unknown_exact_view_fails(self):self.assertNotEqual(self.build('not-a-view').returncode,0)
    def test_18_wrong_source_filename_view_fails(self):
        p=self.build('ordering-context','--input','diagrams/ordering-container.flowmap.json','--output','diagrams/ordering-container.flowmap.html');self.assertNotEqual(p.returncode,0)
    def test_19_typed_fact_mutations_caught_even_with_updated_receipt_hash(self):
        rel='diagrams/ordering-classes.flowmap.json';original=self.load(rel)
        for mutation in ['label','member','kind','parent','target']:
            with self.subTest(mutation=mutation):
                d=copy.deepcopy(original)
                if mutation=='label':d['nodes'][0]['label']='invented'
                if mutation=='member':d['nodes'][0]['element']['codeDetails']['methods'][0]['declaration']='invented()'
                if mutation=='kind':d['flows'][0]['steps'][0]['relationship']['codeRelation']['kind']='dependency'
                if mutation=='parent':d['nodes'][0]['element']['parentId']='order-api'
                if mutation=='target':d['nodes'][0]['element']['instanceOfId']='order-api'
                self.save(rel,d)
                for kind in ['validate','build']:
                    rec=f'qa/repo-flowmap-{kind}-ordering-classes.json';r=self.load(rec);r['specification']['sha256']=hashlib.sha256((self.root/rel).read_bytes()).hexdigest();self.save(rec,r)
                self.assertIn('DIA-008',[e.code for e in dia(self.root,self.model).errors])
    def test_20_same_size_artifact_change_fails(self):
        p=self.root/'diagrams/ordering-context.flowmap.html';raw=p.read_bytes();p.write_bytes(raw.replace(b'Repo Flowmap',b'Fake Flowmap',1))
        self.assertIn('RCP-005',[e.code for e in rcp(self.root,model_path=self.model).errors])
    def test_21_current_native_implementation_hash_required(self):
        rec='qa/repo-flowmap-build-ordering-context.json';r=self.load(rec);r['rendererSha256']='0'*64;self.save(rec,r)
        self.assertIn('RCP-010',[e.code for e in rcp(self.root,model_path=self.model).errors])
    def test_22_wrong_view_receipt_fails(self):
        rec='qa/repo-flowmap-build-ordering-context.json';r=self.load(rec);r['viewId']='ordering-container';self.save(rec,r)
        self.assertTrue(rcp(self.root,model_path=self.model).errors)
    def test_23_preembedded_tamper_fails(self):
        r=self.load('html/report-data.json');r['diagrams'][0]['dataUri']='data:text/html;base64,'+base64.b64encode(b'<h1>wrong</h1>').decode();self.save('html/report-data.json',r)
        self.assertNotEqual(self.strict().returncode,0)
    def test_24_strict_builder_rejects_current_source_mutation(self):
        rel='diagrams/ordering-sequence.flowmap.json';d=self.load(rel);d['flows'][0]['steps'].reverse();self.save(rel,d)
        self.assertNotEqual(self.strict().returncode,0)
    def test_25_input_equals_derived_path_rejected_before_any_write(self):
        p=self.root/'diagrams/ordering-context.flowmap.json';p.write_bytes(self.model.read_bytes());before=self.snapshot()
        result=self.build('ordering-context','--model','diagrams/ordering-context.flowmap.json')
        self.assertNotEqual(result.returncode,0);self.assertIn('collision',result.stderr);self.assertEqual(before,self.snapshot())
    def test_26_input_equals_html_output_rejected_before_any_write(self):
        p=self.root/'diagrams/ordering-context.flowmap.html';p.write_bytes(self.model.read_bytes());before=self.snapshot()
        result=self.build('ordering-context','--model','diagrams/ordering-context.flowmap.html');self.assertNotEqual(result.returncode,0);self.assertEqual(before,self.snapshot())
    def test_27_input_equals_receipt_rejected_before_any_write(self):
        rel='qa/repo-flowmap-build-ordering-context.json';(self.root/rel).write_bytes(self.model.read_bytes());before=self.snapshot()
        self.assertNotEqual(self.build('ordering-context','--model',rel).returncode,0);self.assertEqual(before,self.snapshot())
    def test_28_hardlink_to_model_output_rejected_before_any_write(self):
        p=self.root/'diagrams/ordering-context.flowmap.html';p.unlink();p.hardlink_to(self.model);before=self.snapshot()
        self.assertNotEqual(self.build().returncode,0);self.assertEqual(before,self.snapshot())
    def test_29_symlink_receipt_rejected_before_any_write(self):
        p=self.root/'qa/repo-flowmap-validate-ordering-context.json';p.unlink();p.symlink_to(self.model);before=self.snapshot()
        self.assertNotEqual(self.build().returncode,0);self.assertEqual(before,self.snapshot())
    def test_30_ledger_output_alias_rejected_before_any_write(self):
        p=self.root/'diagrams/ordering-context.flowmap.json';p.unlink();p.hardlink_to(self.ledger);before=self.snapshot()
        self.assertNotEqual(self.build().returncode,0);self.assertEqual(before,self.snapshot())
    def test_31_duplicate_outputs_rejected(self):
        with self.assertRaisesRegex(ValueError,'collision'):assert_distinct_paths({'model':self.model},{'a':self.root/'out','b':self.root/'out'})
    def test_32_native_standalone_input_output_collision(self):
        p=self.root/'diagrams/ordering-context.flowmap.json';before=p.read_bytes();r=subprocess.run(['node',str(ROOT/'assets/repo-flowmap/scripts/build_flowmap.mjs'),str(p),str(ROOT/'assets/repo-flowmap/template.html'),str(p)],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0);self.assertEqual(before,p.read_bytes())
    def test_33_native_standalone_template_output_collision(self):
        template=self.root/'local-template.html';shutil.copyfile(ROOT/'assets/repo-flowmap/template.html',template);before=template.read_bytes();r=subprocess.run(['node',str(ROOT/'assets/repo-flowmap/scripts/build_flowmap.mjs'),str(self.root/'diagrams/ordering-context.flowmap.json'),str(template),str(template)],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0);self.assertEqual(before,template.read_bytes())
    def test_34_native_standalone_declared_canonical_collision(self):
        before=self.model.read_bytes();r=subprocess.run(['node',str(ROOT/'assets/repo-flowmap/scripts/build_flowmap.mjs'),str(self.root/'diagrams/ordering-context.flowmap.json'),str(ROOT/'assets/repo-flowmap/template.html'),str(self.model)],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0);self.assertEqual(before,self.model.read_bytes())
    def test_35_invalid_new_native_mode_rejected(self):
        p='diagrams/ordering-context.flowmap.json';d=self.load(p);d['c4']['mode']='invented';self.save(p,d);r=subprocess.run(['node',str(ROOT/'assets/repo-flowmap/scripts/validate_flowmap.mjs'),str(self.root/p)],capture_output=True,text=True);self.assertNotEqual(r.returncode,0)
    def test_36_failed_regeneration_invalidates_old_success(self):
        old=(self.root/'diagrams/ordering-classes.flowmap.html').read_bytes();m=self.load('model/architecture-model.json');next(e for e in m['elements'] if e['id']=='entity').pop('codeDetails');self.save('model/architecture-model.json',m)
        self.assertNotEqual(self.build('ordering-classes').returncode,0);self.assertFalse(self.load('qa/repo-flowmap-build-ordering-classes.json')['ok']);self.assertEqual(old,(self.root/'diagrams/ordering-classes.flowmap.html').read_bytes())
    def test_37_same_names_preserve_canonical_identity(self):
        m=self.load('model/architecture-model.json');next(e for e in m['elements'] if e['id']=='order-class')['name']='Entity';self.save('model/architecture-model.json',m)
        self.assertEqual(self.build('ordering-classes').returncode,0)
    def test_38_valid_subset_view_not_rejected(self):
        m=self.load('model/architecture-model.json');v=next(v for v in m['views'] if v['id']=='ordering-container');v['elementIds']=['customer','web-app','order-api'];v['relationshipIds']=['customer-to-web','web-to-api'];self.save('model/architecture-model.json',m)
        self.assertEqual(self.build('ordering-container').returncode,0)
    def test_39_missing_explicit_model_does_not_succeed(self):self.assertNotEqual(self.build('ordering-context','--model','missing.json').returncode,0)
    def test_40_legacy_typed_command_rechecks_canonical(self):
        p=subprocess.run([sys.executable,str(SCRIPTS/'build_repo_flowmap.py'),'--root',str(self.root),'--input','diagrams/ordering-context.flowmap.json','--output','diagrams/ordering-context.flowmap.html'],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)
    def test_41_runtime_uses_bbox_for_self_call_export_extent(self):
        # Browser companion test measures real glyphs; this is only a wiring regression.
        t=(ROOT/'assets/repo-flowmap/template.html').read_text();self.assertIn('bbox.x+bbox.width+32',t);self.assertIn('cloneVp.classList.add',t)
    def test_42a_svg_output_html_collision_before_receipt_write(self):
        p=self.root/'diagrams/ordering-context.flowmap.html';before=self.snapshot()
        r=subprocess.run([sys.executable,str(SCRIPTS/'export_repo_flowmap_svg.py'),'--root',str(self.root),'--html','diagrams/ordering-context.flowmap.html','--output','diagrams/ordering-context.flowmap.html'],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0);self.assertIn('collision',r.stderr);self.assertEqual(before,self.snapshot())
    def test_42b_svg_output_canonical_collision_before_receipt_write(self):
        before=self.snapshot();r=subprocess.run([sys.executable,str(SCRIPTS/'export_repo_flowmap_svg.py'),'--root',str(self.root),'--html','diagrams/ordering-context.flowmap.html','--output','model/architecture-model.json'],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0);self.assertIn('collision',r.stderr);self.assertEqual(before,self.snapshot())
    def test_42c_legacy_typed_declared_model_receipt_collision(self):
        model_rel='qa/repo-flowmap-build-ordering-context.json';(self.root/model_rel).write_bytes(self.model.read_bytes())
        raw=(self.root/model_rel).read_bytes();m=json.loads(raw)
        d=project(m,model_rel,hashlib.sha256(raw).hexdigest(),'ordering-context');self.save('diagrams/ordering-context.flowmap.json',d);before=self.snapshot()
        r=subprocess.run([sys.executable,str(SCRIPTS/'build_repo_flowmap.py'),'--root',str(self.root),'--input','diagrams/ordering-context.flowmap.json','--output','diagrams/ordering-context.flowmap.html'],capture_output=True,text=True)
        self.assertNotEqual(r.returncode,0);self.assertIn('collision',r.stderr);self.assertEqual(before,self.snapshot())
    def report_collision(self, *options):
        before=self.snapshot()
        result=subprocess.run([sys.executable,str(SCRIPTS/'build_html_report.py'),'--root',str(self.root),'--data','html/report-data.json','--template',str(ROOT/'assets/html-report-template.html'),'--output',str(self.root/'index.html'),*options],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertIn('collision',result.stderr);self.assertEqual(before,self.snapshot())
    def test_43_report_output_canonical_collision(self):self.report_collision('--output',str(self.model))
    def test_44_validation_output_canonical_collision(self):self.report_collision('--validation-output',str(self.model))
    def test_45_report_output_data_collision(self):self.report_collision('--output',str(self.root/'html/report-data.json'))
    def test_46_report_output_native_html_collision(self):self.report_collision('--output',str(self.root/'diagrams/ordering-context.flowmap.html'))
    def test_47_duplicate_report_outputs(self):self.report_collision('--validation-output',str(self.root/'index.html'))
    def test_48_report_consumed_sources_collision_matrix(self):
        # Omitting contentPath or non-renderer QA provenance must break this test.
        for rel in ('docs/raw.md', 'qa/review-notes.json'):
            for option in ('--output', '--validation-output'):
                for alias in ('direct', 'symlink', 'hardlink'):
                    with self.subTest(source=rel, option=option, alias=alias):
                        self.save(rel, {'note': 'preserve source bytes'})
                        self.save('docs/raw.md', {'note': 'raw document'})
                        report = self.load('html/report-data.json')
                        report['artifacts'] = [{'id': 'raw', 'name': 'Raw', 'kind': 'document',
                                                'contentPath': 'docs/raw.md', 'content': None, 'mimeType': None,
                                                'downloadName': 'raw.md', 'required': True}]
                        self.save('html/report-data.json', report)
                        baseline = self.strict()
                        self.assertEqual(baseline.returncode, 0, baseline.stderr + baseline.stdout)
                        target = self.root / rel
                        if alias != 'direct':
                            target = self.root / ('alias-' + alias)
                            if alias == 'hardlink': target.hardlink_to(self.root / rel)
                            else: target.symlink_to(self.root / rel)
                        try:
                            self.report_collision(option, str(target))
                        finally:
                            if alias != 'direct': target.unlink()

    def test_49_svg_provenance_collision_matrix(self):
        baseline = self.strict()
        self.assertEqual(baseline.returncode, 0, baseline.stderr + baseline.stdout)
        for rel in ('qa/evidence-ledger.json', 'qa/repo-flowmap-validate-ordering-context.json',
                    'qa/repo-flowmap-build-ordering-context.json', 'html/report-data.json',
                    'model/architecture-session.json', 'diagrams/ordering-container.flowmap.html'):
            for option in ('--output', '--receipt'):
                for alias in ('direct', 'symlink', 'hardlink'):
                    with self.subTest(source=rel, option=option, alias=alias):
                        target = self.root / rel
                        if alias != 'direct':
                            target = self.root / ('alias-' + alias)
                            if alias == 'hardlink': target.hardlink_to(self.root / rel)
                            else: target.symlink_to(self.root / rel)
                        before = self.snapshot()
                        result = subprocess.run([
                            sys.executable, str(SCRIPTS/'export_repo_flowmap_svg.py'),
                            '--root', str(self.root), '--html', 'diagrams/ordering-context.flowmap.html',
                            '--chromium', '/nonexistent-collision-test-browser', option, str(target)
                        ], capture_output=True, text=True)
                        try:
                            self.assertNotEqual(result.returncode, 0)
                            self.assertIn('path collision', result.stderr)
                            self.assertEqual(before, self.snapshot())
                        finally:
                            # Restore after RED so every subcase starts with valid provenance.
                            for name, raw in before.items(): (self.root/name).write_bytes(raw)
                            for path in self.root.rglob('*'):
                                if path.is_file() and str(path.relative_to(self.root)) not in before: path.unlink()
                            if alias != 'direct': target.unlink()

    def test_50_svg_default_outputs_regenerate_in_real_browser(self):
        import importlib.util
        browser = shutil.which('chromium') or shutil.which('google-chrome')
        mac_browser = Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
        if not browser and mac_browser.is_file(): browser = str(mac_browser)
        if not browser or importlib.util.find_spec('playwright') is None:
            self.skipTest('optional real Chromium and Playwright required')
        for _ in range(2):
            result = subprocess.run([
                sys.executable, str(SCRIPTS/'export_repo_flowmap_svg.py'),
                '--root', str(self.root), '--html', 'diagrams/ordering-context.flowmap.html',
                '--chromium', browser
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertTrue(self.load('qa/repo-flowmap-svg-ordering-context.json')['ok'])
            self.assertGreater((self.root/'diagrams/ordering-context.flowmap.svg').stat().st_size, 0)

    def test_42_archify_priority_unchanged(self):
        self.assertNotIn('c4-semantic',(SCRIPTS/'doctor.py').read_text())

    @unittest.skipUnless(sync_playwright and Path(ANCHOR_CHROME).is_file(), 'actual Chrome and Playwright required')
    def test_53_unrouteable_relations_warn_in_dom_and_export_without_losing_legend(self):
        # Fault fixture changes only input/layout, never routing, warning or export code.
        # Removing the warning, escaping, layout reservation or legend must fail.
        ids = ['blocked-<image href="x" onerror="alert(1)"/> & 한글', 'blocked-second-' + 'R' * 180]
        source = (self.root/'diagrams/ordering-context.flowmap.html').read_text()
        source = source.replace('  function c4StaticMap(flow) {', '''  function c4StaticMap(flow) {
    flow.steps = %s.map(function(id){
      var s=JSON.parse(JSON.stringify(flow.steps[0]));
      s.relationshipId=id;s.relationship.id=id;return s;
    });''' % json.dumps(ids, ensure_ascii=False).replace('<', '\\u003c'), 1)
        layout_end = '    return L;\n  }\n  function c4BoundaryMarkup'
        self.assertIn(layout_end, source)
        source = source.replace(layout_end, '''    var terminals=Object.keys(L.pos).map(function(id){return L.pos[id];});
    var a=terminals[0],b=terminals[1];
    b.x=a.x;b.y=a.y;b.w=a.w;b.h=a.h;
    return L;
  }
  function c4BoundaryMarkup''', 1)
        fixture = self.root/'overlapped.html';fixture.write_text(source)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=ANCHOR_CHROME, headless=True)
            page = browser.new_page(viewport={'width':1440,'height':1000}, offline=True)
            errors=[];page.on('pageerror', lambda error: errors.append(str(error)))
            try:
                page.goto(fixture.as_uri())
                page.wait_for_function('window.repoFlowmap !== undefined')
                warning = page.locator('#vp .c4-route-warning')
                self.assertEqual(warning.count(), 1, 'unrouteable relationships must visibly warn')
                self.assertTrue(warning.is_visible())
                text = warning.text_content()
                self.assertIn('경고', text)
                for relation_id in ids: self.assertIn(relation_id, text)
                self.assertEqual(page.locator('#vp .c4-edge').count(), 0, 'no empty or unsafe paths')
                self.assertEqual(page.locator('#vp .c4-relation-row').count(), 2)
                self.assertEqual(page.locator('#vp image').count(), 0, 'IDs are text, not active SVG')
                self.assertEqual(page.locator('svg[data-render-status]').get_attribute('data-render-status'), 'pass')
                exported = page.evaluate('window.repoFlowmap.exportSvg()')
                export_path=self.root/'warning.svg';export_path.write_text(exported)
                page.goto(export_path.as_uri())
                result=page.evaluate('''() => {
                  const warning=document.querySelector('.c4-route-warning');
                  const legend=document.querySelector('.c4-relation-row');
                  const box=warning.getBBox(), row=legend.getBBox();
                  const view=document.documentElement.viewBox.baseVal;
                  return {text:warning.textContent, rows:document.querySelectorAll('.c4-relation-row').length,
                    injected:document.querySelectorAll('image,parsererror').length,
                    visible:getComputedStyle(warning).display!=='none' && box.width>0 && box.height>0,
                    inBounds:box.x>=0 && box.y>=0 && box.x+box.width<=view.width && box.y+box.height<=view.height,
                    beforeLegend:box.y+box.height<row.y};
                }''')
                for relation_id in ids: self.assertIn(relation_id, result['text'])
                self.assertEqual(result['rows'], 2)
                self.assertEqual(result['injected'], 0)
                self.assertTrue(result['visible'])
                self.assertTrue(result['inBounds'])
                self.assertTrue(result['beforeLegend'])
                self.assertEqual(errors, [])
            finally:
                browser.close()

    @unittest.skipUnless(sync_playwright and Path(ANCHOR_CHROME).is_file(), 'actual Chrome and Playwright required')
    def test_54_badge_starved_safe_routes_keep_numbered_identity_in_dom_and_svg(self):
        # Removing the explicit numbered fallback, dropping the safe path, or
        # admitting a badge over a card must fail. Only canonical input/layout
        # changes below; badge placement, routing and export are production code.
        m = self.load('model/architecture-model.json')
        relation = next(r for r in m['relationships'] if r['id'] == 'customer-to-system')
        relation['destinationId'] = relation['sourceId']
        self.save('model/architecture-model.json', m)
        built = self.build('ordering-context')
        self.assertEqual(built.returncode, 0, built.stderr)
        self_fixture = self.root/'diagrams/ordering-context.flowmap.html'
        # A 32px gap admits the real route but not a badge's two 17px exclusions.
        # This is the deployment regression's narrow-corridor constraint without
        # depending on the optional, private actual input package.
        source = (self.seed/'diagrams/ordering-context.flowmap.html').read_text()
        layout_end = '    return L;\n  }\n  function c4BoundaryMarkup'
        source = source.replace(layout_end, '''    var a=L.pos.customer,b=L.pos['ordering-system'];
    b.x=a.x+a.w+32;b.y=a.y+(a.h-b.h)/2;
    return L;
  }
  function c4BoundaryMarkup''', 1)
        malicious = 'narrow-<image href="x" onerror="alert(1)"/> & 한글-' + 'R'*180
        source = source.replace('  function c4StaticMap(flow) {', '''  function c4StaticMap(flow) {
    flow.steps[0].relationshipId=%s;flow.steps[0].relationship.id=%s;''' % (
            json.dumps(malicious, ensure_ascii=False).replace('<', '\\u003c'),
            json.dumps(malicious, ensure_ascii=False).replace('<', '\\u003c')), 1)
        narrow_fixture = self.root/'narrow.html';narrow_fixture.write_text(source)
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=ANCHOR_CHROME, headless=True)
            try:
                for fixture, relation_id in ((self_fixture, 'customer-to-system'), (narrow_fixture, malicious)):
                    for width in (1440, 390):
                        with self.subTest(fixture=fixture.name, width=width):
                            page = browser.new_page(viewport={'width':width, 'height':1000}, offline=True)
                            errors=[];page.on('pageerror', lambda error: errors.append(str(error)))
                            page.goto(fixture.as_uri())
                            page.wait_for_function('window.repoFlowmap !== undefined')
                            self.assertTrue(page.evaluate('window.repoFlowmap.ready()'),
                                            page.locator('#map').get_attribute('data-render-error'))
                            edge = page.locator('#vp path.c4-edge')
                            self.assertEqual(edge.count(), 1, 'a safe edge must not be dropped')
                            self.assertEqual(edge.get_attribute('data-relation'), relation_id)
                            self.assertIn('[1]', edge.locator('title').text_content())
                            self.assertIn(relation_id, edge.locator('title').text_content())
                            self.assertEqual(page.locator('#vp .badges .badge').count(), 0,
                                             'no overlapping on-route badge may be accepted')
                            row = page.locator('#vp .c4-relation-row')
                            self.assertEqual(row.count(), 1)
                            self.assertEqual(row.locator('.badge').count(), 1)
                            self.assertEqual(row.locator('.badge').get_attribute('data-i'), '0')
                            self.assertIn('선 위 번호 공간 부족', row.text_content())
                            self.assertIn(relation_id, row.text_content())
                            self.assertIn('customer', row.text_content())
                            self.assertIn('ordering-system' if fixture == narrow_fixture else 'customer', row.text_content())
                            self.assertEqual(page.locator('#vp image').count(), 0)
                            if fixture == narrow_fixture:
                                self.assertAlmostEqual(edge.evaluate('(e)=>e.getTotalLength()'), 32, delta=0.01)
                            # The relocated number remains a real keyboard control,
                            # and selecting it must survive the ensuing re-render.
                            row.locator('.badge').focus();page.keyboard.press('Enter')
                            self.assertEqual(page.evaluate('window.repoFlowmap.state().step'), 0)
                            self.assertEqual(page.locator('#vp .c4-edge.hot').count(), 1)
                            self.assertEqual(page.locator('#vp .c4-relation-row .badge.hot').count(), 1)
                            svg = page.evaluate('window.repoFlowmap.exportSvg()')
                            exported = self.root/'badge-fallback.svg';exported.write_text(svg)
                            page.goto(exported.as_uri())
                            result = page.evaluate('''() => {
                              const row=document.querySelector('.c4-relation-row'), badge=row.querySelector('.badge');
                              const b=badge.getBBox(), r=row.querySelector('rect').getBBox();
                              const v=document.documentElement.viewBox.baseVal;
                              return {text:row.textContent, title:document.querySelector('.c4-edge title').textContent,
                                count:document.querySelectorAll('.c4-edge').length,
                                injected:document.querySelectorAll('image,parsererror').length,
                                visible:getComputedStyle(badge).display!=='none' && b.width>0 && b.height>0,
                                inRow:b.x>=r.x && b.y>=r.y && b.x+b.width<=r.x+r.width && b.y+b.height<=r.y+r.height,
                                inBounds:r.x>=0 && r.y>=0 && r.x+r.width<=v.width && r.y+r.height<=v.height};
                            }''')
                            self.assertEqual(result['count'], 1)
                            self.assertEqual(result['injected'], 0)
                            self.assertTrue(result['visible'])
                            self.assertTrue(result['inRow'])
                            self.assertTrue(result['inBounds'])
                            self.assertIn('선 위 번호 공간 부족', result['text'])
                            for key in ('text', 'title'): self.assertIn(relation_id, result[key])
                            self.assertEqual(errors, [])
                            page.close()
            finally:
                browser.close()

    @unittest.skipUnless(sync_playwright and Path(ANCHOR_CHROME).is_file(), 'actual Chrome and Playwright required')
    def test_52_edge_anchor_geometry_in_real_browser(self):
        '''실제 브라우저 렌더 기하 계약: 모든 c4 엣지 L 세그먼트는 축에 정렬되고,
        단일 관계 context 뷰는 꺾임 없는 직선 한 구간(M+L만)으로 연결된다.'''
        import re
        def tokens(d):
            return re.findall(r'[MLQA]|-?\d+\.?\d*', d)
        def l_segments(d):
            seq=tokens(d);out=[];cur=None;j=0
            while j<len(seq):
                t=seq[j]
                if t in 'MLQA':
                    cmd=t;got=[];j+=1
                    while j<len(seq) and seq[j] not in 'MLQA':
                        got.append(float(seq[j]));j+=1
                    if cmd=='M' and len(got)>=2:cur=(got[0],got[1])
                    elif cmd=='L':
                        for k in range(0,len(got)-1,2):
                            nxt=(got[k],got[k+1])
                            if cur is not None:out.append((cur,nxt))
                            cur=nxt
                    elif cmd=='Q' and len(got)>=4:cur=(got[2],got[3])
                    elif cmd=='A' and len(got)>=7:cur=(got[5],got[6])
                else:j+=1
            return out
        views=['ordering-context','ordering-container','ordering-components','ordering-classes','ordering-deployment']
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=ANCHOR_CHROME,headless=True)
            page=browser.new_page(viewport={'width':1440,'height':1000},offline=True)
            try:
                ds_by_view={}
                for vid in views:
                    page.goto((self.root/f'diagrams/{vid}.flowmap.html').as_uri())
                    page.wait_for_selector('path.c4-edge',state='attached',timeout=15000)
                    ds_by_view[vid]=page.eval_on_selector_all('path.c4-edge','els=>els.map(e=>e.getAttribute("d"))')
                    self.assertEqual(page.locator('#vp .c4-route-warning').count(), 0, f'{vid}: unexpected warning')
            finally:
                browser.close()
            for vid in views:
                ds=ds_by_view[vid]
                expected = len(self.load(f'diagrams/{vid}.flowmap.json')['flows'][0]['steps'])
                self.assertEqual(len(ds), expected, f'{vid}: missing relation paths')
                for d in ds:
                    self.assertTrue(d and d.startswith('M '), f'{vid}: empty/invalid relation path')
                    self.assertNotRegex(d, r'NaN|Infinity|[Cc]', f'{vid}: non-orthogonal route')
                    for (x0,y0),(x1,y1) in l_segments(d):
                        self.assertTrue(abs(x1-x0)<0.5 or abs(y1-y0)<0.5,
                            f'{vid}: diagonal edge segment ({x0},{y0})->({x1},{y1})')
            ctx=ds_by_view['ordering-context']
            self.assertEqual(len(ctx),1,'context view should carry exactly one relation edge')
            kinds=[t for t in tokens(ctx[0]) if t in 'MLQA']
            self.assertEqual(['M','L'],kinds,
                f'context edge must be one straight segment, got {kinds}: {ctx[0]}')

if __name__=='__main__':unittest.main()
