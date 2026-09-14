"""Producer contract: real renderer runs, source bytes and failure evidence."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from validate_render_receipts import run as validate_receipts


class ReceiptProducerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "diagrams").mkdir()
        self.source = self.root / "diagrams/context.flowmap.json"
        self.output = self.root / "diagrams/context.flowmap.html"
        shutil.copyfile(ROOT / "examples/receipt-flowmap/diagrams/context.flowmap.json", self.source)

    def build(self, *extra: str, env: dict | None = None,
              script: Path | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([
            sys.executable, str(script or SCRIPTS / "build_repo_flowmap.py"),
            "--root", str(self.root), "--input", "diagrams/context.flowmap.json",
            "--output", "diagrams/context.flowmap.html", *extra,
        ], capture_output=True, text=True, env=env)

    def receipt(self, kind: str) -> dict:
        path = self.root / f"qa/repo-flowmap-{kind}-context.json"
        self.assertTrue(path.is_file(), f"missing {kind} receipt")
        return json.loads(path.read_text())

    def test_extraction_hashes_exact_source_bytes_not_normalized_text(self) -> None:
        html = self.root / "diagrams/context.html"
        raw = b'<html>\r\n<style>rect{fill:red}</style><svg><rect width="3" height="3"/></svg></html>'
        html.write_bytes(raw)
        svg = self.root / "diagrams/context.svg"
        receipt = self.root / "extract.json"
        result = subprocess.run([
            sys.executable, str(SCRIPTS / "extract_archify_svg.py"),
            "--html", str(html), "--output", str(svg), "--json", str(receipt),
        ], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(receipt.read_text())
        self.assertEqual(data.get("sourceSha256"), hashlib.sha256(raw).hexdigest())
        self.assertEqual(data["svgSha256"], hashlib.sha256(svg.read_bytes()).hexdigest())

    @unittest.skipUnless(shutil.which("node"), "Node required for bundled renderer")
    def test_build_emits_bound_receipts_accepted_by_validator(self) -> None:
        self.output.write_text("stale artifact")
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self.receipt("build")
        self.assertIs(data["ok"], True)
        self.assertEqual(data["exitCode"], 0)
        self.assertEqual(data["input"], "diagrams/context.flowmap.json")
        self.assertEqual(data["output"], "diagrams/context.flowmap.html")
        self.assertEqual(data["specification"]["sha256"], hashlib.sha256(self.source.read_bytes()).hexdigest())
        self.assertEqual(data["artifact"]["sha256"], hashlib.sha256(self.output.read_bytes()).hexdigest())
        self.assertNotEqual(self.output.read_text(), "stale artifact")
        self.assertIs(self.receipt("validate")["ok"], True)
        report = validate_receipts(self.root)
        self.assertEqual(report.errors, [])

    @unittest.skipUnless(shutil.which("node"), "Node required for bundled renderer")
    def test_invalid_input_replaces_old_success_receipts_without_claiming_stale_output(self) -> None:
        self.assertEqual(self.build().returncode, 0)
        previous = self.output.read_bytes()
        self.source.write_text('{"invalid": true}')
        result = self.build()
        self.assertNotEqual(result.returncode, 0)
        self.assertIs(self.receipt("validate")["ok"], False)
        receipt = self.receipt("build")
        self.assertIs(receipt["ok"], False)
        self.assertNotIn("artifact", receipt)
        self.assertEqual(self.output.read_bytes(), previous)
        self.assertTrue(validate_receipts(self.root).errors)

    def test_missing_node_writes_failure_not_success(self) -> None:
        result = self.build(env={**os.environ, "PATH": ""})
        self.assertNotEqual(result.returncode, 0)
        self.assertIs(self.receipt("build")["ok"], False)
        self.assertIs(self.receipt("validate")["ok"], False)
        self.assertFalse(self.output.exists())

    @unittest.skipUnless(shutil.which("node"), "Node required for bundled renderer")
    def test_real_builder_failure_never_hashes_previous_html(self) -> None:
        self.assertEqual(self.build().returncode, 0)
        previous = self.output.read_bytes()
        # Exercise the real builder against a damaged installation, not a mock.
        installation = self.root / "installation"
        (installation / "scripts").mkdir(parents=True)
        script = installation / "scripts/build_repo_flowmap.py"
        shutil.copyfile(SCRIPTS / "build_repo_flowmap.py", script)
        bundle = installation / "assets/repo-flowmap"
        shutil.copytree(ROOT / "assets/repo-flowmap/scripts", bundle / "scripts")
        (bundle / "template.html").write_text("missing injection marker")
        result = self.build(script=script)
        self.assertNotEqual(result.returncode, 0)
        self.assertIs(self.receipt("validate")["ok"], True)
        data = self.receipt("build")
        self.assertIs(data["ok"], False)
        self.assertNotEqual(data["exitCode"], 0)
        self.assertNotIn("artifact", data)
        self.assertEqual(self.output.read_bytes(), previous)

    def test_output_cannot_overwrite_source(self) -> None:
        before = self.source.read_bytes()
        result = self.build("--output", "diagrams/context.flowmap.json")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.source.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
