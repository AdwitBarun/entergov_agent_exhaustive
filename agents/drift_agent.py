from core.models import AgentResult, Finding
def run(profile, baseline_stats=None):
    dataset = profile.get("dataset",{}).get("name","uploaded_dataset"); rows = profile.get("rows",0); findings=[]
    if baseline_stats and baseline_stats.get("rows"):
        prev = baseline_stats["rows"]; delta = abs(rows-prev) / max(prev,1) * 100
        if delta > 50:
            findings.append(Finding("Anomaly/Drift Agent", "DRIFT-VOLUME-001", "high", "Large row-volume drift detected versus baseline.", "Validate upstream counts, partitions and file completeness before publishing.", dataset, None, .88, {"baseline_rows": prev, "current_rows": rows, "delta_pct": round(delta,2), "affected_records": rows}, "Volume drift may indicate missing partitions, duplicate ingestion or source outage.", False, True, "Volume Drift", "Human Review"))
    else:
        findings.append(Finding("Anomaly/Drift Agent", "DRIFT-BASE-001", "info", "No statistical baseline provided for drift comparison.", "Save trusted profile statistics and compare future uploads against it.", dataset, None, 1.0, {"current_rows": rows}, "Behavioral drift requires historical baseline context.", False, False, "Baseline Missing", "Auto-log"))
    for c in profile.get("columns_profile", []):
        ns = c.get("numeric_stats", {})
        if ns and ns.get("std") is not None and ns.get("mean") not in {None, 0} and abs(ns["std"]) / max(abs(ns["mean"]), 1e-9) > 5:
            findings.append(Finding("Anomaly/Drift Agent", "DRIFT-OUTLIER-001", "medium", f"Column '{c['column']}' has extreme numeric spread.", "Review percentile distribution, units and scaling consistency.", dataset, c["column"], .72, {"mean": ns.get("mean"), "std": ns.get("std"), "min": ns.get("min"), "max": ns.get("max")}, "Outliers can distort models, dashboards and decision rules.", False, True, "Outlier", "Human Review"))
    return AgentResult("Anomaly/Drift Agent", "Issues Found" if findings else "Healthy", max(0,100-len(findings)*10), f"Detected {len(findings)} anomaly/drift findings.", findings)
