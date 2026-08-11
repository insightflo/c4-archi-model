#!/usr/bin/env python3
"""Small, dependency-free JSON Schema validator for c4-archi-model schemas.

It implements the schema keywords used by this package. It is intentionally
strict about unknown properties because silent drift is the failure mode this
skill is designed to prevent. It is not a general replacement for the full
JSON Schema specification.
"""
from __future__ import annotations

import sys as _sys
_sys.dont_write_bytecode = True

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class SchemaIssue:
    path: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.message}"


class SchemaLoadError(RuntimeError):
    pass


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SchemaLoadError(f"JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SchemaLoadError(f"Invalid JSON in {path}: {exc}") from exc


def _json_type_matches(instance: Any, expected: str) -> bool:
    if expected == "null":
        return instance is None
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    return False


def _pointer(root: Any, ref: str) -> Any:
    if not ref.startswith("#/"):
        raise SchemaLoadError(f"Only local JSON pointers are supported: {ref}")
    node = root
    for raw_part in ref[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(node, dict) or part not in node:
            raise SchemaLoadError(f"Unresolvable schema reference: {ref}")
        node = node[part]
    return node


def _date_time_ok(value: str) -> bool:
    try:
        normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
        parsed = datetime.fromisoformat(normalized)
        return parsed.tzinfo is not None
    except ValueError:
        return False


def _unique_key(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    except TypeError:
        return repr(value)


def validate(instance: Any, schema: dict[str, Any], *, root_schema: dict[str, Any] | None = None,
             path: str = "$") -> list[SchemaIssue]:
    root = root_schema or schema
    issues: list[SchemaIssue] = []

    if "$ref" in schema:
        try:
            ref_schema = _pointer(root, schema["$ref"])
        except SchemaLoadError as exc:
            return [SchemaIssue(path, str(exc))]
        issues.extend(validate(instance, ref_schema, root_schema=root, path=path))
        schema = {k: v for k, v in schema.items() if k != "$ref"}
        if not schema:
            return issues

    for subschema in schema.get("allOf", []):
        issues.extend(validate(instance, subschema, root_schema=root, path=path))

    if "anyOf" in schema:
        branches = [validate(instance, branch, root_schema=root, path=path) for branch in schema["anyOf"]]
        if not any(not branch for branch in branches):
            issues.append(SchemaIssue(path, "does not match any allowed schema branch"))
            return issues

    if "oneOf" in schema:
        branches = [validate(instance, branch, root_schema=root, path=path) for branch in schema["oneOf"]]
        matches = sum(1 for branch in branches if not branch)
        if matches != 1:
            issues.append(SchemaIssue(path, f"must match exactly one schema branch; matched {matches}"))
            return issues

    if "not" in schema and not validate(instance, schema["not"], root_schema=root, path=path):
        issues.append(SchemaIssue(path, "matches a forbidden schema"))

    if "const" in schema and instance != schema["const"]:
        issues.append(SchemaIssue(path, f"must equal {schema['const']!r}"))

    if "enum" in schema and instance not in schema["enum"]:
        issues.append(SchemaIssue(path, f"must be one of {schema['enum']!r}"))

    expected = schema.get("type")
    if expected is not None:
        allowed = [expected] if isinstance(expected, str) else list(expected)
        if not any(_json_type_matches(instance, item) for item in allowed):
            issues.append(SchemaIssue(path, f"expected type {allowed}, got {type(instance).__name__}"))
            return issues

    if isinstance(instance, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in instance:
                issues.append(SchemaIssue(path, f"missing required property {key!r}"))

        properties = schema.get("properties", {})
        for key, value in instance.items():
            child_path = f"{path}.{key}"
            if key in properties:
                issues.extend(validate(value, properties[key], root_schema=root, path=child_path))
                continue
            additional = schema.get("additionalProperties", True)
            if additional is False:
                issues.append(SchemaIssue(child_path, "additional property is not allowed"))
            elif isinstance(additional, dict):
                issues.extend(validate(value, additional, root_schema=root, path=child_path))

        if "minProperties" in schema and len(instance) < schema["minProperties"]:
            issues.append(SchemaIssue(path, f"must contain at least {schema['minProperties']} properties"))
        if "maxProperties" in schema and len(instance) > schema["maxProperties"]:
            issues.append(SchemaIssue(path, f"must contain at most {schema['maxProperties']} properties"))

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            issues.append(SchemaIssue(path, f"must contain at least {schema['minItems']} items"))
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            issues.append(SchemaIssue(path, f"must contain at most {schema['maxItems']} items"))
        if schema.get("uniqueItems"):
            keys = [_unique_key(item) for item in instance]
            if len(keys) != len(set(keys)):
                issues.append(SchemaIssue(path, "items must be unique"))
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(instance):
                issues.extend(validate(item, item_schema, root_schema=root, path=f"{path}[{index}]"))

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            issues.append(SchemaIssue(path, f"must have length >= {schema['minLength']}"))
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            issues.append(SchemaIssue(path, f"must have length <= {schema['maxLength']}"))
        if "pattern" in schema and re.fullmatch(schema["pattern"], instance) is None:
            issues.append(SchemaIssue(path, f"does not match pattern {schema['pattern']!r}"))
        if schema.get("format") == "date-time" and not _date_time_ok(instance):
            issues.append(SchemaIssue(path, "must be an ISO-8601 date-time with timezone"))

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            issues.append(SchemaIssue(path, f"must be >= {schema['minimum']}"))
        if "maximum" in schema and instance > schema["maximum"]:
            issues.append(SchemaIssue(path, f"must be <= {schema['maximum']}"))
        if "exclusiveMinimum" in schema and instance <= schema["exclusiveMinimum"]:
            issues.append(SchemaIssue(path, f"must be > {schema['exclusiveMinimum']}"))
        if "exclusiveMaximum" in schema and instance >= schema["exclusiveMaximum"]:
            issues.append(SchemaIssue(path, f"must be < {schema['exclusiveMaximum']}"))

    return issues


def validate_file(instance_path: Path, schema_path: Path) -> list[SchemaIssue]:
    instance = load_json(instance_path)
    schema = load_json(schema_path)
    if not isinstance(schema, dict):
        raise SchemaLoadError(f"Schema root must be an object: {schema_path}")
    return validate(instance, schema)
