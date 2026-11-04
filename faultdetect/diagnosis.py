"""依症狀比對知識庫,推論可能故障並給出排除步驟。"""
import json

from .detector import LEVEL_RANK, PROFILES_DIR

LEVEL_WEIGHT = {"info": 0.5, "warn": 1.0, "alarm": 1.5}


def load_kb(path=None, profile="generic"):
    """讀取知識庫;支援 "extends" 繼承,同 id 覆寫,"remove" 移除。"""
    with open(path or PROFILES_DIR / profile / "knowledge_base.json", encoding="utf-8") as f:
        kb = json.load(f)
    if not kb.get("extends"):
        return kb["faults"]
    faults = {f["id"]: f for f in load_kb(profile=kb["extends"])}
    for fid in kb.get("remove", []):
        faults.pop(fid, None)
    faults.update({f["id"]: f for f in kb.get("faults", [])})
    return list(faults.values())


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
                "category": fault.get("category", ""),
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
