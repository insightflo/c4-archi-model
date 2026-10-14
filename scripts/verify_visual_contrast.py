#!/usr/bin/env python3
"""D4: 텍스트·화살표·포커스 표시의 실제 배경 밝기 대비 검사.

두 오프라인 템플릿(렌더러 repo-flowmap/template.html의 밝음·어두움 테마,
보고서 html-report-template.html)에서 CSS 색 변수를 파싱해 역할별 실제
전경/배경 조합의 WCAG 2.x 상대 휘도 대비를 계산한다.

- 텍스트 4.5:1, 큰 텍스트(18pt+ 또는 14pt 굵게) 3.0:1,
  의미 있는 비텍스트(관계선·테두리·포커스 표시) 3.0:1, 순수 장식은 기준 없음.
- 반투명 색(rgba, fill-opacity)은 지정 배경 위에 합성한 뒤 계산한다.
- 같은 색이 글자에도 쓰이면 글자 기준(4.5)을 적용한다.

기준 미달이지만 이중 표시(배경색·텍스트·무늬 등 겹침 표시)로 기능이 유지되는
비텍스트 표시는 note와 함께 [LIMIT]로 기록하고 visual-budgets.md의 한계
목록과 대응시킨다. note 없는 미달, note 없는 역할 정의 오류는 FAIL이다.

사용:
    python3 scripts/verify_visual_contrast.py [--root DIR] [--profile NAME] [--output-json PATH]

--profile을 주면 보고서 템플릿에 정의된 이름 있는 공유 시각 프로필(D5)의 역할 값을
템플릿 기본값 위에 덮어쓴 상태로 같은 63역할을 검사한다(빠진 역할은 기본값 보충,
템플릿에 없는 역할은 경고 후 무시). 인자가 없으면 기존대로 현재 템플릿 값을 검사한다.

Exit: 0 미달 없음(한계 기록만 허용), 1 미달 또는 정의 오류.
"""
from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from c4_validation import Check, ValidationReport, print_report

SKILL_ROOT = SCRIPT_DIR.parent
RENDERER = "assets/repo-flowmap/template.html"
REPORT = "assets/html-report-template.html"

THRESHOLDS = {"text": 4.5, "text-large": 3.0, "nontext": 3.0, "decorative": None}

PROFILE_SCRIPT_RE = re.compile(
    r'<script[^>]*id="visual-profiles"[^>]*>(.*?)</script>', re.S)

# ── 색 파싱 · WCAG 공식 ─────────────────────────────────────────────

HEX_RE = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
RGB_RE = re.compile(r"rgba?\(\s*(\d{1,3})\s*,\s*(\d{1,3})\s*,\s*(\d{1,3})\s*(?:,\s*(\d*\.?\d+)\s*)?\)", re.IGNORECASE)
VAR_RE = re.compile(r"^var\(\s*(--[\w-]+)\s*(?:,\s*([^)]+?)\s*)?\)$")


class ColorError(ValueError):
    """측정할 수 없는 색 값."""


def parse_color(value: str) -> tuple[tuple[float, float, float], float]:
    """색 값 하나를 ((r,g,b), alpha)로 반환. hex·rgb()·rgba() 지원."""
    text = value.strip()
    hex_match = HEX_RE.search(text)
    rgb_match = RGB_RE.search(text)
    if hex_match and (not rgb_match or hex_match.start() < rgb_match.start()):
        digits = hex_match.group(1)
        if len(digits) == 3:
            digits = "".join(c * 2 for c in digits)
        return tuple(float(int(digits[i:i + 2], 16)) for i in (0, 2, 4)), 1.0  # type: ignore[return-value]
    if rgb_match:
        channels = [float(rgb_match.group(i)) for i in (1, 2, 3)]
        if any(c > 255 for c in channels):
            raise ColorError(f"채널 범위 초과: {text!r}")
        alpha = float(rgb_match.group(4)) if rgb_match.group(4) is not None else 1.0
        if not 0.0 <= alpha <= 1.0:
            raise ColorError(f"알파 범위 초과: {text!r}")
        return tuple(channels), alpha  # type: ignore[return-value]
    raise ColorError(f"측정 가능한 색이 아님: {text!r}")


def _channel(value: float) -> float:
    fraction = value / 255
    if fraction <= 0.04045:
        return fraction / 12.92
    return ((fraction + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: tuple[float, float, float]) -> float:
    red, green, blue = (_channel(c) for c in rgb)
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(first: tuple[float, float, float], second: tuple[float, float, float]) -> float:
    one, two = relative_luminance(first), relative_luminance(second)
    lighter, darker = max(one, two), min(one, two)
    return (lighter + 0.05) / (darker + 0.05)


def composite(rgb, alpha: float, background) -> tuple[float, float, float]:
    """반투명 전경을 불투명 배경 위에 합성한다(반올림하지 않는다)."""
    return tuple(rgb[i] * alpha + background[i] * (1 - alpha) for i in range(3))  # type: ignore[return-value]


# ── CSS 변수 파싱 · 해석 ───────────────────────────────────────────

BLOCK_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")


def parse_css_variables(text: str) -> dict[str, dict[str, str]]:
    """:root(밝음)과 어두움 오버라이드 블록을 찾아 테마별 변수 사전을 반환.

    - light: 첫 `:root{...}`
    - dark: `:root[data-theme="dark"]{...}` 와 prefers-color-scheme 안의
      `:root:not([data-theme="light"]){...}`. 두 블록이 모두 있으면 값이
      같아야 한다(드리프트 방지).
    """
    scopes: dict[str, dict[str, str]] = {}
    duplicates: dict[str, dict[str, str]] = {}
    for selector, body in BLOCK_RE.findall(text):
        sel = " ".join(selector.split())
        name = None
        if sel.endswith(":root"):
            name = "light"
        elif "[data-theme=\"dark\"]" in sel:
            name = "dark"
        elif ":not([data-theme=\"light\"])" in sel:
            name = "dark-media"
        if not name:
            continue
        variables = {}
        for declaration in body.split(";"):
            if ":" not in declaration:
                continue
            key, _, value = declaration.partition(":")
            key = key.strip()
            if key.startswith("--"):
                variables[key] = value.strip()
        if not variables:
            continue
        if name in scopes or name in duplicates:
            duplicates.setdefault(name, scopes.get(name, {})).update(variables)
        scopes[name] = variables
    if "dark-media" in scopes:
        media, attr = scopes.pop("dark-media"), scopes.get("dark", {})
        if attr and attr != media:
            raise ColorError("어두움 테마 블록(prefers-color-scheme 와 data-theme) 값이 서로 다릅니다")
        scopes["dark"] = media
    for name, merged in duplicates.items():
        if merged != scopes.get(name):
            raise ColorError(f"{name} 블록이 여러 번 정의되었고 값이 다릅니다")
    if "light" not in scopes:
        raise ColorError(":root 정의를 찾을 수 없습니다")
    # CSS 캐스케이드: 어두움 블록은 밝음 정의 위의 오버라이드다. 병합해 완전한 테마를 만든다.
    if "dark" in scopes:
        scopes["dark"] = {**scopes["light"], **scopes["dark"]}
    return scopes


def resolve_var(name: str, scope: dict[str, str], depth: int = 0) -> str:
    """var() 참조 체인을 따라 최종 색 값을 반환한다(대체값 지원)."""
    if depth > 16:
        raise ColorError(f"변수 순환 참조: {name}")
    if name not in scope:
        raise ColorError(f"정의되지 않은 변수: {name}")
    value = scope[name].strip()
    match = VAR_RE.match(value)
    if not match:
        return value
    inner, fallback = match.group(1), match.group(2)
    try:
        return resolve_var(inner, scope, depth + 1)
    except ColorError:
        if fallback is not None:
            return fallback.strip()
        raise


# ── 역할 정의(선언적 테이블) ────────────────────────────────────────
# fg/bg 사양: ("var", 이름) | ("lit", 색값) | ("over", 전경, 배경, 추가알파)
# 추가알파는 CSS 의 fill-opacity/opacity 처럼 색값 밖에서 곱해지는 불투명도다.

RENDERER_ROLES: list["Role"] = []
REPORT_ROLES: list["Role"] = []


@dataclass(frozen=True)
class Role:
    rid: str
    desc: str
    fg: tuple
    bg: tuple
    kind: str
    themes: tuple[str, ...] = ("light", "dark")
    note: str | None = None


def _renderer(rid, desc, fg, bg, kind, themes=("light", "dark"), note=None):
    RENDERER_ROLES.append(Role(rid, desc, fg, bg, kind, tuple(themes), note))


def _report(rid, desc, fg, bg, kind, note=None):
    REPORT_ROLES.append(Role(rid, desc, fg, bg, kind, ("light",), note))


V = lambda name: ("var", name)
L = lambda value: ("lit", value)
OVER = lambda fg, bg, alpha=1.0: ("over", fg, bg, alpha)

# 렌더러 repo-flowmap — 읽는 대상(텍스트, 4.5)
_renderer("RND-101", "본문 텍스트(ink) · 캔버스 위", V("--color-ink"), V("--color-canvas"), "text")
_renderer("RND-102", "본문 텍스트(ink) · 패널 위(사이드바·C4 카드)", V("--color-ink"), V("--color-paper"), "text")
_renderer("RND-103", "노드 라벨(ink) · 노드 배경 위(워크플로)", V("--color-ink"), V("--color-node"), "text")
_renderer("RND-104", "보조 텍스트(ink-2) · 패널 위", V("--color-ink-2"), V("--color-paper"), "text")
_renderer("RND-105", "식별자·기술(ink-3, 11–12px) · 패널 위", V("--color-ink-3"), V("--color-paper"), "text")
_renderer("RND-106", "노드 설명(ink-3, 10px) · 노드 배경 위", V("--color-ink-3"), V("--color-node"), "text")
_renderer("RND-107", "종류·강조 텍스트(accent) · 패널 위", V("--color-accent"), V("--color-paper"), "text")
_renderer("RND-108", "눌린 버튼 텍스트(accent-ink) · accent 위", V("--color-accent-ink"), V("--color-accent"), "text")
_renderer("RND-109", "상태 라벨(warn-text, 9px) · 경고 배경 위", V("--color-warn-text"), V("--color-warn-bg"), "text")
_renderer("RND-110", "미확정 텍스트(uncertain, 12px 굵게) · 패널 위", V("--color-uncertain"), V("--color-paper"), "text")
_renderer("RND-111", "경계 제목(ink) · 경계 배경 위(패널-2 55% 합성)",
          V("--color-ink"), OVER(V("--color-paper-2"), V("--color-canvas"), 0.55), "text")
_renderer("RND-112", "배지 텍스트(edge-on, 10px) · 패널 위", V("--color-edge-on"), V("--color-paper"), "text")
_renderer("RND-113", "내부 단계 번호(edge-self, 9px) · 패널 위", V("--color-edge-self"), V("--color-paper"), "text")
_renderer("RND-114", "상태 태그(stop) · 패널 위", V("--color-stop"), V("--color-paper"), "text")
_renderer("RND-115", "STALE 배지 텍스트(흰색) · 배지 배경 위", L("#ffffff"), L("#8a6d3b"), "text")
_renderer("RND-116", "STALE 라벨(warn-text) · STALE 틴트(10% 합성) 위",
          V("--color-warn-text"), OVER(L("#8a6d3b"), V("--color-paper"), 0.10), "text")

# 렌더러 — 의미 있는 비텍스트(선·테두리·포커스, 3.0)
_renderer("RND-201", "관계선 기본색(edge) · 캔버스 위(화살촉 폴백·범례)", V("--color-edge"), V("--color-canvas"), "nontext")
_renderer("RND-202", "정방향 관계선(edge-on) · 캔버스 위", V("--color-edge-on"), V("--color-canvas"), "nontext")
_renderer("RND-203", "역방향 관계선(edge-back) · 캔버스 위", V("--color-edge-back"), V("--color-canvas"), "nontext")
_renderer("RND-204", "자기호출 관계선(edge-self) · 캔버스 위", V("--color-edge-self"), V("--color-canvas"), "nontext")
_renderer("RND-205", "강조 테두리(accent) · 캔버스 위", V("--color-accent"), V("--color-canvas"), "nontext")
_renderer("RND-206", "포커스 표시(focus) · 캔버스 위", V("--color-focus"), V("--color-canvas"), "nontext")
_renderer("RND-207", "포커스 표시(focus) · 패널 위", V("--color-focus"), V("--color-paper"), "nontext")
_renderer("RND-208", "정지 표시(stop) · 캔버스 위", V("--color-stop"), V("--color-canvas"), "nontext")
_renderer("RND-209", "미확정 경계선(uncertain) · 캔버스 위", V("--color-uncertain"), V("--color-canvas"), "nontext")
_renderer("RND-210", "선택 플로우 버튼 테두리(accent-line) · 강조 배경 위", V("--color-accent-line"), V("--color-accent-soft"), "nontext",
          note="선택 상태가 배경색(accent-soft)과 텍스트 색(accent)으로 이중 표시됨. visual-budgets.md 한계 목록 참조.")
_renderer("RND-211", "조건 분기 선(warn-line) · 캔버스 위", V("--color-warn-line"), V("--color-canvas"), "nontext",
          note="조건 상태는 범례·사이드바 상태 태그 텍스트·점선 무늬와 함께 이중 표시됨. visual-budgets.md 한계 목록 참조.")
_renderer("RND-212", "유령 관계선(edge 45% 합성) · 캔버스 위", OVER(V("--color-edge"), V("--color-canvas"), 0.45), V("--color-canvas"), "nontext",
          note="도달 불가 상태의 의도적 흔적. --stop 실선 구간(62%)+상태 칩+범례로 이중 표시됨. visual-budgets.md 한계 목록 참조.")

# 렌더러 — 장식(기준 없음, 참고용 수치만 기록)
_renderer("RND-301", "구분선(rule) · 캔버스 위", V("--color-rule"), V("--color-canvas"), "decorative")
_renderer("RND-302", "주 격자(grid-major 합성) · 캔버스 위", OVER(V("--color-grid-major"), V("--color-canvas")), V("--color-canvas"), "decorative")
_renderer("RND-303", "상태 칩 테두리(warn-line) · 경고 배경 위", V("--color-warn-line"), V("--color-warn-bg"), "decorative")

# 보고서 템플릿 — 텍스트(4.5), 밝은 테마만
_report("RPT-101", "본문(ink) · 캔버스 위", V("--ink"), V("--canvas"), "text")
_report("RPT-102", "본문(ink) · 카드(#fff) 위", V("--ink"), L("#ffffff"), "text")
_report("RPT-103", "보조 문단(muted) · 캔버스 위", V("--muted"), V("--canvas"), "text")
_report("RPT-104", "보조 문단(muted) · 카드 위", V("--muted"), L("#ffffff"), "text")
_report("RPT-105", "캡션·라벨(soft) · 카드 위", V("--soft"), L("#ffffff"), "text")
_report("RPT-106", "캡션·라벨(soft) · 캔버스 위(내비 그룹 라벨 포함)", V("--soft"), V("--canvas"), "text")
_report("RPT-107", "미실행 라벨(soft) · 미실행 배경(#eef1f5) 위", V("--soft"), L("#eef1f5"), "text")
_report("RPT-108", "링크(blue) · 카드 위", V("--blue"), L("#ffffff"), "text")
_report("RPT-109", "링크(blue) · 캔버스 위", V("--blue"), V("--canvas"), "text")
_report("RPT-110", "링크·선택 텍스트(blue) · 파란 배경 위", V("--blue"), V("--blue-bg"), "text")
_report("RPT-111", "탭 라벨(muted) · 탭 배경(#e9edf3) 위", V("--muted"), L("#e9edf3"), "text")
_report("RPT-112", "흰 텍스트 · 남색(navy) 위(브랜드·기본 버튼·단계 번호)", L("#ffffff"), V("--navy"), "text")
_report("RPT-113", "코드 박스 텍스트 · 코드 배경 위", L("#d8e0ef"), L("#101827"), "text")
_report("RPT-114", "상태 배지(green) · 초록 배경 위(9px)", V("--green"), V("--green-bg"), "text")
_report("RPT-115", "상태 배지(gold) · 금색 배경 위(9px)", V("--gold"), V("--gold-bg"), "text")
_report("RPT-116", "상태 배지(red) · 빨강 배경 위(9px)", V("--red"), V("--red-bg"), "text")
_report("RPT-117", "대상 라벨(violet) · 보라 배경 위(9px)", V("--violet"), V("--violet-bg"), "text")
_report("RPT-118", "콜아웃 info 라벨 · 비유 배경 위", L("#3a6280"), V("--analogy-bg"), "text")
_report("RPT-119", "콜아웃 warn 라벨(gold) · 터미널 배경 위", V("--gold"), V("--term-bg"), "text")
_report("RPT-120", "콜아웃 danger 라벨(accent) · 빨강 배경 위", V("--accent"), V("--red-bg"), "text")
_report("RPT-121", "콜아웃 good 라벨 · 초록 배경 위", L("#2a7d5a"), V("--green-bg"), "text")
_report("RPT-122", "주의 박스 본문 · 금색 배경 위", L("#75500b"), V("--gold-bg"), "text")
_report("RPT-123", "비유 박스 본문 · 보라 배경 위", L("#63488f"), V("--violet-bg"), "text")
_report("RPT-124", "무결성 경고 본문 · 빨강 배경 위", L("#7d3c33"), V("--red-bg"), "text")
_report("RPT-125", "요소 설명 · 카드 위", L("#3f4b60"), L("#ffffff"), "text")
_report("RPT-126", "표 본문 · 카드 위", L("#48546a"), L("#ffffff"), "text")
_report("RPT-127", "킥커(accent) · 캔버스 위", V("--accent"), V("--canvas"), "text")
_report("RPT-128", "강조 용어(accent) · 강조 배경(accent-soft) 위", V("--accent"), V("--accent-soft"), "text")
_report("RPT-129", "섹션 번호(흰색) · 섹션 심볼(accent) 위", L("#ffffff"), V("--accent"), "text")
_report("RPT-201", "포커스 아웃라인(blue) · 캔버스 위", V("--blue"), V("--canvas"), "nontext")
_report("RPT-301", "표 테두리(line) · 카드 위", V("--line"), L("#ffffff"), "decorative")
_report("RPT-302", "하이라이트(hl-yellow) · 카드 위", L("#ffe9a3"), L("#ffffff"), "decorative")


# ── 평가 ───────────────────────────────────────────────────────

def parse_visual_profiles(text: str) -> dict[str, dict]:
    """보고서 템플릿에 포함된 공유 시각 프로필 정의(JSON)를 파싱한다(D5).

    프로필 구조: {이름: {label, report: {역할: 값}, renderer: {light: {...}, dark: {...}}}}.
    역할 ID는 두 템플릿의 기존 CSS 변수명 그대로다(외부 형식 없음).
    """
    match = PROFILE_SCRIPT_RE.search(text)
    if not match:
        raise ColorError('보고서 템플릿에 시각 프로필 정의(<script id="visual-profiles">)가 없습니다')
    profiles = json.loads(match.group(1))
    if not isinstance(profiles, dict) or not profiles:
        raise ColorError("시각 프로필 정의가 비어 있거나 객체가 아닙니다")
    return profiles


def _string_map(value, where: str) -> dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ColorError(f"프로필 {where} 정의가 객체가 아닙니다")
    return {str(key): str(item) for key, item in value.items()}


def profile_overrides(entry: dict, relative: str) -> dict[str, dict[str, str]]:
    """프로필 항목에서 파일(RENDERER/REPORT)별 테마→역할 맵을 만든다.

    빠진 테마·역할은 아예 넣지 않는다 — 적용 시점에 템플릿 기본값이 그대로 남는다
    (오래된/불완전 프로필의 빠진 역할은 기본으로 보충, 원본을 덮어쓰지 않는 원칙).
    """
    if relative == RENDERER:
        renderer = entry.get("renderer") or {}
        return {theme: _string_map(renderer.get(theme), f"renderer.{theme}")
                for theme in ("light", "dark") if (renderer.get(theme) or {})}
    report_map = _string_map(entry.get("report"), "report")
    return {"light": report_map} if report_map else {}


def merge_profile(scopes: dict[str, dict[str, str]], overrides: dict[str, dict[str, str]],
                  relative: str, report: ValidationReport) -> dict[str, dict[str, str]]:
    """테마 스코프 위에 프로필 역할 값을 덮어쓴다. 템플릿에 없는 역할은 경고하고 무시한다."""
    merged = {theme: dict(scope) for theme, scope in scopes.items()}
    for theme, values in overrides.items():
        if theme not in merged:
            continue
        for key, value in values.items():
            if key not in merged[theme]:
                report.warning("CNT-PROFILE-ROLE", f"{relative}#{key}",
                               f"프로필이 {relative} {theme} 테마에 정의되지 않은 역할을 지정했다(무시됨): {key}")
                continue
            merged[theme][key] = value
    return merged


def opaque(spec: tuple, scope: dict[str, str]) -> tuple[tuple[float, float, float], float]:
    """사양을 (rgb, 알파)로 평가한다. over 사양은 배경 위에 합성해 불투명으로 돌려준다."""
    if spec[0] == "var":
        return parse_color(resolve_var(spec[1], scope))
    if spec[0] == "lit":
        return parse_color(spec[1])
    if spec[0] == "over":
        _, fg, bg, extra_alpha = spec
        fg_rgb, fg_alpha = opaque(fg, scope)
        bg_rgb, bg_alpha = opaque(bg, scope)
        if bg_alpha < 1:
            raise ColorError("over 의 배경이 불투명해야 함")
        alpha = fg_alpha * extra_alpha
        if alpha >= 1:
            return fg_rgb, 1.0
        return composite(fg_rgb, alpha, bg_rgb), 1.0
    raise ColorError(f"알 수 없는 색 사양: {spec!r}")


def evaluate_role(role: Role, scopes: dict[str, dict[str, str]], path: str, report: ValidationReport) -> list[dict]:
    rows: list[dict] = []
    theme_results: list[tuple[str, float, str]] = []
    failure = None
    limit = None
    for theme in role.themes:
        if theme not in scopes:
            report.error("CNT-SCOPE", f"{path}#{role.rid}", f"템플릿에 {theme} 테마 정의가 없어 {role.rid} 검사를 실행할 수 없습니다")
            return rows
        try:
            fg_rgb, fg_alpha = opaque(role.fg, scopes[theme])
            bg_rgb, bg_alpha = opaque(role.bg, scopes[theme])
            if fg_alpha < 1 or bg_alpha < 1:
                raise ColorError("전경/배경이 불투명하게 확정되지 않음(over 사양 필요)")
            ratio = contrast(fg_rgb, bg_rgb)
        except ColorError as error:
            report.error("CNT-PARSE", f"{path}#{role.rid}", f"{theme} 테마 {role.rid} 해석 실패: {error}")
            return rows
        threshold = THRESHOLDS[role.kind]
        if threshold is None:
            status = "DECOR"
        elif ratio >= threshold:
            status = "PASS"
        elif role.note:
            status = "LIMIT"
            limit = (theme, ratio, threshold)
        else:
            status = "FAIL"
            failure = failure or (theme, ratio, threshold)
        theme_results.append((theme, ratio, status))
        rows.append({"id": role.rid, "desc": role.desc, "theme": theme, "kind": role.kind,
                     "ratio": round(ratio, 2), "threshold": threshold, "result": status,
                     "note": role.note if status == "LIMIT" else None})
    threshold = THRESHOLDS[role.kind]
    values = " · ".join(f"{theme} {ratio:.2f}" for theme, ratio, _ in theme_results)
    detail = f"{values} (min {threshold:g})" if threshold is not None else f"{values} (장식·기준 없음)"
    if failure:
        report.fail_check(role.rid, role.desc, detail)
        theme, ratio, threshold = failure
        report.error("CNT-LOW", f"{path}#{role.rid}",
                     f"{role.desc} — {theme} {ratio:.2f}:1 미달 (기준 {threshold:g}:1)")
    elif limit:
        theme, ratio, threshold = limit
        report.checks.append(Check(role.rid, role.desc, "LIMIT", detail))
        report.warning("CNT-LIMIT", f"{path}#{role.rid}",
                       f"{role.desc} — {theme} {ratio:.2f}:1 (기준 {threshold:g}:1) 한계 기록: {role.note}")
    else:
        report.pass_check(role.rid, role.desc, detail)
    return rows


def run(root: Path = SKILL_ROOT, profile: str | None = None) -> tuple[ValidationReport, list[dict]]:
    report = ValidationReport("visual-contrast")
    rows: list[dict] = []
    profiles: dict | None = None
    if profile is not None:
        try:
            profiles = parse_visual_profiles((root / REPORT).read_text(encoding="utf-8", errors="replace"))
        except (OSError, ColorError, json.JSONDecodeError) as error:
            report.error("CNT-PROFILE-FILE", REPORT, f"시각 프로필 정의를 읽을 수 없습니다: {error}")
            return report, rows
        if profile not in profiles:
            report.error("CNT-PROFILE", profile,
                         f"알 수 없는 프로필 이름입니다: {profile!r} (정의됨: {', '.join(profiles)})")
            return report, rows
    for relative, roles in ((RENDERER, RENDERER_ROLES), (REPORT, REPORT_ROLES)):
        path = root / relative
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            scopes = parse_css_variables(text)
        except (OSError, ColorError) as error:
            report.error("CNT-FILE", relative, f"템플릿을 읽거나 테마 변수를 파싱할 수 없습니다: {error}")
            continue
        if profiles is not None:
            try:
                scopes = merge_profile(scopes, profile_overrides(profiles[profile], relative), relative, report)
            except ColorError as error:
                report.error("CNT-PROFILE-FILE", relative, f"프로필 정의가 잘못되었습니다: {error}")
                continue
        for role in roles:
            for row in evaluate_role(role, scopes, relative, report):
                rows.append({"file": relative, **({"profile": profile} if profile else {}), **row})
    return report, rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="텍스트·비텍스트 표시의 실제 배경 대비 검사(WCAG 상대 휘도)")
    parser.add_argument("--root", type=Path, default=SKILL_ROOT, help="스킬 루트 디렉터리")
    parser.add_argument("--profile", help="이름 있는 공유 시각 프로필(보고서 템플릿 정의) 값을 덮어쓴 상태로 검사")
    parser.add_argument("--output-json", type=Path, help="qa 기록용 JSON 출력 경로")
    parser.add_argument("--quiet", action="store_true", help="요약만 출력")
    args = parser.parse_args(argv)
    report, rows = run(args.root, args.profile)
    if not args.quiet:
        print_report(report)
    else:
        print(f"Validation: {report.name} / Result: {report.result} / Errors: {len(report.errors)} / Warnings: {len(report.warnings)}")
    if args.output_json:
        payload = report.to_dict()
        payload["rows"] = rows
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
