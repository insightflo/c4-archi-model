import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
import { validateFlowmap } from "./validate_flowmap.mjs";

const input = path.resolve(process.argv[2] || "docs/flowmap/flowmap.json");
const template = path.resolve(process.argv[3] || path.join(scriptDir, "..", "template.html"));
const output = path.resolve(process.argv[4] || "docs/flowmap/flowmap.html");
const marker = "/* FLOWMAP_JSON */";

try {
  const data = JSON.parse(fs.readFileSync(input, "utf8"));
  const errors = validateFlowmap(data);
  if (errors.length) throw new Error(`스키마 오류:\n- ${errors.join("\n- ")}`);

  const source = fs.readFileSync(template, "utf8");
  if (source.split(marker).length !== 2) {
    throw new Error(`template.html에 ${marker} 마커가 정확히 1개 있어야 합니다`);
  }

  const json = JSON.stringify(data, null, 2).replaceAll("<", "\\u003c");
  const html = source.replace(marker, json);
  fs.mkdirSync(path.dirname(output), { recursive: true });
  fs.writeFileSync(output, html, "utf8");
  console.log(`[PASS] ${output}`);
} catch (error) {
  console.error(`[FAIL] ${error.message}`);
  process.exit(1);
}
