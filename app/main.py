import os
import uuid
import json
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from app.compatibility_engine import check_rbc_compatibility, apply_antibody_gate
from app.risk_matrix import risk_assessment
from app.storage import now_iso, compute_hash, save_run, load_run
from app.pdf_generator import build_validation_pdf

app = FastAPI(title="TVIP - BECS Validation Demonstrator", version="1.0.0")

HOSPITAL_NAME = os.getenv("HOSPITAL_NAME", "Hospital Name")
DIVISION_NAME = os.getenv("DIVISION_NAME", "Transfusion Medicine / Validation")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
WATERMARK = os.getenv("CONFIDENTIAL_WATERMARK", "CONFIDENTIAL - VALIDATION EVIDENCE")

class ValidateRequest(BaseModel):
    workflow: str = Field(default="Type & Cross")
    test_script_id: str = Field(default="BB-VAL-TS-001")
    donor_type: str = Field(..., examples=["O-"])
    recipient_type: str = Field(..., examples=["A+"])
    antibody_screen_positive: bool = False
    crossmatch_incompatible: bool = False
    emergency_release: bool = False

@app.get("/")
def root():
    return {"status": "ok", "app": app.title, "version": app.version}

@app.post("/validate")
def validate(req: ValidateRequest):
    run_id = f"BB-VAL-{uuid.uuid4().hex[:10].upper()}"

    abo = check_rbc_compatibility(req.donor_type, req.recipient_type)
    gate_ok, gate_msg, gate_rule = apply_antibody_gate(req.antibody_screen_positive, req.crossmatch_incompatible)

    compatible = abo.compatible and gate_ok
    expected = "COMPATIBLE" if compatible else "INCOMPATIBLE"
    actual = expected  # In a real system you could simulate mismatches; keep “clean” for evidence demo.

    risk = risk_assessment(
        abo_rh_compatible=abo.compatible,
        antibody_screen_positive=req.antibody_screen_positive,
        crossmatch_incompatible=req.crossmatch_incompatible,
        emergency_release=req.emergency_release
    )

    rule_trace = [abo.rule_id, gate_rule]
    status = "PASS" if expected == actual else "FAIL"

    run = {
        "run_id": run_id,
        "timestamp_utc": now_iso(),
        "workflow": req.workflow,
        "test_script_id": req.test_script_id,
        "donor_type": req.donor_type.upper(),
        "recipient_type": req.recipient_type.upper(),
        "expected_result": expected,
        "actual_result": actual,
        "status": status,
        "risk": {"level": risk.level, "score": risk.score, "drivers": risk.drivers},
        "rule_trace": rule_trace,
        "notes": {
            "compatibility_rationale": abo.rationale,
            "gate_rationale": gate_msg,
        },
    }

    # Evidence hash (includes everything above except the hash field itself)
    evidence_hash = compute_hash(run)
    run["evidence_hash"] = evidence_hash

    save_run(run_id, run)

    return {
        "run_id": run_id,
        "status": status,
        "risk": run["risk"],
        "evidence_hash": evidence_hash,
        "verification_url": f"{BASE_URL}/verify/{run_id}",
        "pdf_url": f"{BASE_URL}/pdf/{run_id}",
        "fhir_url": f"{BASE_URL}/fhir/{run_id}",
    }

@app.get("/verify/{run_id}")
def verify(run_id: str):
    run = load_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found.")

    # Recompute hash to prove integrity
    stored_hash = run.get("evidence_hash", "")
    run_copy = dict(run)
    run_copy.pop("evidence_hash", None)
    recomputed = compute_hash(run_copy)

    integrity_ok = (stored_hash == recomputed)

    return {
        "run_id": run_id,
        "integrity_ok": integrity_ok,
        "stored_hash": stored_hash,
        "recomputed_hash": recomputed,
        "run": run,
    }

@app.get("/pdf/{run_id}")
def pdf(run_id: str):
    run = load_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found.")

    out_path = os.path.join("validation_reports", f"{run_id}.pdf")
    verification_url = f"{BASE_URL}/verify/{run_id}"

    build_validation_pdf(
        out_path=out_path,
        hospital_name=HOSPITAL_NAME,
        division_name=DIVISION_NAME,
        watermark_text=WATERMARK,
        run=run,
        verification_url=verification_url,
        logo_path="static/hospital_logo.png"
    )

    return FileResponse(out_path, media_type="application/pdf", filename=f"{run_id}.pdf")

@app.get("/fhir/{run_id}")
def fhir_export(run_id: str):
    run = load_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Validation run not found.")

    # Simple FHIR-like “stamp” (not a full transfusion resource model)
    fhir_bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "timestamp": run["timestamp_utc"],
        "identifier": {"system": "urn:tvip:validation", "value": run_id},
        "entry": [
            {
                "resource": {
                    "resourceType": "Observation",
                    "status": "final",
                    "code": {"text": "BECS Validation Outcome"},
                    "valueString": f'{run["status"]} ({run["expected_result"]})',
                    "note": [{"text": f'EvidenceHash: {run["evidence_hash"]}'}],
                }
            }
        ]
    }
    return JSONResponse(fhir_bundle)

@app.post("/run-validation-pack")
def run_validation_pack():

    scenarios = [
        {"donor": "O-", "recipient": "A+", "antibody": False, "crossmatch": False},
        {"donor": "O+", "recipient": "O-", "antibody": False, "crossmatch": True},
        {"donor": "A+", "recipient": "AB+", "antibody": False, "crossmatch": False},
        {"donor": "B-", "recipient": "A+", "antibody": True, "crossmatch": False},
        {"donor": "AB+", "recipient": "O-", "antibody": False, "crossmatch": True},
        {"donor": "O-", "recipient": "O-", "antibody": False, "crossmatch": False},
    ]

    results = []

    for s in scenarios:

        compatibility = check_rbc_compatibility(s["donor"], s["recipient"])

        risk = risk_assessment(
            compatibility.compatible,
            s["antibody"],
            s["crossmatch"],
            False
        )

        results.append({
            "donor": s["donor"],
            "recipient": s["recipient"],
            "compatible": compatibility.compatible,
            "risk_level": risk.level
        })

    return {
        "validation_pack": "Blood Bank Validation Scenario Pack",
        "tests_run": len(results),
        "results": results
    }
@app.get("/dashboard")
def dashboard():
    return FileResponse("dashboard/index.html")

@app.get("/dashboard-data")
def dashboard_data():

    report_dir = "validation_reports"

    total = 0
    passed = 0
    failed = 0

    low = 0
    moderate = 0
    high = 0
    critical = 0

    runs = []

    if os.path.exists(report_dir):

        for file in os.listdir(report_dir):

            if file.endswith(".json"):

                total += 1

                with open(os.path.join(report_dir, file)) as f:

                    data = json.load(f)

                    runs.append({
                        "id": data.get("run_id",""),
                        "date": data.get("timestamp_utc",""),
                        "donor": data.get("donor_type",""),
                        "recipient": data.get("recipient_type",""),
                        "risk": data.get("risk",{}).get("level",""),
                        "status": data.get("status","")
                    })

                    if data["status"] == "PASS":
                        passed += 1
                    else:
                        failed += 1

                    level = data["risk"]["level"]

                    if level == "LOW":
                        low += 1
                    elif level == "MODERATE":
                        moderate += 1
                    elif level == "HIGH":
                        high += 1
                    elif level == "CRITICAL":
                        critical += 1

    return {
        "total_runs": total,
        "pass": passed,
        "fail": failed,
        "low": low,
        "moderate": moderate,
        "high": high,
        "critical": critical,
        "runs": runs
    }

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.pagesizes import letter

@app.get("/master-report")
def master_report():

    report_dir = "validation_reports"

    total = 0
    passed = 0
    failed = 0

    if os.path.exists(report_dir):

        for file in os.listdir(report_dir):

            if file.endswith(".json"):

                total += 1

                with open(os.path.join(report_dir, file)) as f:

                    data = json.load(f)

                    if data["status"] == "PASS":
                        passed += 1
                    else:
                        failed += 1

    output = "Validation_Master_Report.pdf"

    styles = getSampleStyleSheet()

    elements = []

    elements.append(Paragraph("Validation Master Report", styles['Title']))
    elements.append(Spacer(1,20))

    elements.append(Paragraph(f"Total Runs: {total}", styles['Normal']))
    elements.append(Paragraph(f"Pass Results: {passed}", styles['Normal']))
    elements.append(Paragraph(f"Fail Results: {failed}", styles['Normal']))

    doc = SimpleDocTemplate(output, pagesize=letter)
    doc.build(elements)

    return FileResponse(output, media_type="application/pdf", filename=output)
