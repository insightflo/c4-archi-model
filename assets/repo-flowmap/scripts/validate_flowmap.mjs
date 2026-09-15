import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const allowedSides = new Set(["top", "right", "bottom", "left", "n", "e", "s", "w"]);
const allowedStates = new Set(["failover", "blocked", "cond"]);
const flowIdPattern = /^[A-Za-z0-9_-]+$/;
const colorPattern = /^(#[0-9A-Fa-f]{3,8}|var\(--[A-Za-z0-9_-]+\)|[A-Za-z]+|rgba?\([0-9.,%\s]+\)|hsla?\([0-9.,%\sdegrad]+\))$/;

function isPlainObject(value) {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

export function validateFlowmap(data) {
  const errors = [];
  const needObject = (value, at) => {
    if (!value || typeof value !== "object" || Array.isArray(value)) errors.push(`${at}: 객체가 필요합니다`);
  };
  const needArray = (value, at) => {
    if (!Array.isArray(value)) errors.push(`${at}: 배열이 필요합니다`);
  };
  const duplicateIds = (items, at) => {
    if (!Array.isArray(items)) return new Set();
    const ids = new Set();
    items.forEach((item, index) => {
      if (!item || typeof item.id !== "string" || !item.id.trim()) {
        errors.push(`${at}[${index}].id: 비어 있지 않은 문자열이 필요합니다`);
      } else if (ids.has(item.id)) {
        errors.push(`${at}: 중복 id "${item.id}"`);
      } else {
        ids.add(item.id);
      }
    });
    return ids;
  };

  needObject(data, "root");
  if (!data || typeof data !== "object") return errors;
  needObject(data.meta, "meta");
  needArray(data.layers, "layers");
  needArray(data.nodes, "nodes");
  needArray(data.flows, "flows");
  if (typeof data.meta?.project !== "string" || !data.meta.project.trim()) {
    errors.push("meta.project: 비어 있지 않은 문자열이 필요합니다");
  }
  if (typeof data.meta?.last_analyzed_commit !== "string" || !data.meta.last_analyzed_commit.trim()) {
    errors.push("meta.last_analyzed_commit: 비어 있지 않은 문자열이 필요합니다");
  }

  const layerIds = duplicateIds(data.layers, "layers");
  const nodeIds = duplicateIds(data.nodes, "nodes");
  duplicateIds(data.flows, "flows");

  (Array.isArray(data.layers) ? data.layers : []).forEach((layer, index) => {
    if (!isPlainObject(layer)) return;
    if (typeof layer.label !== "string" || !layer.label.trim()) {
      errors.push(`layers[${index}].label: 비어 있지 않은 문자열이 필요합니다`);
    }
    if (layer.color != null && (typeof layer.color !== "string" || !colorPattern.test(layer.color.trim()))) {
      errors.push(`layers[${index}].color: 허용되지 않는 색상 값 "${layer.color}"`);
    }
  });

  (Array.isArray(data.nodes) ? data.nodes : []).forEach((node, index) => {
    if (!isPlainObject(node)) {
      errors.push(`nodes[${index}]: 객체가 필요합니다`);
      return;
    }
    if (!layerIds.has(node.layer)) errors.push(`nodes[${index}].layer: 존재하지 않는 "${node.layer}"`);
    if (!node.label) errors.push(`nodes[${index}].label: 필수입니다`);
  });

  (Array.isArray(data.flows) ? data.flows : []).forEach((flow, flowIndex) => {
    if (!isPlainObject(flow)) {
      errors.push(`flows[${flowIndex}]: 객체가 필요합니다`);
      return;
    }
    if (!flow.title) errors.push(`flows[${flowIndex}].title: 필수입니다`);
    if (typeof flow.id === "string" && !flowIdPattern.test(flow.id)) {
      errors.push(`flows[${flowIndex}].id: URL 해시 복원을 위해 영숫자·_·-만 허용됩니다 ("${flow.id}")`);
    }
    if (!Array.isArray(flow.steps)) {
      errors.push(`flows[${flowIndex}].steps: 배열이 필요합니다`);
      return;
    }
    if (flow.status != null && flow.status !== "stale") {
      errors.push(`flows[${flowIndex}].status: "stale"만 허용됩니다`);
    }
    flow.steps.forEach((step, stepIndex) => {
      const at = `flows[${flowIndex}].steps[${stepIndex}]`;
      if (!isPlainObject(step)) {
        errors.push(`${at}: 객체가 필요합니다`);
        return;
      }
      if (!nodeIds.has(step.from)) errors.push(`${at}.from: 존재하지 않는 "${step.from}"`);
      if (!nodeIds.has(step.to)) errors.push(`${at}.to: 존재하지 않는 "${step.to}"`);
      for (const key of ["fromSide", "toSide"]) {
        if (step[key] != null && !allowedSides.has(step[key])) {
          errors.push(`${at}.${key}: 허용되지 않는 "${step[key]}"`);
        }
      }
      if (step.kind != null && step.kind !== "self") errors.push(`${at}.kind: "self"만 허용됩니다`);
      if (step.state != null) {
        if (!allowedStates.has(step.state)) {
          errors.push(`${at}.state: failover·blocked·cond만 허용됩니다 ("${step.state}")`);
        } else if (step.from === step.to && step.kind !== "self" && step.recursive !== true) {
          // 내부 처리 단계는 바깥 선이 없어서 상태를 그릴 자리가 없다.
          errors.push(`${at}.state: 모듈 내부 처리 단계에는 쓸 수 없습니다`);
        }
      }
      if (step.stateLabel != null) {
        if (typeof step.stateLabel !== "string" || !step.stateLabel.trim()) {
          errors.push(`${at}.stateLabel: 비어 있지 않은 문자열이 필요합니다`);
        } else if (step.stateLabel.length > 12) {
          errors.push(`${at}.stateLabel: 12자 이하여야 합니다 ("${step.stateLabel}")`);
        }
        if (step.state == null) errors.push(`${at}.stateLabel: state 없이 쓸 수 없습니다`);
      }
      if ((step.kind === "self" || step.recursive === true) && step.from !== step.to) {
        errors.push(`${at}: self/recursive는 from === to에서만 허용됩니다`);
      }
      if (step.recursive != null && typeof step.recursive !== "boolean") {
        errors.push(`${at}.recursive: boolean이 필요합니다`);
      }
    });
  });
  if (Object.hasOwn(data, "c4")) validateTypedView(data, errors);
  return errors;
}

// Local maintained fork: additive typed C4/UML view validation. Legacy inputs are unchanged.
function validateTypedView(data, errors) {
  if (data.c4 == null || !isPlainObject(data.c4)) { errors.push('c4: typed extension object required'); return; }
  const c = data.c4, view = c.view;
  const modeFor = {systemLandscape:'structure',systemContext:'structure',container:'structure',component:'structure',code:'class',dynamic:'sequence',deployment:'deployment'};
  if (c.extensionVersion !== 1 || !isPlainObject(view) || modeFor[view.type] !== c.mode) {
    errors.push('c4: unsupported extension version / View type / mode'); return;
  }
  if (!['structure','class','sequence','deployment'].includes(c.mode)) errors.push('c4.mode: unsupported');
  if (c.viewId !== view.id || typeof c.modelPath !== 'string' || !/^[a-f0-9]{64}$/.test(c.modelSha256 || '')) errors.push('c4: exact View/model SHA-256 binding required');
  if (typeof c.modelPath==='string' && (path.isAbsolute(c.modelPath)||c.modelPath.split(/[\\/]/).includes('..'))) errors.push('c4.modelPath: package-relative path required');
  if (!Array.isArray(c.boundaries) || !Array.isArray(c.targets)) errors.push('c4: boundary/target arrays required');
  if (!Array.isArray(data.nodes) || !Array.isArray(data.flows) || data.flows.length !== 1) { errors.push('c4: one complete native flow per View required'); return; }
  if (JSON.stringify(data.nodes.map(n=>n.id)) !== JSON.stringify(view.elementIds)) errors.push('c4: canonical participant/element order and IDs differ');
  if (data.nodes.length>24 || (view.relationshipIds||[]).length>32 || (view.steps||[]).length>40) errors.push('c4: split View exceeding 24 nodes / 32 relations / 40 steps');
  const logicalPlacement=c.mode==='deployment' && c.deploymentPresentation==='logical-placement';
  const hasLogical=data.nodes.some(n=>['softwareSystem','container'].includes(n.element?.type));
  if (c.mode==='deployment' && (c.deploymentPresentation!=null && !['physical-instances','logical-placement'].includes(c.deploymentPresentation) || logicalPlacement && !hasLogical)) errors.push('deploymentPresentation: unsupported or inconsistent presentation');
  if (c.mode!=='deployment' && c.deploymentPresentation!=null) errors.push('deploymentPresentation: deployment only');
  const nodes=new Map(data.nodes.map(n=>[n.id,n]));
  const elements=[...data.nodes.map(n=>n.element),...(c.boundaries||[])];
  const byId=new Map(elements.filter(Boolean).map(e=>[e.id,e]));
  for(const n of data.nodes) {
    if (!isPlainObject(n.element) || n.element.id!==n.id || n.label!==n.element.name || n.desc!==n.element.description) { errors.push('c4: node canonical ID/name/description mismatch'); continue; }
    if (!['person','softwareSystem','container','component','codeElement','deploymentNode','infrastructureNode'].includes(n.element.type)) errors.push('c4: unsupported canonical element type');
    if (!Array.isArray(n.element.claimIds) || !n.element.claimIds.length) errors.push('c4: node evidence claim required');
    if (c.mode==='class') {
      const d=n.element.codeDetails;
      if (n.element.type!=='codeElement' || !d || !['class','interface'].includes(d.kind)) {errors.push('class: explicit class/interface codeDetails required');continue;}
      for (const key of ['attributes','methods']) {
        if (d[key]!==null && !Array.isArray(d[key])) {errors.push('class: null or explicit member list required');continue;}
        for(const m of d[key]||[]) if (!m || typeof m.declaration!=='string' || !m.declaration.trim() || !Array.isArray(m.claimIds) || !m.claimIds.length) errors.push('class: member declaration and evidence required');
      }
    }
    if (c.mode==='deployment') {
      const allowed=logicalPlacement?['deploymentNode','infrastructureNode','softwareSystem','container']:['deploymentNode','infrastructureNode'];
      if (!allowed.includes(n.element.type)) errors.push('deployment: explicit deployment boundaries/instances required');
      if (logicalPlacement && ['softwareSystem','container'].includes(n.element.type) && n.element.instanceOfId) errors.push('deployment: logical element cannot masquerade as an instance');
      if (n.element.instanceOfId && !(c.targets||[]).some(t=>t.id===n.element.instanceOfId && ['softwareSystem','container'].includes(t.type))) errors.push('deployment: unsupported deployment target');
    }
  }
  for(const e of elements.filter(Boolean)) {
    let p=e.parentId; const seen=new Set([e.id]);
    while(p && byId.has(p)) {if(seen.has(p)){errors.push('c4: cyclic containment');break;}seen.add(p);p=byId.get(p).parentId;}
  }
  const steps=data.flows[0]?.steps;
  if (!Array.isArray(steps)) return;
  const canonical=c.mode==='sequence' ? [...(view.steps||[])].sort((a,b)=>a.order-b.order) : null;
  if (c.mode==='sequence' && (data.nodes.length>12 || steps.length!==canonical.length)) errors.push('sequence: participant budget/order count mismatch');
  steps.forEach((s,i)=>{
    const r=s.relationship;
    if(!r || r.id!==s.relationshipId || r.sourceId!==s.from || r.destinationId!==s.to || r.description!==s.call) {errors.push('c4: relationship ID/endpoints/display call disagree');return;}
    if(s.order!==i+1) errors.push('c4: native displayed order must be consecutive');
    if(canonical && (!s.canonicalStep || JSON.stringify(s.canonicalStep)!==JSON.stringify(canonical[i]) || s.relationshipId!==canonical[i]?.relationshipId)) errors.push('sequence: canonical step identity/order mismatch');
    if(canonical && s.canonicalStep?.kind!=='interaction') errors.push('sequence: decision/failure/recovery fragments unsupported');
    if(canonical) {
      const step=canonical[i];
      const note=step?.condition ? '조건: '+step.condition+(step.note?'\n'+step.note:'') : step?.note;
      if(s.note!==note) errors.push('sequence: display note must preserve original condition prefix and note');
    }
    if(c.mode==='class' && (!r.codeRelation || !['inheritance','realization','association','composition','dependency'].includes(r.codeRelation.kind))) errors.push('class: explicit supported UML relationship kind required');
    for(const key of ['return','async','alt','par']) if(key in s) errors.push('sequence: unsupported explicit '+key);
  });
  const expected=c.mode==='sequence'?canonical.map(s=>s.relationshipId):view.relationshipIds;
  if(JSON.stringify(steps.map(s=>s.relationshipId))!==JSON.stringify(expected)) errors.push('c4: full ordered relationship set mismatch');
}

if (process.argv[1] && import.meta.url === pathToFileURL(path.resolve(process.argv[1])).href) {
  const input = path.resolve(process.argv[2] || "docs/flowmap/flowmap.json");
  try {
    const data = JSON.parse(fs.readFileSync(input, "utf8"));
    const errors = validateFlowmap(data);
    if (errors.length) {
      errors.forEach((error) => console.error(`[FAIL] ${error}`));
      process.exit(1);
    }
    console.log(`[PASS] ${data.nodes.length} nodes · ${data.flows.length} flows · ${data.flows.reduce((n, flow) => n + flow.steps.length, 0)} steps`);
  } catch (error) {
    console.error(`[FAIL] ${error.message}`);
    process.exit(1);
  }
}
