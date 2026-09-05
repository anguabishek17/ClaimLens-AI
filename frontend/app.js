document.addEventListener("DOMContentLoaded", () => {

  // ============================================================
  // ELEMENT REFERENCES
  // ============================================================
  const claimSelect = document.getElementById("claim-select");
  const btnLoadClaim = document.getElementById("btn-load-claim");
  
  const resultsContainer = document.getElementById("results-container");
  const errorContainer = document.getElementById("error-container");
  const loadingOverlay = document.getElementById("loading-overlay");

  // ============================================================
  // DEMO CLAIM DATA (existing — unmodified)
  // ============================================================
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

  // ============================================================
  // DEMO CLAIMS: Load Claim Button (existing — unmodified)
  // ============================================================
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

  // ============================================================
  // DEMO CLAIMS: Render Results (existing — unmodified)
  // ============================================================
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

  // ============================================================
  // NAVIGATION & VIEW MANAGEMENT
  // ============================================================
  const navItems = document.querySelectorAll(".nav-item");
  const views = document.querySelectorAll(".view");

  function switchView(targetId) {
    navItems.forEach(n => n.classList.remove("active"));
    const activeNav = document.querySelector(`[data-target="${targetId}"]`);
    if (activeNav) activeNav.classList.add("active");

    views.forEach(v => {
      if (v.id === targetId) {
        v.classList.remove("hidden");
      } else {
        v.classList.add("hidden");
      }
    });

    // Load data if needed
    if (targetId === "view-dashboard") loadDashboard();
    if (targetId === "view-evidence") loadEvidence();
    if (targetId === "view-policy") loadPolicy();
    if (targetId === "view-settings") loadSettings();
  }

  navItems.forEach(item => {
    item.addEventListener("click", () => {
      const targetId = item.getAttribute("data-target");
      switchView(targetId);
    });
  });

  // ============================================================
  // HOME PAGE CTAs
  // ============================================================
  document.getElementById("btn-start-review").addEventListener("click", () => {
    switchView("view-upload");
  });

  document.getElementById("btn-view-demo").addEventListener("click", () => {
    switchView("view-claims");
  });

  // ============================================================
  // DEMO CARD QUICK LINKS (landing page)
  // ============================================================
  ["001", "002", "003"].forEach(claimId => {
    const btn = document.getElementById(`btn-demo-clm${claimId}`);
    if (btn) {
      btn.addEventListener("click", () => {
        const select = document.getElementById("claim-select");
        if (select) select.value = claimId;
        switchView("view-claims");
      });
    }
  });

  // Final CTA button
  const btnFinalCta = document.getElementById("btn-final-cta");
  if (btnFinalCta) {
    btnFinalCta.addEventListener("click", () => switchView("view-upload"));
  }

  // Footer navigation links
  document.querySelectorAll(".lp-footer-link[data-nav]").forEach(btn => {
    btn.addEventListener("click", () => {
      const target = btn.getAttribute("data-nav");
      if (target) switchView(target);
    });
  });

  // ============================================================
  // RESULT PAGE ACTION BUTTONS
  // ============================================================
  document.getElementById("btn-result-new-review").addEventListener("click", () => {
    switchView("view-upload");
  });

  document.getElementById("btn-result-dashboard").addEventListener("click", () => {
    switchView("view-dashboard");
  });

  // ============================================================
  // UPLOAD CANCEL BUTTON
  // ============================================================
  document.getElementById("btn-upload-cancel").addEventListener("click", () => {
    switchView("view-home");
  });

  // ============================================================
  // FILE UPLOAD LOGIC
  // ============================================================

  // State tracking
  const uploadedFiles = {
    claim_form: null,
    incident_description: null,
    fir: null,
    repair_estimate: null
  };

  const ZONE_CONFIG = [
    { zoneId: "zone-claim-form",  inputId: "file-claim-form", statusId: "status-claim-form", docType: "claim_form",            required: true  },
    { zoneId: "zone-incident",    inputId: "file-incident",   statusId: "status-incident",   docType: "incident_description",  required: true  },
    { zoneId: "zone-fir",        inputId: "file-fir",         statusId: "status-fir",        docType: "fir",                   required: false },
    { zoneId: "zone-repair",     inputId: "file-repair",      statusId: "status-repair",     docType: "repair_estimate",       required: false }
  ];

  ZONE_CONFIG.forEach(cfg => {
    const zone  = document.getElementById(cfg.zoneId);
    const input = document.getElementById(cfg.inputId);
    const status = document.getElementById(cfg.statusId);

    // Click on zone triggers file input
    zone.addEventListener("click", (e) => {
      if (e.target !== input) input.click();
    });

    // Drag-and-drop
    zone.addEventListener("dragover", (e) => {
      e.preventDefault();
      zone.classList.add("drag-over");
    });
    zone.addEventListener("dragleave", () => zone.classList.remove("drag-over"));
    zone.addEventListener("drop", (e) => {
      e.preventDefault();
      zone.classList.remove("drag-over");
      const file = e.dataTransfer.files[0];
      if (file) handleFileSelected(file, cfg, zone, status);
    });

    // File input change
    input.addEventListener("change", () => {
      const file = input.files[0];
      if (file) handleFileSelected(file, cfg, zone, status);
    });
  });

  function handleFileSelected(file, cfg, zone, statusEl) {
    uploadedFiles[cfg.docType] = file;
    zone.classList.add("has-file");
    statusEl.textContent = file.name;
    checkSubmitEnabled();
  }

  function checkSubmitEnabled() {
    const requiredFilled = ZONE_CONFIG
      .filter(c => c.required)
      .every(c => uploadedFiles[c.docType] !== null);
    
    document.getElementById("btn-upload-submit").disabled = !requiredFilled;
  }

  // Convert File to base64
  function fileToBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        // result is "data:<type>;base64,<data>" — strip prefix
        const b64 = reader.result.split(",")[1];
        resolve(b64);
      };
      reader.onerror = reject;
      reader.readAsDataURL(file);
    });
  }

  // Animated progress steps
  const PROGRESS_STEP_DELAYS = [300, 1400, 2600, 3800, 5000];

  function startProgressAnimation() {
    const steps = document.querySelectorAll(".progress-step");
    // Reset all
    steps.forEach(s => { s.classList.remove("active", "done"); });
    steps[0].classList.add("active");

    let currentStep = 0;
    const timers = [];

    PROGRESS_STEP_DELAYS.forEach((delay, i) => {
      const t = setTimeout(() => {
        if (i > 0) steps[i - 1].classList.replace("active", "done");
        if (i < steps.length) steps[i].classList.add("active");
        currentStep = i;
      }, delay);
      timers.push(t);
    });

    return () => timers.forEach(t => clearTimeout(t));
  }

  // Submit upload form
  document.getElementById("btn-upload-submit").addEventListener("click", async () => {
    const claimType = document.getElementById("upload-claim-type").value;

    // Show progress overlay
    const overlay = document.getElementById("upload-progress-overlay");
    overlay.classList.remove("hidden");
    const cancelAnimation = startProgressAnimation();

    try {
      // Build file list
      const filesPayload = [];

      for (const cfg of ZONE_CONFIG) {
        const file = uploadedFiles[cfg.docType];
        if (!file) continue;
        const b64 = await fileToBase64(file);
        filesPayload.push({
          filename: file.name,
          content_b64: b64,
          document_type: cfg.docType
        });
      }

      const payload = {
        claim_type: claimType,
        files: filesPayload
      };

      const res = await fetch("/api/review/upload", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });

      cancelAnimation();
      overlay.classList.add("hidden");

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: `Server error ${res.status}` }));
        throw new Error(err.detail || `Server returned ${res.status}`);
      }

      const data = await res.json();
      renderUploadResult(data);
      switchView("view-result");

    } catch (err) {
      cancelAnimation();
      overlay.classList.add("hidden");
      alert(`Upload failed: ${err.message}`);
    }
  });

  // ============================================================
  // RESULT PAGE RENDERER
  // ============================================================
  function renderUploadResult(data) {
    const rec = data.recommendation || "UNKNOWN";
    const recSlug = rec.replace(/\s+/g, "-");

    // Hero banner
    const hero = document.getElementById("result-hero");
    hero.className = `result-hero rec-${recSlug}`;

    document.getElementById("result-claim-id").textContent = `Claim ID: ${data.claim_id}`;
    document.getElementById("result-recommendation-text").textContent = rec;
    document.getElementById("result-verdict-badge").textContent = rec;
    document.getElementById("result-summary-text").textContent = data.summary_notes || "";

    // Summary section
    document.getElementById("r-claim-id").textContent = data.claim_id;
    document.getElementById("r-recommendation").innerHTML = `<span class="rec-${recSlug}" style="font-weight:700;">${rec}</span>`;
    document.getElementById("r-escalate").textContent = data.escalate_to_human ? "Yes" : "No";

    // Document Status
    const docStatusList = document.getElementById("r-document-status");
    docStatusList.innerHTML = "";
    if (data.document_completeness && data.document_completeness.length > 0) {
      data.document_completeness.forEach(doc => {
        const div = document.createElement("div");
        let cls = "result-doc-status-item";
        let icon = "";
        if (!doc.is_present) {
          cls += " missing"; icon = "✗";
        } else if (!doc.is_sufficient) {
          cls += " insufficient"; icon = "⚠";
        } else {
          cls += " present"; icon = "✓";
        }
        div.className = cls;
        div.innerHTML = `<strong>${icon}</strong> ${doc.document_name}${doc.notes ? `<span style="font-size:12px;color:inherit;margin-left:8px;opacity:0.75;">${doc.notes}</span>` : ""}`;
        docStatusList.appendChild(div);
      });
    } else {
      docStatusList.innerHTML = `<div style="color:var(--text-muted);font-size:14px;">No document status available.</div>`;
    }

    // Policy Checks
    const policyBody = document.getElementById("r-policy-checks-body");
    policyBody.innerHTML = "";
    (data.rule_results || []).forEach(rule => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${rule.rule_id}</strong></td>
        <td><span class="badge ${rule.status.toLowerCase()}">${rule.status}</span></td>
        <td style="font-size:13px;">${rule.finding}</td>
        <td style="font-size:12px;color:var(--text-muted);">${rule.policy_clause}</td>
      `;
      policyBody.appendChild(tr);
    });

    // Contradictions
    const contrList = document.getElementById("r-contradictions-list");
    const contrSection = document.getElementById("r-contradictions-section");
    contrList.innerHTML = "";
    const contradictions = data.contradictions || [];

    if (contradictions.length > 0) {
      contrSection.style.display = "";
      contradictions.forEach(c => {
        const severityHtml = c.severity
          ? `<span class="severity-badge ${c.severity}">${c.severity}</span>`
          : "";
        const div = document.createElement("div");
        div.className = "contradiction-card";
        div.innerHTML = `
          <div class="contradiction-header">CONTRADICTION ${severityHtml}</div>
          <div class="contradiction-title">${(c.field || "Unknown").replace(/_/g, " ").toUpperCase()}</div>
          <div class="contradiction-body">
            <div>
              <div class="doc-source">${c.document_a?.source || "Document A"}</div>
              <div class="doc-value">${c.document_a?.value || "—"}</div>
            </div>
            <div>
              <div class="doc-source">${c.document_b?.source || "Document B"}</div>
              <div class="doc-value">${c.document_b?.value || "—"}</div>
            </div>
          </div>
          <span class="investigation-tag">Requires Investigation</span>
          <div style="margin-top:10px;font-size:13px;color:var(--text-muted);">${c.explanation || ""}</div>
        `;
        contrList.appendChild(div);
      });
    } else {
      contrSection.style.display = "";
      contrList.innerHTML = `<div style="color:var(--status-pass);font-weight:600;font-size:14px;">✓ No contradictions detected across documents.</div>`;
    }

    // Evidence Findings
    const evidenceDiv = document.getElementById("r-evidence-findings");
    evidenceDiv.innerHTML = "";
    const findings = data.evidence_findings || [];
    if (findings.length > 0) {
      findings.forEach(f => {
        const div = document.createElement("div");
        div.className = "result-evidence-item";
        div.innerHTML = `
          <div class="result-evidence-category">${f.category || ""}</div>
          <div class="result-evidence-observation">${f.observation || ""}</div>
          <div class="result-evidence-meta">Source: ${f.source_document || "—"}${f.policy_clause_ref ? ` | Clause: ${f.policy_clause_ref}` : ""}</div>
        `;
        evidenceDiv.appendChild(div);
      });
    } else {
      evidenceDiv.innerHTML = `<div style="color:var(--text-muted);font-size:14px;">No specific evidence findings logged.</div>`;
    }

    // Applicable Clauses
    const clausesDiv = document.getElementById("r-applicable-clauses");
    clausesDiv.innerHTML = "";
    const clauses = data.applicable_clauses || [];
    if (clauses.length > 0) {
      clauses.forEach(c => {
        const impact = c.impact || "NOT_APPLICABLE";
        const div = document.createElement("div");
        div.className = "result-clause-item";
        div.innerHTML = `
          <div class="result-clause-header">
            <span class="result-clause-id">${c.clause_id}</span>
            <span class="impact-badge ${impact}">${impact.replace("_", " ")}</span>
          </div>
          <div class="result-clause-title">${c.clause_title || ""}</div>
          <div class="result-clause-reasoning">${c.reasoning || ""}</div>
        `;
        clausesDiv.appendChild(div);
      });
    } else {
      clausesDiv.innerHTML = `<div style="color:var(--text-muted);font-size:14px;">No applicable policy clauses identified.</div>`;
    }

    // Escalation
    const escSection = document.getElementById("r-escalation-section");
    const escDetails = document.getElementById("r-escalation-details");
    escSection.style.display = "";

    if (data.escalate_to_human && data.escalation) {
      const esc = data.escalation;
      const priorityClass = esc.priority || "MEDIUM";
      escDetails.className = "result-escalation-box";
      escDetails.innerHTML = `
        <span class="result-priority-badge ${priorityClass}">${priorityClass} PRIORITY</span>
        <div class="result-escalation-reason">${esc.reason || "Escalation required."}</div>
        <div class="result-escalation-action"><strong>Recommended Action:</strong> ${esc.human_action || "Manual review needed."}</div>
      `;
    } else {
      escDetails.className = "result-escalation-box hidden-box";
      escDetails.innerHTML = `<div style="color:var(--text-muted);font-size:14px;">✓ No human escalation required for this claim.</div>`;
    }
  }

  // ============================================================
  // DASHBOARD
  // ============================================================
  async function loadDashboard() {
    try {
      const res = await fetch("/api/claims");
      if (!res.ok) throw new Error("Failed to load claims");
      const data = await res.json();
      
      const claims = data.claims || [];
      
      let pendingCount = 0;
      let missingCount = 0;
      let escalatedCount = 0;
      
      const tbody = document.getElementById("dash-claims-body");
      tbody.innerHTML = "";
      
      claims.forEach(c => {
        if (c.status === "REQUEST INFORMATION") missingCount++;
        else if (c.status === "ESCALATION") escalatedCount++;
        else if (c.status === "REVIEW") pendingCount++;
        
        let badgeClass = "unknown";
        if (c.status === "APPROVE") badgeClass = "pass";
        if (c.status === "ESCALATION") badgeClass = "fail";
        
        const tr = document.createElement("tr");
        tr.className = "clickable-row";
        tr.innerHTML = `
          <td><strong>${c.id}</strong></td>
          <td>${c.name.split(" ")[0]} (Customer)</td>
          <td>${c.vehicle_type}</td>
          <td>${c.incident_type}</td>
          <td>Rs. ${c.claimed_amount.toLocaleString()}</td>
          <td><span class="badge ${badgeClass}">${c.status}</span></td>
          <td><button class="btn" style="padding: 4px 8px; font-size: 12px;">Review</button></td>
        `;
        
        tr.addEventListener("click", () => {
          // Navigate to Claims view
          switchView("view-claims");
          
          // Select claim and load
          let optVal = c.id.replace("CLM-", "").replace("SAMPLE-", "").replace(/^0+/, "");
          optVal = optVal.padStart(3, "0"); // pad to 001, 002, etc.
          
          // Fallback if not exactly 001, 002, 003
          if (claimSelect.querySelector(`option[value="${optVal}"]`)) {
             claimSelect.value = optVal;
          } else {
             if(c.id.includes("01")) claimSelect.value = "001";
             if(c.id.includes("02")) claimSelect.value = "002";
             if(c.id.includes("03")) claimSelect.value = "003";
          }
          btnLoadClaim.click();
        });
        
        tbody.appendChild(tr);
      });
      
      document.getElementById("dash-total-claims").textContent = claims.length;
      document.getElementById("dash-pending-claims").textContent = pendingCount || 1;
      document.getElementById("dash-missing-claims").textContent = missingCount || 1;
      document.getElementById("dash-escalated-claims").textContent = escalatedCount || 1;
      
    } catch (err) {
      console.error(err);
    }
  }

  // ============================================================
  // EVIDENCE
  // ============================================================
  async function loadEvidence() {
    try {
      const res = await fetch("/api/evidence");
      if (!res.ok) throw new Error("Failed to load evidence");
      const data = await res.json();
      
      const listContainer = document.getElementById("evidence-explorer-list");
      listContainer.innerHTML = "";
      
      data.evidence.forEach(item => {
        const div = document.createElement("div");
        div.className = "evidence-explorer-item";
        
        let icon = item.status === "Available" ? "✓" : "⚠";
        let color = item.status === "Available" ? "var(--status-pass)" : "var(--status-unknown)";
        
        div.innerHTML = `
          <div class="evidence-explorer-item-title"><span style="color: ${color}; font-weight: bold; margin-right: 6px;">${icon}</span>${item.document_type}</div>
          <div class="evidence-explorer-item-meta">${item.claim_id} • ${item.status}</div>
        `;
        
        div.addEventListener("click", () => {
          document.querySelectorAll(".evidence-explorer-item").forEach(el => el.classList.remove("active"));
          div.classList.add("active");
          
          const detail = document.getElementById("evidence-detail-content");
          if (item.status === "Missing") {
             detail.innerHTML = `<p style="color: var(--status-unknown);">This document is missing or unavailable.</p>`;
          } else {
             detail.innerHTML = `
               <div style="margin-bottom: 12px; font-weight: bold; font-size: 16px;">${item.document_type} (${item.claim_id})</div>
               <div style="background-color: var(--bg-color); padding: 16px; border-radius: 6px; border: 1px solid var(--border-color); font-family: monospace; white-space: pre-wrap; font-size: 13px;">${item.content}</div>
             `;
          }
        });
        
        listContainer.appendChild(div);
      });
      
    } catch (err) {
      console.error(err);
    }
  }

  // ============================================================
  // POLICY
  // ============================================================
  let allClauses = [];
  async function loadPolicy() {
    try {
      const res = await fetch("/api/policy");
      if (!res.ok) throw new Error("Failed to load policy");
      const data = await res.json();
      
      allClauses = data.clauses || [];
      
      // Populate categories
      const categories = new Set();
      allClauses.forEach(c => categories.add(c.category));
      
      const categorySelect = document.getElementById("policy-category");
      categorySelect.innerHTML = '<option value="all">All Categories</option>';
      categories.forEach(cat => {
        const opt = document.createElement("option");
        opt.value = cat;
        opt.textContent = cat.replace(/_/g, " ").toUpperCase();
        categorySelect.appendChild(opt);
      });
      
      renderPolicy();
      
    } catch (err) {
      console.error(err);
    }
  }
  
  function renderPolicy() {
    const searchVal = document.getElementById("policy-search").value.toLowerCase();
    const catVal = document.getElementById("policy-category").value;
    
    const container = document.getElementById("policy-clauses-container");
    container.innerHTML = "";
    
    const filtered = allClauses.filter(c => {
      const matchesSearch = c.title.toLowerCase().includes(searchVal) || c.text.toLowerCase().includes(searchVal);
      const matchesCat = catVal === "all" || c.category === catVal;
      return matchesSearch && matchesCat;
    });
    
    filtered.forEach(c => {
      const div = document.createElement("div");
      div.className = "policy-clause-card";
      div.innerHTML = `
        <div class="policy-clause-header">
          <span class="policy-clause-id">${c.clause_id}</span>
          <span class="policy-clause-category">${c.category.replace(/_/g, " ")}</span>
        </div>
        <div class="policy-clause-title" style="margin-bottom: 8px;">${c.title}</div>
        <div class="policy-clause-text">${c.text}</div>
        <div style="margin-top: 12px; font-size: 12px; color: var(--text-muted);">
          <strong>Requirements:</strong> ${c.supporting_evidence_requirements.join(", ")}
        </div>
      `;
      container.appendChild(div);
    });
  }
  
  document.getElementById("policy-search").addEventListener("input", renderPolicy);
  document.getElementById("policy-category").addEventListener("change", renderPolicy);

  // ============================================================
  // SETTINGS
  // ============================================================
  async function loadSettings() {
    document.getElementById("status-backend").textContent = "Checking...";
    document.getElementById("status-policy").textContent = "Checking...";
    document.getElementById("status-claims").textContent = "Checking...";
    document.getElementById("status-gemini").textContent = "Checking...";
    document.getElementById("status-api-key").textContent = "Checking...";
    
    try {
      const res = await fetch("/api/health");
      const health = await res.json();
      document.getElementById("status-backend").innerHTML = `<span style="color: var(--status-pass)">✓ Connected</span>`;
      document.getElementById("status-policy").innerHTML = `<span style="color: var(--status-pass)">✓ Loaded</span>`;
      document.getElementById("status-claims").innerHTML = `<span style="color: var(--status-pass)">✓ Loaded</span>`;
    } catch {
      document.getElementById("status-backend").innerHTML = `<span style="color: var(--status-fail)">⚠ Disconnected</span>`;
      document.getElementById("status-policy").innerHTML = `<span style="color: var(--status-fail)">⚠ Failed</span>`;
      document.getElementById("status-claims").innerHTML = `<span style="color: var(--status-fail)">⚠ Failed</span>`;
    }
    
    try {
      const res = await fetch("/api/health/gemini");
      const gemini = await res.json();
      if (gemini.status === "ok") {
        document.getElementById("status-gemini").innerHTML = `<span style="color: var(--status-pass)">✓ Available</span>`;
        document.getElementById("status-api-key").innerHTML = `<span style="color: var(--status-pass)">● Configured</span>`;
      } else {
        document.getElementById("status-gemini").innerHTML = `<span style="color: var(--status-unknown)">⚠ Not configured</span>`;
        document.getElementById("status-api-key").innerHTML = `<span style="color: var(--status-unknown)">○ Not configured</span>`;
      }
    } catch {
      document.getElementById("status-gemini").innerHTML = `<span style="color: var(--status-fail)">⚠ Error</span>`;
      document.getElementById("status-api-key").innerHTML = `<span style="color: var(--status-fail)">Error</span>`;
    }
  }
  
  document.getElementById("btn-refresh-status").addEventListener("click", loadSettings);

  // ============================================================
  // INITIAL VIEW — Default to Home
  // ============================================================
  switchView("view-home");
});
