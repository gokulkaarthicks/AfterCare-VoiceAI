"""A complete cardiac discharge summary for the demo scripts.

Synthetic: the patient, contact details, and clinician are fictional. It is rich
enough that the intake pipeline produces a high risk score, medications, and a
cardiac-specific questionnaire.
"""

from __future__ import annotations

from app.shared.fixtures.doctors import DEMO_DOCTORS_BY_ID

_CARDIOLOGIST = DEMO_DOCTORS_BY_ID["doc-004"]

SAMPLE_DISCHARGE_SUMMARY = f"""
DISCHARGE SUMMARY

Patient: Daniel Ashcroft
Date of Birth: 1959-03-15
Phone: +15550109901
Email: daniel.ashcroft@example.com

Admission Date: 2026-03-20
Discharge Date: 2026-03-26

Primary Diagnosis: Acute ST-elevation myocardial infarction (STEMI), anterior wall

Procedures Performed:
- Emergency coronary angiography
- Percutaneous coronary intervention (PCI) with drug-eluting stent to the proximal LAD

Hospital Course:
Admitted with crushing substernal chest pain radiating to the left arm, diaphoresis,
and nausea. ECG showed ST elevation in V1-V4; troponin I peaked at 15.2 ng/mL. Taken
emergently to the cath lab where a 95% LAD occlusion was stented. Recovery was
uncomplicated. Echocardiogram: EF 45% with anterior hypokinesis. Heparin weaned on day 3.

Discharge Medications:
1. Aspirin 81 mg daily - antiplatelet, do not stop
2. Clopidogrel 75 mg daily - dual antiplatelet, continue at least 12 months
3. Metoprolol succinate 50 mg daily - beta-blocker for rate and blood pressure
4. Atorvastatin 80 mg nightly - high-intensity statin
5. Lisinopril 10 mg daily - ACE inhibitor for cardiac remodelling
6. Nitroglycerin 0.4 mg sublingual PRN - for chest pain; call 911 if pain persists after 3 doses

Discharge Instructions:
- Cardiology follow-up in 2 weeks
- Monitor blood pressure daily; target below 130/80
- Start cardiac rehabilitation in 2 weeks
- Low-sodium, heart-healthy diet
- No lifting over 10 lbs for 6 weeks
- Call 911 for chest pain, shortness of breath, or fainting
- Do not stop aspirin or clopidogrel without speaking to the cardiologist
- Return to the ED for unusual bruising, blood in stool, or severe headache

Attending Physician: {_CARDIOLOGIST["name"]}, MD
"""

# The same patient, as submitted to POST /intake.
SAMPLE_INTAKE_REQUEST = {
    "patient_name": "Daniel Ashcroft",
    "patient_phone": "+15550109901",
    "patient_dob": "1959-03-15",
    "patient_email": "daniel.ashcroft@example.com",
    "discharge_summary_text": SAMPLE_DISCHARGE_SUMMARY,
}
