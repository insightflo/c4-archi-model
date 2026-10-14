"""A9 chronological event log — shared test instrumentation.

Installs a per-frame recorder via Playwright's add_init_script BEFORE navigation.
Every record carries (wall time, per-document performance time, monotonic base,
sequence, event kind, payload, and a state snapshot). Records from the main frame
and every iframe are merged into one timeline normalized to a shared millisecond
clock (nt = performance.now() + (Date.now() - performance.now())), so ordering
assertions work across frames.

Nothing here touches product code: the wrappers only observe and pass through.
The message-event records ('msg:<type>') are the canonical signal — they fire in
every frame including opaque-origin sandboxed embeds, where a wrapped
window.postMessage or an accessor on window.repoFlowmap is NOT reliably reached
by the parent document (a defineProperty accessor there silently swallows the
page's own assignment, so no property interception is used at all).
"""
from __future__ import annotations

import re

RECORDER_JS = r"""
(() => {
  if (window.__timelineInstalled) return;
  window.__timelineInstalled = true;
  const timeline = window.__timeline = [];
  let seq = 0;
  const REPO_MESSAGE = /^repo-flowmap-/;
  const pick = (message) => {
    const out = {};
    ['type', 'viewId', 'stepIndex', 'requestId', 'step', 'ready', 'action'].forEach(key => {
      if (message && message[key] !== undefined) out[key] = message[key];
    });
    return out;
  };
  const snapshot = () => {
    const out = {};
    try {
      const state = window.repoFlowmap && window.repoFlowmap.state ? window.repoFlowmap.state() : null;
      if (state) { out.step = state.step; out.playing = state.playing; out.stopNotice = state.stopNotice || null; out.camera = state.camera; }
    } catch (err) {}
    try { out.markCount = document.querySelectorAll('g.c4-flow-mark').length; } catch (err) {}
    try {
      const announce = document.querySelector('.flow-step-announce');
      if (announce) out.announce = announce.textContent;
      const progress = document.querySelector('.flow-progress');
      if (progress) out.progress = progress.textContent;
      const guide = document.querySelector('.flow-guide-btn');
      if (guide) out.guidePressed = guide.getAttribute('aria-pressed');
      const selectors = document.querySelectorAll('.flow-step-selector');
      for (let i = 0; i < selectors.length; i++) {
        if (selectors[i].getAttribute('aria-selected') === 'true') { out.selectedStep = i; break; }
      }
    } catch (err) {}
    return out;
  };
  const push = (kind, fields) => {
    const now = Date.now();
    const record = { t: now, p: Math.round(performance.now() * 100) / 100, mono: now - performance.now(), seq: seq++, kind };
    const extra = fields || {};
    for (const key in extra) { try { record[key] = extra[key]; } catch (err) {} }
    timeline.push(record);
  };
  // 1) message events received by THIS window. The state snapshot is taken BEFORE
  //    the page's own listeners run (this one is registered first), i.e. the
  //    pre-dispatch state of the receiving document.
  window.addEventListener('message', event => {
    try {
      const message = event.data;
      if (message && typeof message.type === 'string' && REPO_MESSAGE.test(message.type)) {
        push('msg:' + message.type, { payload: pick(message), state: snapshot() });
      }
    } catch (err) {}
  });
  // 2) same-document postMessage calls (top-level renderer pages driving themselves).
  const originalPostMessage = window.postMessage.bind(window);
  window.postMessage = function (message, targetOrigin, transfer) {
    try {
      if (message && typeof message.type === 'string' && REPO_MESSAGE.test(message.type)) {
        push('post:' + message.type, { payload: pick(message) });
      }
    } catch (err) {}
    return originalPostMessage(message, targetOrigin, transfer);
  };
  // 3) A4 mark lifecycle in real mutation order. Observing the `document` node (not
  //    documentElement, which does not exist yet when an init script runs) keeps the
  //    recorder alive and still sees every subtree mutation. A step change re-renders
  //    #vp wholesale, so marks can be nested inside removed/added subtrees.
  const marksIn = node => {
    if (!node || node.nodeType !== 1 || !node.querySelectorAll) return [];
    const found = [];
    if (node.classList && node.classList.contains('c4-flow-mark')) found.push(node);
    try { node.querySelectorAll('g.c4-flow-mark').forEach(mark => found.push(mark)); } catch (err) {}
    return found;
  };
  new MutationObserver(records => {
    // One batch can contain both the re-rendered #vp group and the mark appended
    // into it afterwards; subtree scans see CURRENT state, so dedupe per callback.
    const seenRemove = new Set(), seenAdd = new Set();
    for (const record of records) {
      for (const node of record.removedNodes) marksIn(node).forEach(mark => {
        if (seenRemove.has(mark)) return;
        seenRemove.add(mark);
        push('mark-remove', { stepIndex: mark.getAttribute('data-step-index'), state: snapshot() });
      });
      for (const node of record.addedNodes) marksIn(node).forEach(mark => {
        if (seenAdd.has(mark)) return;
        seenAdd.add(mark);
        push('mark-add', { stepIndex: mark.getAttribute('data-step-index'), state: snapshot() });
      });
    }
  }).observe(document, { childList: true, subtree: true });
  // 4) report-side narration/readout/guide-state mutations.
  const reportRole = node => {
    let element = node && node.nodeType === 1 ? node : node && node.parentElement;
    while (element && element !== document.body) {
      if (element.classList) {
        if (element.classList.contains('flow-step-announce')) return 'announce';
        if (element.classList.contains('flow-progress')) return 'progress';
      }
      element = element.parentElement;
    }
    return null;
  };
  new MutationObserver(records => {
    for (const record of records) {
      if (record.type === 'attributes') {
        const target = record.target;
        if (target && target.classList && target.classList.contains('flow-guide-btn') && record.attributeName === 'aria-pressed') {
          push('guide-pressed', { pressed: target.getAttribute('aria-pressed'), state: snapshot() });
        }
        continue;
      }
      const role = reportRole(record.target);
      if (role === 'announce') push('announce', { text: (record.target.textContent || (record.target.parentElement || {}).textContent || '').slice(0, 80) });
      else if (role === 'progress') push('readout', { text: ((record.target.textContent || (record.target.parentElement || {}).textContent) || '').slice(0, 30) });
    }
  }).observe(document, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ['aria-pressed'] });
  // 5) user interventions, capture phase, with the state at intervention time.
  document.addEventListener('click', event => {
    const target = event.target && event.target.closest ? event.target.closest(
      '.flow-guide-btn,[data-step-nav],.flow-step-selector,#flow-tabs [role="tab"],#diagram-tabs [role="tab"],' +
      '[data-zoom],[data-full],#dialog-close,#dialog-minus,#dialog-plus,#dialog-reset,#play,#prev,#next,#all,#unsel,li.step'
    ) : null;
    if (target) {
      push('click', {
        control: ((target.id ? '#' + target.id : '') + ' ' + (typeof target.className === 'string' ? target.className : '')).trim().slice(0, 48),
        label: (target.textContent || '').trim().slice(0, 20),
        state: snapshot(),
      });
    }
  }, true);
})();

// Export timing hook (appended separately AFTER window.repoFlowmap exists — an
// accessor installed before assignment does not survive sandboxed embeds).
window.__timelineWrapExport = () => {
  const timeline = window.__timeline;
  const value = window.repoFlowmap;
  if (!timeline || !value || value.__timelineWrapped || typeof value.exportSvg !== 'function') return false;
  value.__timelineWrapped = true;
  const original = value.exportSvg;
  value.exportSvg = function () {
    const svg = original.apply(this, arguments);
    try {
      const now = Date.now();
      const state = {};
      try { Object.assign(state, value.state()); } catch (err) {}
      try { state.markCount = document.querySelectorAll('g.c4-flow-mark').length; } catch (err) {}
      timeline.push({ t: now, p: Math.round(performance.now() * 100) / 100, mono: now - performance.now(),
        seq: timeline.length, kind: 'export', svgLength: svg ? svg.length : 0, state });
    } catch (err) {}
    return svg;
  };
  return true;
};
"""

STEP_ANNOUNCE = re.compile(r'(\d+)\s*/\s*(\d+)\s*단계')
# Cross-frame clock jitter bound: records within this window count as simultaneous.
TOLERANCE_MS = 25.0


def record_step_index(record: dict):
    """Unified step index accessor: message records nest it under payload."""
    payload = record.get('payload')
    if isinstance(payload, dict) and 'stepIndex' in payload:
        return payload['stepIndex']
    return record.get('stepIndex')


class Timeline:
    """Merged chronological log across the main frame and every iframe."""

    def __init__(self) -> None:
        self.records: list[dict] = []
        self._origin: float | None = None

    @staticmethod
    def install(page) -> None:
        page.add_init_script(RECORDER_JS)

    def collect(self, page, phase: str = '') -> None:
        sources: list[tuple[str, object]] = [('main', page.main_frame)]
        try:
            handles = page.locator('iframe').element_handles()
        except Exception:
            handles = []
        for index, handle in enumerate(handles):
            try:
                frame = handle.content_frame()
            except Exception:
                continue
            if frame is None:
                continue
            try:
                info = handle.evaluate(
                    "el => ({id: el.id || '', cls: (el.className || '').toString(), viewId: el.dataset ? (el.dataset.viewId || '') : '',"
                    " dialog: !!(el.closest && el.closest('dialog'))})")
            except Exception:
                info = {}
            name = 'frame%d' % index
            if info.get('id'):
                name += '#' + str(info['id'])
            elif info.get('cls'):
                name += '.' + str(info['cls']).split()[0]
            if info.get('viewId'):
                name += '@' + str(info['viewId'])
            if info.get('dialog'):
                name += '/dialog'
            sources.append((name, frame))
        for name, frame in sources:
            try:
                # Read-cursor per document: repeated collects return only NEW records,
                # so one event is never counted twice (fresh documents start at 0).
                records = frame.evaluate(
                    '(() => { const out = (window.__timeline || []).slice(window.__readMark || 0);'
                    'window.__readMark = (window.__timeline || []).length; return out; })()')
            except Exception:
                continue
            for record in records:
                item = dict(record)
                item['src'] = name
                item['nt'] = round(item.get('p', 0.0) + item.get('mono', 0.0), 1)
                if phase:
                    item['phase'] = phase
                self.records.append(item)
        self.records.sort(key=lambda r: r['nt'])  # stable: per-source order kept on ties
        if self._origin is None and self.records:
            self._origin = self.records[0]['nt']

    # ── queries (message-event records are the canonical signal) ──
    def where(self, kind: str | None = None, src_contains: str | None = None,
              text_contains: str | None = None) -> list[dict]:
        found = []
        for record in self.records:
            if kind and record.get('kind') != kind:
                continue
            if src_contains and src_contains not in record.get('src', ''):
                continue
            if text_contains and text_contains not in str(record.get('text', '')) + str(record.get('label', '')):
                continue
            found.append(record)
        return found

    def announces(self) -> list[dict]:
        return self.where('announce')

    def clicks(self, control_contains: str | None = None) -> list[dict]:
        return [r for r in self.where('click')
                if control_contains is None or control_contains in r.get('control', '')]

    def guide_pressures(self) -> list[dict]:
        return self.where('guide-pressed')

    def sends(self) -> list[dict]:
        return self.where('msg:repo-flowmap-step')

    def acks(self) -> list[dict]:
        return self.where('msg:repo-flowmap-step-ack')

    def marks(self) -> list[dict]:
        return [record for record in self.records
                if record.get('kind') in ('mark-add', 'mark-remove')]

    def exports(self) -> list[dict]:
        return self.where('export')

    # ── evidence rendering ──────────────────────────────────
    def render(self, kinds: tuple[str, ...] | None = None) -> str:
        lines = []
        for index, record in enumerate(self.records):
            if kinds and record.get('kind') not in kinds:
                continue
            offset = (record['nt'] - (self._origin or record['nt'])) / 1000.0
            detail = []
            for key in ('text', 'pressed', 'control', 'label', 'stepIndex', 'step', 'payload'):
                if key in record:
                    detail.append('%s=%r' % (key, record[key]))
            state = record.get('state') or {}
            state_bits = []
            for key in ('step', 'playing', 'stopNotice', 'markCount', 'guidePressed', 'selectedStep', 'announce'):
                if key in state:
                    state_bits.append('%s:%r' % (key, state[key]))
            if state_bits:
                detail.append('state{%s}' % ', '.join(state_bits))
            lines.append('#%02d +%07.3fs [%s]%s %s %s' % (
                index, offset, record.get('phase', '-'), record.get('src', '?'),
                record.get('kind'), ' '.join(detail)))
        return '\n'.join(lines) or '(empty timeline)'


def guide_cycles(timeline: Timeline) -> list[dict]:
    """Group narration announces into guided step cycles (n, total, announce, sends, acks).

    Assumes a run without manual mid-guidance intervention: consecutive announces of
    the same step number fold into one cycle. Stop/end sentences close the active cycle.
    """
    cycles: list[dict] = []
    current: dict | None = None
    for record in timeline.announces():
        match = STEP_ANNOUNCE.search(record.get('text', ''))
        if not match:
            current = None
            continue
        n, total = int(match.group(1)), int(match.group(2))
        if current is None or current['n'] != n:
            current = {'n': n, 'total': total, 'announce': record, 'sends': [], 'acks': []}
            cycles.append(current)
        else:
            current['announce'] = record
    for record in timeline.sends():
        index = record_step_index(record)
        for cycle in cycles:
            if index is not None and index == cycle['n'] - 1:
                cycle['sends'].append(record)
                break
    for record in timeline.acks():
        payload = record.get('payload') or {}
        request = payload.get('requestId')
        for cycle in cycles:
            if any((s.get('payload') or {}).get('requestId') == request for s in cycle['sends']):
                cycle['acks'].append(record)
                break
    return cycles


def assert_guide_figure_agreement(timeline: Timeline) -> list[dict]:
    """Report narration and live figures must point at the SAME step on every guided cycle.

    Contract (ack-based): each narration 'n/N단계' is followed by a repo-flowmap-step
    send for index n-1, and every ack for that request reports step n-1. A figure acking
    a different step (or a send without its narration) is a defect; the raised message
    embeds the rendered timeline so the log itself explains the failure.
    """
    cycles = guide_cycles(timeline)
    problems = []
    for cycle in cycles:
        n = cycle['n']
        announce_nt = cycle['announce']['nt']
        if not cycle['sends']:
            problems.append("단계 %d/%d 안내(%r) 뒤에 그림 단계 지시(repo-flowmap-step) 기록이 없습니다" % (
                n, cycle['total'], cycle['announce'].get('text')))
            continue
        for send in cycle['sends']:
            if send['nt'] < announce_nt - TOLERANCE_MS:
                problems.append("단계 %d 지시가 안내(%r)보다 먼저 기록되었습니다 (역전)" % (n, cycle['announce'].get('text')))
        for ack in cycle['acks']:
            payload = ack.get('payload') or {}
            if payload.get('step') != n - 1:
                problems.append("안내는 %d/%d단계(index %d)를 말하지만 그림 ack는 step=%r을 답했습니다 (requestId=%r)" % (
                    n, cycle['total'], n - 1, payload.get('step'), payload.get('requestId')))
    for send in timeline.sends():
        if not any(send in cycle['sends'] for cycle in cycles):
            payload = send.get('payload') or {}
            problems.append("안내 없이 그림에 단계 지시가 갔습니다 (stepIndex=%r, requestId=%r)" % (
                payload.get('stepIndex'), payload.get('requestId')))
    if problems:
        raise AssertionError('설명·그림 불일치:\n  ' + '\n  '.join(problems) +
                             '\n시간순 기록:\n' + timeline.render())
    return cycles
