"""End-to-end build gates and backwards-compatible print embedding regressions."""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_html_report import embed_assets
from c4_validation import ValidationReport, schema_report


class ReportIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        shutil.copytree(ROOT / "examples", self.root / "examples")
        self.data_path = self.root / "examples/html-report-data.example.json"
        self.data = json.loads(self.data_path.read_text())
        self.data["diagrams"] = []
        self.output = self.root / "index.html"
        self.validation = self.root / "validation.json"

    def save(self) -> None:
        self.data_path.write_text(json.dumps(self.data))

    def cli(self, script: str, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / script), "--root", str(self.root), *args],
            capture_output=True, text=True, check=False,
        )

    def build(self, *args: str) -> subprocess.CompletedProcess[str]:
        self.save()
        return self.cli("build_html_report.py", "--data", str(self.data_path),
                        "--template", str(ROOT / "assets/html-report-template.html"),
                        "--output", str(self.output), "--validation-output", str(self.validation), *args)

    def renderer(self) -> Path:
        model = json.loads((self.root / self.data["build"]["canonicalModelPath"]).read_text())
        view = next(v for v in model["views"] if v["id"] == "ordering-container")
        elements = {e["id"]: e for e in model["elements"]}
        rels = {r["id"]: r for r in model["relationships"]}
        (self.root / "diagrams").mkdir()
        (self.root / "qa").mkdir()
        source = self.root / "diagrams/ordering-container.architecture.json"
        source.write_text(json.dumps({
            "components": [{"id": eid, "label": elements[eid]["name"]} for eid in view["elementIds"]],
            "connections": [{"id": rid, "from": rels[rid]["sourceId"], "to": rels[rid]["destinationId"]}
                            for rid in view["relationshipIds"]],
        }))
        artifact = self.root / "diagrams/ordering-container.html"
        artifact.write_text("<!doctype html><html><body>Ordering</body></html>")
        example = json.loads((ROOT / "examples/html-report-data.example.json").read_text())
        diagram = next(d for d in example["diagrams"] if d["viewId"] == "ordering-container")
        diagram.update(assetPath=str(artifact.relative_to(self.root)), dataUri=None, mimeType="text/html")
        diagram.pop("printAssetPath", None)
        self.data["diagrams"] = [diagram]
        (self.root / "qa/archify-validate-ordering-container.json").write_text('{"ok":true}')
        receipt = {"ok": True, "input": str(source.relative_to(self.root)),
                   "specification": {"sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
                   "output": str(artifact.relative_to(self.root)),
                   "artifact": {"sha256": hashlib.sha256(artifact.read_bytes()).hexdigest()}}
        (self.root / "qa/archify-deliver-ordering-container.json").write_text(json.dumps(receipt))
        return source

    def test_strict_builder_includes_diagram_gate(self) -> None:
        source = self.renderer()
        source.write_text('{"components":[],"connections":[]}')
        result = self.build()
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertFalse(self.output.exists())
        self.assertIn("DIA-002", self.validation.read_text())

    def test_strict_builder_includes_receipt_gate(self) -> None:
        self.renderer()
        (self.root / "qa/archify-deliver-ordering-container.json").unlink()
        result = self.build()
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertFalse(self.output.exists())
        self.assertIn("RCP-003", self.validation.read_text())

    def test_lenient_build_exposes_receipt_failure(self) -> None:
        self.renderer()
        (self.root / "qa/archify-deliver-ordering-container.json").unlink()
        result = self.build("--lenient")
        self.assertEqual(2, result.returncode, result.stdout + result.stderr)
        self.assertIn('"result":"FAIL"', self.output.read_text())
        self.assertIn("RCP-003", self.output.read_text())

    def test_valid_renderer_with_custom_canonical_path_passes_both_entrypoints(self) -> None:
        self.renderer()
        # A conventional-path model must not silently supersede the report's model.
        (self.root / "model").mkdir()
        (self.root / "model/architecture-model.json").write_text('{"views":[]}')
        result = self.build()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("DIA-001", self.validation.read_text())
        self.assertIn("RCP-001", self.validation.read_text())
        result = self.cli("validate_all.py", "--data", str(self.data_path))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_explicit_missing_data_fails_instead_of_text_fallback(self) -> None:
        result = self.cli("validate_all.py", "--data", "missing.json", "--output-json", str(self.validation))
        self.assertNotEqual(0, result.returncode, result.stdout)
        self.assertIn("ALL-001", self.validation.read_text())
        self.assertEqual("FAIL", json.loads(self.validation.read_text())["result"])

    def test_explicit_missing_model_fails_without_report_data(self) -> None:
        result = self.cli("validate_all.py", "--model", "missing.json",
                          "--output-json", str(self.validation))
        self.assertNotEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertEqual("FAIL", json.loads(self.validation.read_text())["result"])
        self.assertIn("RCP-000", self.validation.read_text())

    def test_omitted_missing_default_data_allows_text_fallback(self) -> None:
        result = self.cli("validate_all.py")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)

    def test_legacy_diagram_without_print_path_is_schema_valid(self) -> None:
        data = json.loads((ROOT / "examples/html-report-data.example.json").read_text())
        for diagram in data["diagrams"]:
            diagram.pop("printAssetPath", None)
        report = schema_report("legacy", data, ROOT / "references/html-report-data.schema.json")
        self.assertEqual([], report.errors)

    def test_preembedded_screen_still_embeds_print(self) -> None:
        raw = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><rect width="10" height="10"/></svg>'
        (self.root / "print.svg").write_bytes(raw)
        diagram = {"dataUri": "data:text/html;base64,PGh0bWw+PC9odG1sPg==", "printAssetPath": "print.svg"}
        report = ValidationReport("embed")
        embed_assets(self.root, {"diagrams": [diagram]}, 10000, report)
        self.assertEqual("data:image/svg+xml;base64," + base64.b64encode(raw).decode(), diagram.get("printDataUri"))
        self.assertEqual("print.svg", diagram.get("printSourcePath"))
        self.assertEqual([], report.errors)

    def test_print_mime_is_inferred_from_print_file_not_screen(self) -> None:
        (self.root / "screen.html").write_text("<html></html>")
        for extension, mime in [("png", "image/png"), ("jpg", "image/jpeg"), ("webp", "image/webp")]:
            with self.subTest(extension=extension):
                (self.root / f"print.{extension}").write_bytes(b"print bytes")
                diagram = {"assetPath": "screen.html", "mimeType": "text/html", "printAssetPath": f"print.{extension}"}
                embed_assets(self.root, {"diagrams": [diagram]}, 10000, ValidationReport("embed"))
                self.assertEqual(f"data:{mime};base64,cHJpbnQgYnl0ZXM=", diagram.get("printDataUri"))


if __name__ == "__main__":
    unittest.main()
