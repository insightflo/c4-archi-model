#!/usr/bin/env python3
"""Extract a standalone, sanitized, self-scoped SVG from a delivered archify HTML artifact.

The c4-archi-model single HTML report embeds static SVG per view. An archify
artifact is an interactive HTML whose inline diagram SVG is styled by page CSS
(theme custom properties live on ``<html data-theme data-preset>``, the rest on
classes). This script builds a standalone SVG that is safe to inline:

1. Locate the single ``<svg>...</svg>`` block (archify guarantees one).
2. Reject unsafe content: ``<script>``, ``foreignObject``, external
   ``http(s)://`` references in the SVG or artifact CSS.
3. Filter CSS to rules that can affect the SVG; drop page-level selectors
   (``html``, ``body``, ``:root``, viewer UI classes like toolbar/cards).
4. Scope every surviving selector under a unique root id
   (``#archify-svg-<n>``) so the embedded ``<style>`` cannot restyle the host
   report document or sibling SVGs. Copy the artifact theme attribute onto the
   SVG root so scoped theme custom properties still resolve.
5. Drop ``@keyframes`` and ``animation`` declarations (static embedding)
   unless ``--keep-animation`` is given.

The output is a derived static embedding view; the delivered HTML stays the
interactive rendering ground truth. Receipt JSON reports kept/dropped rule
counts, SHA-256, scope id, theme, and hygiene status.

Standard library only. Exit codes: 0 success, 1 validation failure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

SVG_TAG_RE = re.compile(r"<svg\b[^>]*>", re.IGNORECASE)
SVG_BLOCK_RE = re.compile(r"<svg\b.*?</svg>", re.IGNORECASE | re.DOTALL)
STYLE_BLOCK_RE = re.compile(r"<style\b[^>]*>(.*?)</style>", re.IGNORECASE | re.DOTALL)
HTML_TAG_RE = re.compile(r"<html\b[^>]*>", re.IGNORECASE)
SCRIPT_RE = re.compile(r"<\s*script\b", re.IGNORECASE)
FOREIGN_OBJECT_RE = re.compile(r"<\s*foreignObject\b", re.IGNORECASE)
EXTERNAL_REF_RE = re.compile(r'(?:href|xlink:href|src)\s*=\s*["\']https?://', re.IGNORECASE)
EXTERNAL_URL_RE = re.compile(r"https?://(?!www\.w3\.org)")
ID_ATTR_RE = re.compile(r'\bid="([^"]+)"')

SVG_ELEMENT_NAMES = {
    "svg", "g", "defs", "marker", "style", "rect", "circle", "ellipse", "line",
    "polyline", "polygon", "path", "text", "tspan", "title", "desc", "use",
    "image", "clipPath", "linearGradient", "radialGradient", "stop", "filter",
    "feGaussianBlur", "feOffset", "feMerge", "feMergeNode", "pattern", "mask",
    "tref", "textPath",
}
PAGE_SELECTOR_TOKEN_RE = re.compile(r"(^|[>\s,+~])(html|body|:root)(?=[\s,+~:\[.#{]|$)")


def _fail(receipt_path: Path | None, code: str, message: str) -> int:
    print(f"[FAIL] {code}: {message}", file=sys.stderr)
    if receipt_path:
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps({"ok": False, "code": code, "message": message},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return 1


def strip_css_comments(css: str) -> str:
    return re.sub(r"/\*.*?\*/", "", css, flags=re.DOTALL)


def split_selector_list(selector: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    buf = ""
    for ch in selector:
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        parts.append(buf)
    return [p.strip() for p in parts if p.strip()]


def tokenize_selector(sel: str) -> list[tuple[str, str]]:
    """Tokenize into ('compound'|'comb', text) at bracket depth 0."""
    tokens: list[tuple[str, str]] = []
    buf = ""
    depth = 0
    i = 0
    while i < len(sel):
        ch = sel[i]
        if ch in "([":
            depth += 1
        elif ch in ")]":
            depth -= 1
        if depth == 0 and ch in ">+~":
            if buf.strip():
                tokens.append(("compound", buf.strip()))
                buf = ""
            tokens.append(("comb", ch))
            i += 1
            continue
        if depth == 0 and ch.isspace():
            j = i
            while j < len(sel) and sel[j].isspace():
                j += 1
            if j < len(sel) and sel[j] not in ">+~,":
                if buf.strip():
                    tokens.append(("compound", buf.strip()))
                    buf = ""
                tokens.append(("comb", " "))
            i = j
            continue
        buf += ch
        i += 1
    if buf.strip():
        tokens.append(("compound", buf.strip()))
    return tokens


def scope_selector(sel: str, scope_id: str) -> str | None:
    """Rewrite one selector so it only matches inside #scope_id.

    First compound resolution:
    - ``svg[...]/:pseudo`` or bare ``svg``   -> ``#id`` + trailing parts
    - attribute/pseudo-only ``[data-x]``     -> ``#id[data-x]``
    - ``*``                                   -> ``#id *``
    - anything else (class/element)           -> ``#id <original>``
    Returns None when the shape is not safely rewritable.
    """
    tokens = tokenize_selector(sel)
    if not tokens or tokens[0][0] != "compound" or not tokens[0][1]:
        return None
    compound = tokens[0][1]
    rest = ""
    m = re.match(r"^svg(?![\w-])(.*)$", compound, re.DOTALL)
    if m:
        rest = m.group(1)
    elif compound == "*":
        rest = ""
    elif compound.startswith(("[", ":")):
        rest = compound
    else:
        rest = None

    if rest is None:
        head = f"#{scope_id} {compound}"
    elif rest == "":
        head = f"#{scope_id}"
    else:
        if not rest.startswith(("[", ":")):
            return None
        head = f"#{scope_id}{rest}"

    out = [head]
    for kind, val in tokens[1:]:
        if kind == "comb":
            out.append(f" {val} ")
        else:
            out.append(val)
    return "".join(out)


def selector_is_safe(selector: str, svg_classes: set[str], svg_ids: set[str]) -> bool:
    sel = selector.strip()
    if not sel:
        return False
    if PAGE_SELECTOR_TOKEN_RE.search(" " + sel + " "):
        return False
    for class_name in re.findall(r"\.([A-Za-z_][\w-]*)", sel):
        if class_name not in svg_classes:
            return False
    for ident in re.findall(r"#([A-Za-z_][\w-]*)", sel):
        if ident not in svg_ids:
            return False
    parts = re.split(r"[>\s,+~]+", sel)
    for part in parts:
        part = part.strip()
        if not part or part.startswith((".", "#", "[", ":", "*")):
            continue
        base = re.match(r"^([A-Za-z][\w-]*)", part)
        if base and base.group(1) not in SVG_ELEMENT_NAMES:
            return False
    return True


def split_rules(css: str) -> list[tuple[str, str]]:
    """Split CSS into (selector_text, body) pairs at brace depth 1."""
    rules: list[tuple[str, str]] = []
    depth = 0
    buf = ""
    for ch in css:
        if ch == "{":
            depth += 1
            buf += ch
        elif ch == "}":
            depth -= 1
            buf += ch
            if depth == 0:
                m = re.match(r"^([^{}]*)\{(.*)\}$", buf.strip(), re.DOTALL)
                if m and m.group(1).strip():
                    rules.append((m.group(1).strip(), m.group(2)))
                buf = ""
        elif depth > 0 or not ch.isspace():
            buf += ch
        elif buf:
            buf += ch
    return rules


def filter_css(
    css: str,
    svg_classes: set[str],
    svg_ids: set[str],
    scope_id: str,
    drop_keyframes: bool,
) -> tuple[str, dict[str, int]]:
    css = strip_css_comments(css)
    stats = {
        "rulesTotal": 0,
        "rulesKept": 0,
        "rulesDroppedPage": 0,
        "rulesDroppedForeign": 0,
        "rulesDroppedUnscopable": 0,
        "keyframesDropped": 0,
        "fontFaceDropped": 0,
    }

    def walk(css_text: str) -> list[str]:
        out: list[str] = []
        for selector, body in split_rules(css_text):
            if selector.startswith("@"):
                at_name = selector[1:].split("(", 1)[0].split(" ", 1)[0].strip()
                if at_name == "keyframes" and drop_keyframes:
                    stats["keyframesDropped"] += 1
                    continue
                if at_name == "font-face":
                    stats["fontFaceDropped"] += 1
                    continue
                if at_name in ("media", "supports"):
                    inner = walk(body)
                    if inner:
                        out.append(f"{selector}{{{ ''.join(inner) }}}")
                    continue
                stats["rulesDroppedPage"] += 1  # import/charset/namespace/unknown
                continue
            stats["rulesTotal"] += 1
            selectors = split_selector_list(selector)
            kept: list[str] = []
            unscopable = 0
            for s in selectors:
                if not selector_is_safe(s, svg_classes, svg_ids):
                    if PAGE_SELECTOR_TOKEN_RE.search(" " + s + " "):
                        stats["rulesDroppedPage"] += 1
                    else:
                        stats["rulesDroppedForeign"] += 1
                    continue
                scoped = scope_selector(s, scope_id)
                if scoped is None:
                    unscopable += 1
                    continue
                kept.append(scoped)
            if not kept:
                if unscopable and all(
                    selector_is_safe(s, svg_classes, svg_ids) for s in selectors
                ):
                    stats["rulesDroppedUnscopable"] += 1
                continue
            body_text = body.strip()
            if drop_keyframes:
                body_text = re.sub(r"animation(?:-name)?\s*:[^;}]*;?", "", body_text)
            if not body_text.strip():
                continue
            out.append(f"{','.join(kept)}{{{body_text}}}")
            stats["rulesKept"] += 1
        return out

    return "\n".join(walk(css)), stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--html", type=Path, required=True,
                        help="delivered archify HTML artifact")
    parser.add_argument("--output", type=Path, required=True,
                        help="standalone SVG output path")
    parser.add_argument("--scope-id",
                        help="unique root id for CSS scoping (default: archify-svg-<output stem>)")
    parser.add_argument("--theme", choices=["dark", "light"],
                        help="theme attribute to place on the SVG root "
                             "(default: read from the artifact <html data-theme>)")
    parser.add_argument("--json", type=Path, help="receipt JSON output path")
    parser.add_argument("--keep-animation", action="store_true",
                        help="keep @keyframes and animation declarations")
    args = parser.parse_args()

    receipt_path = args.json
    html_path: Path = args.html
    out_path: Path = args.output

    if not html_path.is_file():
        return _fail(receipt_path, "ARCHIFY-SVG-001", f"artifact not found: {html_path}")
    html = html_path.read_text(encoding="utf-8")

    blocks = SVG_BLOCK_RE.findall(html)
    if len(blocks) != 1:
        return _fail(receipt_path, "ARCHIFY-SVG-002",
                     f"expected exactly 1 <svg> block, found {len(blocks)}")
    svg_block = blocks[0]

    if SCRIPT_RE.search(svg_block):
        return _fail(receipt_path, "ARCHIFY-SVG-003", "svg contains <script>")
    if FOREIGN_OBJECT_RE.search(svg_block):
        return _fail(receipt_path, "ARCHIFY-SVG-004", "svg contains foreignObject")
    if EXTERNAL_REF_RE.search(svg_block):
        return _fail(receipt_path, "ARCHIFY-SVG-005",
                     "svg contains external http(s) reference")

    html_tag = HTML_TAG_RE.search(html)
    theme = args.theme
    if theme is None:
        m = re.search(r'data-theme="([^"]+)"', html_tag.group(0)) if html_tag else None
        theme = m.group(1) if m else "dark"
    if theme not in ("dark", "light"):
        return _fail(receipt_path, "ARCHIFY-SVG-008", f"unsupported theme: {theme}")

    scope_id = args.scope_id or (
        "archify-svg-" + re.sub(r"[^a-z0-9-]+", "-", out_path.stem.lower()).strip("-")
    )
    if not re.fullmatch(r"[A-Za-z][\w-]*", scope_id):
        return _fail(receipt_path, "ARCHIFY-SVG-009",
                     f"invalid scope id: {scope_id}")

    svg_classes = set()
    for value in re.findall(r'class="([^"]*)"', svg_block):
        svg_classes.update(v for v in value.split() if v)
    svg_ids = set(ID_ATTR_RE.findall(svg_block))
    if scope_id in svg_ids:
        return _fail(receipt_path, "ARCHIFY-SVG-010",
                     f"scope id already used inside svg: {scope_id}")

    css_text = "\n".join(
        strip_css_comments(c) for c in STYLE_BLOCK_RE.findall(html)
    )
    if EXTERNAL_URL_RE.search(css_text):
        return _fail(receipt_path, "ARCHIFY-SVG-006",
                     "artifact css contains external http(s) url (only data: allowed)")

    filtered_css, stats = filter_css(
        css_text, svg_classes, svg_ids, scope_id, drop_keyframes=not args.keep_animation
    )
    if not filtered_css:
        return _fail(receipt_path, "ARCHIFY-SVG-007",
                     "no safe css rules survived filtering; cannot build standalone svg")

    tag_m = SVG_TAG_RE.search(svg_block)
    tag = tag_m.group(0)
    inner = svg_block[tag_m.end():]
    if "xmlns=" not in tag:
        tag = tag.replace("<svg", '<svg xmlns="http://www.w3.org/2000/svg"', 1)
    if "xlink:" in inner and "xmlns:xlink=" not in tag:
        tag = tag.replace("<svg", '<svg xmlns:xlink="http://www.w3.org/1999/xlink"', 1)
    if ID_ATTR_RE.fullmatch(tag) is None and f'id="{scope_id}"' not in tag:
        tag = tag.replace("<svg", f'<svg id="{scope_id}"', 1)
    if 'data-theme=' not in tag:
        tag = tag.replace("<svg", f'<svg data-theme="{theme}"', 1)

    standalone = f"{tag}<style>{filtered_css}</style>{inner}"

    if SCRIPT_RE.search(standalone) or FOREIGN_OBJECT_RE.search(standalone):
        return _fail(receipt_path, "ARCHIFY-SVG-003",
                     "standalone svg contains script or foreignObject")
    if EXTERNAL_REF_RE.search(standalone):
        return _fail(receipt_path, "ARCHIFY-SVG-005",
                     "standalone svg contains external http(s) reference")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(standalone, encoding="utf-8")

    receipt = {
        "ok": True,
        "source": str(html_path),
        "output": str(out_path),
        "scopeId": scope_id,
        "theme": theme,
        "svgSha256": hashlib.sha256(standalone.encode("utf-8")).hexdigest(),
        "svgBytes": len(standalone.encode("utf-8")),
        "hygiene": {
            "script": False,
            "foreignObject": False,
            "externalRefs": False,
        },
        "cssFilter": stats,
        "keepAnimation": bool(args.keep_animation),
        "note": "derived static embedding view; delivered HTML remains the interactive ground truth",
    }
    if receipt_path:
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    print(
        f"[PASS] standalone svg written: {out_path} "
        f"({receipt['svgBytes']} bytes, kept {stats['rulesKept']}/{stats['rulesTotal']} css rules, "
        f"scope #{scope_id}, theme {theme})"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
