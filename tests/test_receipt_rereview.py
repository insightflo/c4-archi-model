"""External re-review: print image role, validate binding, shared View resolution."""
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
from urllib.parse import quote_from_bytes

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from c4_validation import ValidationReport
from validate_render_receipts import run

SVG = b'<svg xmlns="http://www.w3.org/2000/svg" width="2" height="3"><rect width="2" height="3"/></svg>'
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAIAAAADCAIAAAA2iEnWAAAAFElEQVR4nGP8//8/AwMDEwMYQCkAORsDA3CXx5UAAAAASUVORK5CYII="
)


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def uri(mime: str, raw: bytes) -> str:
    return f"data:{mime};base64," + base64.b64encode(raw).decode("ascii")


class ReceiptRereviewTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        (self.root / "diagrams").mkdir()
        (self.root / "qa").mkdir()
        self.stem = "context"
        self.source = self.root / "diagrams/context.flowmap.json"
        self.source.write_text('{"nodes": []}', encoding="utf-8")
        self.output = self.root / "diagrams/context.html"
        self.output.write_bytes(b"<!doctype html><html><body>Native diagram</body></html>")
        self.validate: dict = {"ok": True}
        self.validation_stdout: str | None = None
        self.build: dict = {
            "ok": True, "input": "diagrams/context.flowmap.json",
            "specification": {"sha256": sha(self.source.read_bytes())},
            "output": "diagrams/context.html",
            "artifact": {"sha256": sha(self.output.read_bytes())},
        }
        self.diagram: dict = {"viewId": "context", "assetPath": "diagrams/context.html"}

    def check(self) -> ValidationReport:
        qa = self.root / "qa"
        (qa / f"repo-flowmap-validate-{self.stem}.json").write_text(
            self.validation_stdout if self.validation_stdout is not None else json.dumps(self.validate),
            encoding="utf-8",
        )
        (qa / f"repo-flowmap-build-{self.stem}.json").write_text(json.dumps(self.build), encoding="utf-8")
        data = self.root / "report-data.json"
        data.write_text(json.dumps({"diagrams": [self.diagram]}), encoding="utf-8")
        return run(self.root, data)

    def assert_rejected(self, code: str, location: str = "") -> None:
        report = self.check()
        errors = [error for error in report.errors if error.code == code]
        self.assertTrue(errors, report.to_dict())
        if location:
            self.assertTrue(any(location in error.path for error in errors), report.to_dict())

    def bind_validation(self) -> None:
        self.validate = {
            "ok": True, "input": self.build["input"],
            "specification": dict(self.build["specification"]), "viewId": self.diagram["viewId"],
        }

    def print_artifact(self, suffix: str, raw: bytes) -> Path:
        output = self.root / f"diagrams/context.{suffix}"
        output.write_bytes(raw)
        extraction = {
            "ok": True, "source": self.build["output"],
            "sourceSha256": sha(self.output.read_bytes()),
            "output": str(output.relative_to(self.root)), "svgSha256": sha(raw),
        }
        (self.root / f"qa/repo-flowmap-svg-{self.stem}.json").write_text(json.dumps(extraction), encoding="utf-8")
        self.diagram["printAssetPath"] = str(output.relative_to(self.root))
        return output

    def test_absent_validate_metadata_and_null_print_fallback_pass(self) -> None:
        self.diagram.update(printAssetPath=None, printDataUri=None)
        self.assertEqual([], self.check().errors)

    def test_native_validate_stdout_still_passes(self) -> None:
        self.validation_stdout = "[PASS] schema\n[PASS] graph\n"
        self.assertEqual([], self.check().errors)

    def test_complete_validate_json_binding_passes(self) -> None:
        self.bind_validation()
        self.assertEqual([], self.check().errors)

    def test_validate_wrong_path_with_same_source_bytes_rejected(self) -> None:
        self.bind_validation()
        other = self.root / "different.json"
        other.write_bytes(self.source.read_bytes())
        self.validate["input"] = "different.json"
        self.assert_rejected("RCP-009", "validate-context.json")
        self.assert_rejected("RCP-007")

    def test_validate_wrong_digest_rejected(self) -> None:
        self.bind_validation()
        self.validate["specification"]["sha256"] = "0" * 64
        self.assert_rejected("RCP-009", "validate-context.json")

    def test_validate_wrong_view_rejected(self) -> None:
        self.bind_validation()
        self.validate["viewId"] = "container"
        self.assert_rejected("RCP-009", "validate-context.json")

    def test_partial_validate_path_or_digest_rejected(self) -> None:
        for metadata in [
            {"input": self.build["input"]},
            {"specification": self.build["specification"]},
            {"input": self.build["input"], "specification": {}},
            {"input": None, "specification": self.build["specification"]},
            {"input": self.build["input"], "specification": None},
        ]:
            with self.subTest(metadata=metadata):
                self.validate = {"ok": True, **metadata}
                self.assert_rejected("RCP-009", "validate-context.json")

    def test_validate_supplied_view_without_input_metadata_is_checked(self) -> None:
        self.validate = {"ok": True, "viewId": "context"}
        self.assertEqual([], self.check().errors)
        self.validate["viewId"] = "container"
        self.assert_rejected("RCP-009", "validate-context.json")

    def test_verified_html_cannot_be_print_asset(self) -> None:
        self.assertEqual([], self.check().errors)
        self.diagram["printAssetPath"] = self.build["output"]
        self.assert_rejected("RCP-007", "printAssetPath")

    def test_html_print_uri_rejected_even_with_verified_bytes(self) -> None:
        self.diagram["printDataUri"] = uri("text/html", self.output.read_bytes())
        self.assert_rejected("RCP-007", "printDataUri")

    def test_html_mislabeled_as_image_uri_rejected_without_print_path(self) -> None:
        for mime in ["image/svg+xml", "image/png", "image/jpeg", "image/gif", "image/webp", "image/bmp"]:
            with self.subTest(mime=mime):
                self.diagram["printDataUri"] = uri(mime, self.output.read_bytes())
                self.assert_rejected("RCP-007", "printDataUri")

    def test_html_mislabeled_as_image_file_rejected(self) -> None:
        for suffix in ["svg", "png", "jpg", "gif", "webp", "bmp"]:
            with self.subTest(suffix=suffix):
                self.print_artifact(suffix, self.output.read_bytes())
                self.assert_rejected("RCP-007", "printAssetPath")

    def test_svg_png_print_files_and_uris_pass(self) -> None:
        for suffix, mime, raw in [("svg", "image/svg+xml", SVG), ("png", "image/png", PNG)]:
            with self.subTest(suffix=suffix):
                self.print_artifact(suffix, raw)
                self.diagram["printDataUri"] = uri(mime, raw)
                self.assertEqual([], self.check().errors)
                self.diagram["printAssetPath"] = None
                self.assertEqual([], self.check().errors)

    def test_other_supported_raster_formats_pass(self) -> None:
        # Actual 2x3 white images, encoded once with Pillow; no runtime dependency.
        fixtures = [
            ("gif", "image/gif", "R0lGODdhAgADAIEAAP///wAAAAAAAAAAACwAAAAAAgADAAAIBgABCBwYEAA7"),
            ("webp", "image/webp", "UklGRiQAAABXRUJQVlA4IBgAAAAwAQCdASoCAAMAAUAmJaQAA3AA/vz0AAA="),
            ("bmp", "image/bmp", "Qk1OAAAAAAAAADYAAAAoAAAAAgAAAAMAAAABABgAAAAAABgAAADEDgAAxA4AAAAAAAAAAAAA////////AAD///////8AAP///////wAA"),
            ("jpg", "image/jpeg", "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAADAAIDASIAAhEBAxEB/8QAHwAAAQUBAQEBAQEAAAAAAAAAAAECAwQFBgcICQoL/8QAtRAAAgEDAwIEAwUFBAQAAAF9AQIDAAQRBRIhMUEGE1FhByJxFDKBkaEII0KxwRVS0fAkM2JyggkKFhcYGRolJicoKSo0NTY3ODk6Q0RFRkdISUpTVFVWV1hZWmNkZWZnaGlqc3R1dnd4eXqDhIWGh4iJipKTlJWWl5iZmqKjpKWmp6ipqrKztLW2t7i5usLDxMXGx8jJytLT1NXW19jZ2uHi4+Tl5ufo6erx8vP09fb3+Pn6/8QAHwEAAwEBAQEBAQEBAQAAAAAAAAECAwQFBgcICQoL/8QAtREAAgECBAQDBAcFBAQAAQJ3AAECAxEEBSExBhJBUQdhcRMiMoEIFEKRobHBCSMzUvAVYnLRChYkNOEl8RcYGRomJygpKjU2Nzg5OkNERUZHSElKU1RVVldYWVpjZGVmZ2hpanN0dXZ3eHl6goOEhYaHiImKkpOUlZaXmJmaoqOkpaanqKmqsrO0tba3uLm6wsPExcbHyMnK0tPU1dbX2Nna4uPk5ebn6Onq8vP09fb3+Pn6/9oADAMBAAIRAxEAPwD3+iiigD//2Q=="),
        ]
        for suffix, mime, encoded in fixtures:
            with self.subTest(suffix=suffix):
                raw = base64.b64decode(encoded)
                self.print_artifact(suffix, raw)
                self.diagram["printDataUri"] = uri(mime, raw)
                self.assertEqual([], self.check().errors)

    def test_svg_percent_encoded_print_uri_passes(self) -> None:
        self.print_artifact("svg", SVG)
        self.diagram["printAssetPath"] = None
        self.diagram["printDataUri"] = "data:image/svg+xml;charset=utf-8," + quote_from_bytes(SVG)
        self.assertEqual([], self.check().errors)

    def test_verified_svg_with_html_or_wrong_image_mime_rejected(self) -> None:
        self.print_artifact("svg", SVG)
        for mime in ["text/html", "image/png", "application/octet-stream"]:
            with self.subTest(mime=mime):
                self.diagram["printDataUri"] = uri(mime, SVG)
                self.assert_rejected("RCP-007", "printDataUri")

    def test_malformed_svg_and_truncated_png_rejected(self) -> None:
        for suffix, mime, raw in [
            ("svg", "image/svg+xml", b"<svg><g>"),
            ("svg", "image/svg+xml", b"<html><svg/></html>"),
            ("png", "image/png", b"\x89PNG\r\n\x1a\n"),
        ]:
            with self.subTest(raw=raw):
                self.print_artifact(suffix, raw)
                self.diagram["printDataUri"] = uri(mime, raw)
                self.assert_rejected("RCP-007", "printAssetPath")
                self.assert_rejected("RCP-007", "printDataUri")

    def test_number_prefix_alias_shares_dia_resolution(self) -> None:
        self.stem = "01-container"
        self.source = self.source.rename(self.root / f"diagrams/{self.stem}.flowmap.json")
        self.build["input"] = str(self.source.relative_to(self.root))
        self.diagram["viewId"] = "ordering-container"
        self.assertEqual([], self.check().errors)

    def test_exact_dotted_canonical_id_wins_over_normalized_alias(self) -> None:
        self.stem = "ordering.context"
        self.source = self.source.rename(self.root / f"diagrams/{self.stem}.flowmap.json")
        self.build["input"] = str(self.source.relative_to(self.root))
        self.diagram["viewId"] = "ordering.context"
        (self.root / "model").mkdir()
        (self.root / "model/architecture-model.json").write_text(json.dumps({
            "views": [{"id": "ordering.context"}, {"id": "ordering-context"}],
        }), encoding="utf-8")
        self.assertEqual([], self.check().errors)

    def test_dotted_detail_source_cannot_be_attributed_to_context(self) -> None:
        self.stem = "ordering-context.detail"
        self.source = self.source.rename(self.root / f"diagrams/{self.stem}.flowmap.json")
        self.build["input"] = str(self.source.relative_to(self.root))
        (self.root / "model").mkdir()
        (self.root / "model/architecture-model.json").write_text(json.dumps({
            "views": [{"id": "ordering-context"}, {"id": "ordering-context-detail"}],
        }), encoding="utf-8")
        self.diagram["viewId"] = "ordering-context-detail"
        self.assertEqual([], self.check().errors)
        self.diagram["viewId"] = "ordering-context"
        self.assert_rejected("RCP-007")

    @unittest.skipUnless(shutil.which("node"), "Node required for bundled renderer")
    def test_real_flowmap_producer_control_and_html_print_rejection(self) -> None:
        shutil.copyfile(ROOT / "examples/receipt-flowmap/diagrams/context.flowmap.json", self.source)
        result = subprocess.run([
            sys.executable, str(ROOT / "scripts/build_repo_flowmap.py"),
            "--root", str(self.root), "--input", "diagrams/context.flowmap.json",
            "--output", "diagrams/context.flowmap.html",
        ], capture_output=True, text=True)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.validate = json.loads((self.root / "qa/repo-flowmap-validate-context.json").read_text())
        self.build = json.loads((self.root / "qa/repo-flowmap-build-context.json").read_text())
        self.diagram["assetPath"] = "diagrams/context.flowmap.html"
        self.assertEqual([], self.check().errors)
        self.diagram["printAssetPath"] = "diagrams/context.flowmap.html"
        self.assert_rejected("RCP-007", "printAssetPath")
        self.diagram.pop("printAssetPath")
        self.validate["specification"]["sha256"] = "0" * 64
        self.assert_rejected("RCP-009", "validate-context.json")


if __name__ == "__main__":
    unittest.main()
