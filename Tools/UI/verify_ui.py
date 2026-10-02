#!/usr/bin/env python3
"""Offline source checks. Does not assert runtime UMG accessibility or performance."""
from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "ArtSource" / "UI"


def luminance(color: str) -> float:
    rgb = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722)))


def main():
    theme = json.loads((UI / "theme.json").read_text(encoding="utf-8"))
    result = {"schema": "iron-echo-ui-source-check/0.1", "scope": "Offline tokens, SVG XML and control rectangles only", "runtimeVerified": False, "contrast": [], "layouts": [], "icons": [], "failures": []}
    for pair in theme["contrastPairs"]:
        a = luminance(theme["colors"][pair["fg"]])
        b = luminance(theme["colors"][pair["bg"]])
        ratio = (max(a, b) + 0.05) / (min(a, b) + 0.05)
        record = dict(pair, ratio=round(ratio, 3), passed=ratio >= pair["minimum"])
        result["contrast"].append(record)
        if not record["passed"]:
            result["failures"].append(f"Contrast failed: {pair['label']}")
    manifest = json.loads((UI / "layout_manifest.json").read_text(encoding="utf-8"))
    for layout in manifest["layouts"]:
        failures = []
        ET.parse(ROOT / layout["file"])
        for control in layout["controls"]:
            if min(control["width"], control["height"]) < theme["metrics"]["minimumTarget"]:
                failures.append(f"{control['id']}: target smaller than token minimum")
            if control["x"] < 0 or control["y"] < 0 or control["x"] + control["width"] > layout["width"] or control["y"] + control["height"] > layout["height"]:
                failures.append(f"{control['id']}: control outside viewport")
        if sum(control["primary"] for control in layout["controls"]) > 1:
            failures.append("More than one primary action")
        for i, a in enumerate(layout["controls"]):
            for b in layout["controls"][i + 1:]:
                x_gap = max(b["x"] - a["x"] - a["width"], a["x"] - b["x"] - b["width"])
                y_gap = max(b["y"] - a["y"] - a["height"], a["y"] - b["y"] - b["height"])
                if max(x_gap, y_gap) < theme["metrics"]["minimumGap"]:
                    failures.append(f"Targets too close: {a['id']} / {b['id']}")
        result["layouts"].append({"file": layout["file"], "viewport": [layout["width"], layout["height"]], "controls": len(layout["controls"]), "passed": not failures})
        result["failures"].extend(f"{layout['file']}: {message}" for message in failures)
    for path in sorted((UI / "Icons").glob("*.svg")):
        root = ET.parse(path).getroot()
        has_title = root.find("{http://www.w3.org/2000/svg}title") is not None
        passed = has_title and root.attrib.get("viewBox") == "0 0 24 24" and root.attrib.get("stroke") == "currentColor"
        result["icons"].append({"file": str(path.relative_to(ROOT)), "passed": passed})
        if not passed:
            result["failures"].append(f"Icon source invalid: {path.name}")
    motion = theme["motion"]
    exit_ratio = motion["exitSeconds"] / motion["enterSeconds"]
    result["motion"] = {"exitEnterRatio": round(exit_ratio, 3), "reducedMotionConfig": motion["reducedMotion"], "passed": abs(exit_ratio - 0.4) < 1e-6 and motion["reducedMotion"]["duration"] == 0}
    if not result["motion"]["passed"]:
        result["failures"].append("Motion token policy mismatch")
    (UI / "contrast_report.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding="utf-8")
    print(f"Contrast: {sum(p['passed'] for p in result['contrast'])}/{len(result['contrast'])}; layouts: {sum(p['passed'] for p in result['layouts'])}/{len(result['layouts'])}; icons: {sum(p['passed'] for p in result['icons'])}/{len(result['icons'])}.")
    print("Runtime UMG checks remain unverified.")
    if result["failures"]:
        for message in result["failures"]:
            print(message)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
