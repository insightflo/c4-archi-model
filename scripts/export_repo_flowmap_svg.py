#!/usr/bin/env python3
"""Execute the SAME native repo-flowmap HTML and export its SVG with source binding.

Optional browser tool: Python Playwright + Chromium. Default transport is file://.
'injected-test' is an explicitly labelled test fallback, NOT a file:// verification.
No independent SVG rendering/layout is performed by this script.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode = True
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
from build_repo_flowmap import assert_distinct_paths, write_receipt
from c4_validation import validate_svg


def main() -> int:
    p=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--html',type=Path,required=True)
    p.add_argument('--output',type=Path)
    p.add_argument('--receipt',type=Path)
    p.add_argument('--chromium',default=None)
    p.add_argument('--transport',choices=['file','injected-test'],default='file')
    a=p.parse_args();root=a.root.resolve();source=root/a.html
    stem=source.name[:-len('.flowmap.html')] if source.name.endswith('.flowmap.html') else source.stem
    output=root/(a.output or Path('diagrams')/(stem+'.flowmap.svg'))
    receipt=root/(a.receipt or Path('qa')/('repo-flowmap-svg-'+stem+'.json'))
    try:
        for f in (source,output,receipt):
            if not f.resolve().is_relative_to(root):raise ValueError('all paths must stay inside --root')
        reads={'native HTML':source}
        ir=root/'diagrams'/(stem+'.flowmap.json')
        if ir.is_file():
            reads['native input']=ir;data=json.loads(ir.read_bytes())
            if isinstance(data.get('c4'),dict):reads['canonical']=root/data['c4']['modelPath']
        # Package sources and QA provenance are not export destinations. Only
        # this view's derived SVG and export receipt are regenerable; exclude
        # their lexical names, not aliases that could hide a protected input.
        regenerable={root/'diagrams'/(stem+'.flowmap.svg'),
                     root/'qa'/('repo-flowmap-svg-'+stem+'.json')}
        for name in ('model','html','diagrams','qa'):
            directory=root/name
            if directory.is_dir():
                for path in directory.rglob('*'):
                    if path.is_file() and path not in regenerable:
                        reads[str(path)]=path
        assert_distinct_paths(reads,{'SVG':output,'receipt':receipt})
    except (OSError,ValueError,KeyError,TypeError) as exc:
        print(f'[FAIL] {exc}',file=sys.stderr);return 1
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print('[NOT_RUN] optional Python Playwright is not installed',file=sys.stderr);return 2
    receipt.parent.mkdir(parents=True,exist_ok=True)
    write_receipt(receipt,{'ok':False,'source':source.relative_to(root).as_posix(),'message':'extraction not completed'})
    try:
        raw=source.read_bytes();requests=[];errors=[]
        with sync_playwright() as pw:
            b=pw.chromium.launch(executable_path=a.chromium or shutil.which('chromium'),headless=True,args=['--no-sandbox'])
            context=b.new_context(viewport={'width':1600,'height':1100},offline=True)
            context.route('http://**/*',lambda route:(requests.append(route.request.url),route.abort()))
            context.route('https://**/*',lambda route:(requests.append(route.request.url),route.abort()))
            page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
            if a.transport=='file':page.goto(source.as_uri(),wait_until='load')
            else:page.set_content(raw.decode('utf-8-sig'),wait_until='load')
            page.evaluate('document.fonts.ready');page.wait_for_function('window.repoFlowmap && window.repoFlowmap.ready()')
            svg=page.evaluate('window.repoFlowmap.exportSvg()')
            state=page.evaluate('window.repoFlowmap.state()')
            if requests or errors:raise ValueError(f'native runtime requested external resources or threw: {requests!r} {errors!r}')
            if source.read_bytes()!=raw:raise ValueError('HTML changed during extraction')
            # Native export explicitly resets camera transform and sizes the SVG from
            # the actual geometry, including final participant self-call glyphs.
            output.parent.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='.flowmap-svg-',dir=root) as work:
                candidate=Path(work)/'native-export.svg'
                candidate.write_text(svg,encoding='utf-8')
                checks=validate_svg(candidate)
                if checks.errors:raise ValueError('; '.join(f.message for f in checks.errors))
                candidate.replace(output)
            b.close()
        result={'ok':True,'exitCode':0,'renderer':'repo-flowmap','source':source.relative_to(root).as_posix(),
                'sourceSha256':hashlib.sha256(raw).hexdigest(),'output':output.relative_to(root).as_posix(),
                'svgSha256':hashlib.sha256(output.read_bytes()).hexdigest(),'svgBytes':output.stat().st_size,
                'browserTransport':a.transport,'fileUrlVerified':a.transport=='file','viewId':state.get('viewId'),
                'message':'native exportSvg() execution; not a separate renderer'}
        write_receipt(receipt,result);print(f'[PASS] {output} ({a.transport}); source-bound extraction receipt');return 0
    except Exception as exc:
        blocked='ERR_BLOCKED_BY_ADMINISTRATOR' in str(exc)
        write_receipt(receipt,{'ok':False,'source':source.relative_to(root).as_posix(),'status':'NOT_RUN' if blocked else 'FAIL','message':str(exc)})
        print(f'[{"NOT_RUN" if blocked else "FAIL"}] {exc}',file=sys.stderr);return 2 if blocked else 1


if __name__=='__main__':raise SystemExit(main())
