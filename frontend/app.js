document.addEventListener("DOMContentLoaded", () => {
  const claimSelect = document.getElementById("claim-select");
  const btnLoadClaim = document.getElementById("btn-load-claim");
  
  const resultsContainer = document.getElementById("results-container");
  const errorContainer = document.getElementById("error-container");
  const loadingOverlay = document.getElementById("loading-overlay");

  const claimsData = {
    "001": {
      vehicle_type: "CAR",
      claim_type: "ACCIDENT",
      incident_date: "2026-09-01",
      claim_date: "2026-09-03",
      insured_declared_value: 750000.0,
      claimed_amount: 32000.0,
      claim_form_text: "Vehicle Reg: DL-01-AB-1234. Model: Hyundai i20. Date of incident: 2026-09-01. Driver had valid DL: DL-987654321. Minor collision with median barrier causing front bumper and headlight crack. Estimated repair: Rs. 32,000. Policy Number: POL-99887766-CAR",
      evidence_doc_text: "Authorized Service Center Estimate. Vehicle DL-01-AB-1234. Date: 2026-09-02. Replaced parts: Front bumper assembly (Rs 18,000), Right headlight unit (Rs 8,500), Labor & Painting charges (Rs 5,500). Total: Rs. 32,000.",
      incident_description_text: "On 2026-09-01 evening around 8 PM, I swerved to avoid a stray animal near Sector 18 and made contact with the road divider. The front bumper was damaged. I informed the insurer within 48 hours."
    },
    "002": {
      vehicle_type: "TWO_WHEELER",
      claim_type: "ACCIDENT",
      incident_date: "2026-08-20",
      claim_date: "2026-08-22",
      insured_declared_value: 90000.0,
      claimed_amount: 14500.0,
      claim_form_text: "short",
      evidence_doc_text: "[MISSING DOCUMENT]",
      incident_description_text: "I had a skid on the evening of 2026-08-20 due to rain. The bike sustained side damage."
    },
    "003": {
      vehicle_type: "CAR",
      claim_type: "ACCIDENT",
      incident_date: "2026-08-25",
      claim_date: "2026-08-27",
      insured_declared_value: 550000.0,
      claimed_amount: 45000.0,
      claim_form_text: `MOTOR INSURANCE CLAIM FORM
Claim Reference: CLM-2026-003
Vehicle Type: Private Car
Registration Number: MH-12-AB-1234
Make / Model: Maruti Suzuki Swift ZXi
Insured Declared Value (IDV): Rs. 5,50,000
Policy Number: POL-55443322-CAR

INCIDENT & DRIVER DETAILS:
Date of Incident: 2026-08-25
Time of Incident: 16:30 IST
Date of Claim Filing: 2026-08-27
Driver Name: Vikram Patil
Driver Licence Number: MH-12-2019008812

DAMAGE REPORTED:
Front bumper collision and front radiator grill damage sustained while parking inside garage.
Claimed Amount: Rs. 45,000.`,
      incident_description_text: `CUSTOMER INCIDENT STATEMENT
Policyholder: Vikram Patil
Vehicle Reg: MH-12-AB-1234

On the afternoon of August 20, 2026 at around 4:30 PM, I was driving my Maruti Swift on the Pune-Mumbai highway. A passing heavy commercial truck swerved into my lane and clipped my right side wing mirror and scratched the right front and rear door panels. The side mirror glass snapped off. I managed to control the car and brought it back home.`,
      evidence_doc_text: `GARAGE REPAIR ESTIMATE & FINAL BILL
Bill No: INV-2026-0815
Invoice Date: 2026-08-15
Vehicle Reg No: MH-12-AB-1235
Model: Maruti Suzuki Swift

ITEMIZED REPAIR BILL:
1. Rear Bumper Assembly Replacement: Rs. 24,000.00
2. Rear Tail Lamp Assembly Left & Right: Rs. 16,000.00
3. Rear Boot Lid Dents Repair & Painting: Rs. 18,000.00
4. Painting & Labor Charges: Rs. 10,000.00
---------------------------------------------------
TOTAL AMOUNT INVOICED: Rs. 68,000.00

Work completed and handed over to customer on 2026-08-15.`
    }
  };

  btnLoadClaim.addEventListener("click", async () => {
    const claimId = claimSelect.value;
    const payload = claimsData[claimId];
    
    if (!payload) return;
    
    // UI Reset
    errorContainer.classList.add("hidden");
    resultsContainer.classList.add("hidden");
    loadingOverlay.classList.remove("hidden");
    
    // Overview Data
    document.getElementById("overview-id").textContent = `CLM-${claimId}`;
    document.getElementById("overview-vehicle").textContent = payload.vehicle_type;
    document.getElementById("overview-incident").textContent = payload.claim_type;
    document.getElementById("overview-amount").textContent = `Rs. ${payload.claimed_amount.toLocaleString()}`;

    try {
      const res = await fetch("/api/claims/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      
      if (!res.ok) {
        throw new Error(`Server returned ${res.status}`);
      }
      
      const data = await res.json();
      renderResults(data);
    } catch (err) {
      errorContainer.textContent = `Error reviewing claim: ${err.message}`;
      errorContainer.classList.remove("hidden");
    } finally {
      loadingOverlay.classList.add("hidden");
    }
  });

  function renderResults(data) {
    resultsContainer.classList.remove("hidden");
    
    // 1. Evidence Status
    const evidenceList = document.getElementById("evidence-list");
    evidenceList.innerHTML = "";
    
    let claimFormStatus = "✓ Claim Form";
    let estimateStatus = "✓ Repair Estimate";
    let firStatus = "✓ FIR";
    let incidentStatus = "✓ Incident Description";
    
    const rule2 = data.rule_results.find(r => r.rule_id === "R-002");
    if (rule2 && rule2.status === "FAIL") {
      if (rule2.evidence.includes("Claim Form")) claimFormStatus = "⚠ Claim Form Missing";
      if (rule2.evidence.includes("Incident Description")) incidentStatus = "⚠ Incident Description Missing";
      if (rule2.evidence.includes("Evidence Document (FIR or Repair Estimate)")) {
        estimateStatus = "⚠ Repair Estimate Missing";
        firStatus = "⚠ FIR Missing";
      }
    }
    
    evidenceList.innerHTML = `
      <div class="evidence-item"><span class="${claimFormStatus.includes('✓') ? 'icon-check' : 'icon-warn'}">${claimFormStatus.charAt(0)}</span> ${claimFormStatus.substring(2)}</div>
      <div class="evidence-item"><span class="${estimateStatus.includes('✓') ? 'icon-check' : 'icon-warn'}">${estimateStatus.charAt(0)}</span> ${estimateStatus.substring(2)}</div>
      <div class="evidence-item"><span class="${firStatus.includes('✓') ? 'icon-check' : 'icon-warn'}">${firStatus.charAt(0)}</span> ${firStatus.substring(2)}</div>
      <div class="evidence-item"><span class="${incidentStatus.includes('✓') ? 'icon-check' : 'icon-warn'}">${incidentStatus.charAt(0)}</span> ${incidentStatus.substring(2)}</div>
    `;

    // 2. Policy Checks
    const policyBody = document.getElementById("policy-checks-body");
    policyBody.innerHTML = "";
    data.rule_results.forEach(rule => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${rule.rule_id}</td>
        <td><span class="badge ${rule.status.toLowerCase()}">${rule.status}</span></td>
        <td>${rule.finding}</td>
        <td>${rule.policy_clause}</td>
      `;
      policyBody.appendChild(tr);
    });

    // 3. Contradictions
    const contradictionsSection = document.getElementById("contradictions-section");
    const contradictionsList = document.getElementById("contradictions-list");
    contradictionsList.innerHTML = "";
    
    if (data.contradictions && data.contradictions.length > 0) {
      contradictionsSection.classList.remove("hidden");
      data.contradictions.forEach(c => {
        const div = document.createElement("div");
        div.className = "contradiction-card";
        div.innerHTML = `
          <div class="contradiction-header">CONTRADICTION</div>
          <div class="contradiction-title">${(c.field || "Unknown Field").replace(/_/g, " ").toUpperCase()}</div>
          <div class="contradiction-body">
            <div>
              <div class="doc-source">${c.document_a.source}</div>
              <div class="doc-value">${c.document_a.value}</div>
            </div>
            <div>
              <div class="doc-source">${c.document_b.source}</div>
              <div class="doc-value">${c.document_b.value}</div>
            </div>
          </div>
          <span class="investigation-tag">[Requires Investigation]</span>
          <div style="margin-top: 12px; font-size: 13px; color: var(--text-muted);">${c.explanation}</div>
        `;
        contradictionsList.appendChild(div);
      });
    } else {
      contradictionsSection.classList.add("hidden");
    }

    // 4. Findings
    const findingsList = document.getElementById("findings-list");
    findingsList.innerHTML = "";
    if (data.rule_results.length > 0) {
       data.rule_results.filter(r => r.evidence && r.evidence.length > 0).slice(0, 3).forEach(r => {
         const div = document.createElement("div");
         div.className = "finding-item";
         div.innerHTML = `
           <div class="finding-text">${r.finding}</div>
           <div class="finding-meta">Evidence: ${r.evidence.join(", ")} | Clause: ${r.policy_clause}</div>
         `;
         findingsList.appendChild(div);
       });
    } else {
       findingsList.innerHTML = '<div class="finding-meta">No specific findings logged.</div>';
    }

    // 5. Recommendation
    const recTitle = document.getElementById("rec-title");
    const recSummary = document.getElementById("rec-summary");
    const recClauses = document.getElementById("rec-clauses");
    const humanReviewContainer = document.getElementById("human-review-container");
    const humanReviewReason = document.getElementById("human-review-reason");
    
    recTitle.textContent = data.recommendation;
    recTitle.className = `rec-large rec-${data.recommendation.replace(" ", "-")}`;
    recSummary.textContent = data.summary_notes;
    
    if (data.applicable_clauses && data.applicable_clauses.length > 0) {
      recClauses.textContent = `Applicable clauses: ${data.applicable_clauses.map(c => c.clause_id).join(", ")}`;
    } else {
      recClauses.textContent = "";
    }

    // 6. Human Review
    if (data.escalate_to_human && data.escalation) {
      humanReviewContainer.classList.remove("hidden");
      humanReviewReason.innerHTML = `${data.escalation.reason}<br><strong style="color:#9a3412;">Action:</strong> ${data.escalation.human_action}`;
    } else {
      humanReviewContainer.classList.add("hidden");
    }
  }
});
