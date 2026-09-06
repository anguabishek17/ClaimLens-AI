# ClaimLens AI
## Insurance Claims Evidence Review Assistant

ClaimLens AI is a dual-engine reasoning system designed to automatically audit motor insurance claims by combining deterministic rules and semantic AI evaluation.

## 1. Overview
ClaimLens AI helps review motor insurance claims by analyzing submitted claim documents, checking policy rules, identifying missing evidence, detecting contradictions, and generating a structured review recommendation. The platform is designed to assist investigators rather than replace human decision-making, ensuring a thorough and fair evaluation of every claim.

## 2. Problem Statement
Insurance claim investigation often requires investigators to manually compare multiple documents, such as:
- Claim Forms
- Incident Descriptions
- FIR documents
- Repair Estimates
- Policy information

This process introduces several challenges:
- Missing documents delaying the process
- Unstructured and varied evidence formats
- Manual, time-consuming comparison
- Complex policy verification
- Cross-document inconsistencies that are hard to spot

## 3. Solution
ClaimLens AI streamlines the review process through a multi-stage approach:

Documents
↓
Evidence Extraction
↓
Policy Validation
↓
Consistency Analysis
↓
AI Reasoning
↓
Review Recommendation

Combining deterministic policy rules with AI semantic analysis ensures that hard constraints (like missing documents or strict deadlines) are rigidly enforced, while nuanced inconsistencies (like matching descriptions of an accident) are semantically evaluated by AI.

## 4. Key Features
- **Document Upload**: Supports uploading text documents (Claim Form, Incident Description, FIR, Repair Estimate).
- **Evidence Completeness Checking**: Automatically identifies required vs. optional evidence based on the claim type.
- **Policy Rule Validation**: Runs deterministic rule checks to enforce business logic (e.g., reporting windows, deductible thresholds, vehicle matching).
- **Cross-Document Consistency**: Detects conflicting information, such as date mismatches between a claim form and a repair bill.
- **AI-Assisted Semantic Analysis**: Uses Google Gemini to perform semantic searches over policy clauses and structure a comprehensive reasoning context.
- **Evidence-Backed Recommendation**: Synthesizes findings into a final recommendation supported by actual evidence and policy clauses.

## 5. How It Works
```text
Upload Documents
        ↓
Extract Evidence
        ↓
Check Completeness
        ↓
Run Policy Rules
        ↓
Compare Documents
        ↓
Semantic AI Analysis
        ↓
Generate Recommendation
```
- **Upload Documents**: User provides text-based claim documents via the UI.
- **Extract Evidence**: The system parses the semi-structured text.
- **Check Completeness**: Flags if mandatory documents are missing.
- **Run Policy Rules**: Evaluates hardcoded rules against the extracted data.
- **Compare Documents**: Uses an LLM task to detect inconsistencies across documents.
- **Semantic AI Analysis**: Retrieves relevant policy clauses and synthesizes context using Gemini.
- **Generate Recommendation**: Outputs a final decision state for the investigator.

## 6. System Architecture
```text
          Frontend (HTML/CSS/JS)
                    ↓
            FastAPI Backend
                    ↓
          Document Processing
                    ↓
          Policy Rule Engine
                    ↓
           Evidence Analysis
                    ↓
       Gemini Semantic Analysis
                    ↓
             Decision Engine
                    ↓
              Review Result
```

## 7. AI Architecture
- **Deterministic Layer**: Used for predictable policy and evidence checks, ensuring strict boundaries.
- **AI Layer**: Uses Google Gemini (`gemini-embedding-001` for vector embeddings and `gemini-1.5-flash` for LLM tasks) for semantic search and contextual contradiction detection.
- **Decision Layer**: Combines findings to produce one of the final recommendations:
  - **APPROVE**
  - **REQUEST INFORMATION**
  - **ESCALATE**

## 8. Decision Logic
| Decision | Meaning |
|---|---|
| **APPROVE** | Evidence and policy checks support the claim. |
| **REQUEST INFORMATION** | Required evidence is missing. |
| **ESCALATE** | Conflicting or uncertain evidence requires human investigation. |

*Escalation does not automatically indicate fraud.* It flags the claim as requiring a detailed human review.

## 9. Demonstration Scenarios
- **Scenario 1 — Normal Claim (Claim 001)**
  - Expected: **APPROVE**
  - Details: All documents present, dates align, and policy rules are met.

- **Scenario 2 — Missing Documents (Claim 002)**
  - Expected: **REQUEST INFORMATION**
  - Details: Missing mandatory repair estimates or FIRs.

- **Scenario 3 — Difficult Contradiction (Claim 003)**
  - Expected: **ESCALATE**
  - Details: Date and registration inconsistencies exist between the claim form and repair bill.

## 10. Application Modules
- **Home / Dashboard**: Overview of available claims and their statuses.
- **New Claim Review**: Interface to upload new claim documents and trigger analysis.
- **Demo Claims**: Pre-built scenarios to demonstrate the system's capabilities.
- **Evidence**: Displays the status of required vs. missing documents.
- **Policy**: View the loaded insurance policy clauses.
- **Settings**: Configuration overview.

## 11. Technology Stack
| Layer | Technology | Purpose |
|---|---|---|
| Frontend | HTML / CSS / JavaScript | Vanilla UI interface |
| Backend | Python 3.11 | Core logic application |
| API Framework | FastAPI | High-performance REST API |
| AI | Google Gemini | LLM processing (`gemini-1.5-flash`) |
| Embeddings | Gemini Embedding Model | Vector search (`gemini-embedding-001`) |
| Similarity Search | NumPy | Local semantic vector matching |

## 12. Project Structure
```text
.
├── app.py                   # Main entry point (FastAPI + Static UI)
├── requirements.txt         # Required dependencies
├── README.md                # Project documentation
├── backend/                 # API Routes, Models, Config, and Services
│   ├── rules/               # Deterministic rule engine
│   └── services/            # Document, Retrieval, and Gemini services
├── frontend/                # Vanilla HTML/CSS/JS interface (index.html, style.css, app.js)
└── data/                    # Sample claims, processed data, and policy files
```

## 13. Installation
1. Ensure Python 3.11+ is installed.
2. Clone the repository.
3. Install dependencies:
```bash
pip install -r requirements.txt
```

## 14. Configuration
Create a `.env` file in the root directory based on `.env.example`.
Required environment variable:
- `GEMINI_API_KEY`: Your Google Gemini API key.

*Never commit your secrets or actual API keys to Git.*

## 15. Running the Application
Start the application using:
```bash
python app.py
```
The backend API and the frontend dashboard will be served locally at:
[http://localhost:8000](http://localhost:8000)

## 16. API / Health Check
To verify the system is running, access the health endpoint:
```http
GET /api/health
```
**Expected Response:**
```json
{
  "status": "ok",
  "project": "ClaimLens AI"
}
```

## 17. Security & Reliability
- **Environment-based API keys**: Secrets are loaded securely via `.env`.
- **No hard-coded secrets**: Zero exposure of sensitive keys in the source code.
- **Graceful AI degradation**: Continues processing deterministic rules even if LLM insights fail.
- **Deterministic policy rules**: Prevents AI hallucinations from overriding hard boundaries.
- **Explainable findings**: Every AI decision is grounded in retrieved text.

## 18. Responsible AI
ClaimLens AI is an **investigator-assistance system**.
- It does not replace human investigators.
- It should not automatically accuse customers of fraud.
- Uncertain or conflicting cases are escalated for human review.
- AI-generated findings should be treated as decision support and reviewed appropriately.

## 19. Future Enhancements
- *FUTURE:* OCR for scanned documents
- *FUTURE:* More document formats (PDF, images)
- *FUTURE:* Advanced policy retrieval and agentic reasoning
- *FUTURE:* Claim history analysis
- *FUTURE:* Investigator feedback loops
- *FUTURE:* Audit trails for compliance
- *FUTURE:* Role-based access control
- *FUTURE:* Production database integration
- *FUTURE:* Cloud deployment architecture

## 20. Demo Video
## 🎥 Demo
Demo Video:
[ADD DEMO VIDEO LINK HERE]

**Recommended demonstration flow:**
1. Open ClaimLens AI
2. Start New Claim Review
3. Upload claim documents
4. Analyze the claim
5. Review evidence status
6. Review policy checks
7. Show APPROVE scenario (Claim 001)
8. Show REQUEST INFORMATION scenario (Claim 002)
9. Show ESCALATE scenario (Claim 003)

## 21. Hackathon Value Proposition
- **Evidence First**: Decisions are rigidly grounded in provided claim evidence.
- **Hybrid Intelligence**: Effectively combines deterministic policy rules with semantic AI analysis to cover both hard boundaries and nuanced contradictions.
- **Explainability**: Findings and recommendations are directly connected to extracted evidence and specific policy clauses.
- **Human-in-the-Loop**: The system knows its limits—difficult or contradictory cases are securely escalated.
- **Operational Efficiency**: Reduces repetitive manual document comparison, allowing investigators to focus on complex cases.

## 22. Project Status
| Component | Status |
|---|---|
| Frontend | 🟢 Active |
| Backend | 🟢 Active |
| Document Upload | 🟢 Active |
| Evidence Processing | 🟢 Active |
| Policy Rules | 🟢 Active |
| Gemini Integration | 🟢 Active |
| Contradiction Detection | 🟢 Active |
| Demo Scenarios | 🟢 Active |
| Health Check | 🟢 Active |
| Local Deployment | 🟢 Active |

## 23. Team
- **Project**: ClaimLens AI
- **Track**: PS02
- **Domain**: Insurance / InsurTech

## 24. License
This project is built for the hackathon and is provided as-is. See the LICENSE file for details if available.
