"""依症狀比對知識庫,推論可能故障並給出排除步驟。"""
import json
from pathlib import Path

from .detector import LEVEL_RANK

DEFAULT_KB = Path(__file__).with_name("knowledge_base.json")
LEVEL_WEIGHT = {"info": 0.5, "warn": 1.0, "alarm": 1.5}


def load_kb(path=None):
    with open(path or DEFAULT_KB, encoding="utf-8") as f:
        return json.load(f)["faults"]


def diagnose(symptoms, kb=None, min_score=0.3):
    """symptoms: {symptom: level} 或 symptom 清單。回傳依信心排序的故障清單。"""
    kb = kb or load_kb()
    if not isinstance(symptoms, dict):
        symptoms = {s: "warn" for s in symptoms}
    results = []
    for fault in kb:
        weights = fault["symptoms"]
        total = sum(weights.values())
        got = sum(w * LEVEL_WEIGHT.get(symptoms[s], 1.0)
                  for s, w in weights.items() if s in symptoms)
        score = min(got / total, 1.0)
        if score >= min_score:
            results.append({
                "id": fault["id"],
                "name": fault["name"],
                "confidence": round(score, 2),
                "matched": [s for s in weights if s in symptoms],
                "steps": fault["steps"],
            })
    return sorted(results, key=lambda r: -r["confidence"])


def symptoms_from_findings(findings):
    out = {}
    for f in findings:
        if LEVEL_RANK[f.level] >= LEVEL_RANK.get(out.get(f.symptom, "info"), 0):
            out[f.symptom] = f.level
    return out


def build_report(findings_by_machine, kb=None):
    kb = kb or load_kb()
    report = []
    for mid, findings in findings_by_machine.items():
        status = max((f.level for f in findings), key=LEVEL_RANK.get, default="ok")
        if status == "info":
            status = "ok"
        report.append({
            "machine_id": mid,
            "status": status,
            "findings": [f.to_dict() for f in findings],
            "diagnosis": diagnose(symptoms_from_findings(findings), kb) if status != "ok" else [],
        })
    order = {"alarm": 0, "warn": 1, "ok": 2}
    return sorted(report, key=lambda r: (order[r["status"]], r["machine_id"]))
