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
  return errors;
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
