# ClaimLens AI

## What the project does
ClaimLens AI is a dual-engine reasoning system designed to automatically audit motor insurance claims. It reads and extracts information from unstructured claim forms, repair estimates, and First Information Reports (FIR). It then evaluates the data using strict deterministic policy rules and a semantic AI evaluation pipeline (Gemini RAG) to detect contradictions and verify evidence completeness. The platform automatically outputs recommendations to either APPROVE, REJECT, REQUEST INFORMATION, or ESCALATE to a human investigator.

## Problem Statement
Insurance claim verification is historically a manual, slow, and error-prone process. The challenge was to build an intelligent assistant that cross-references user-submitted claim documents against the official policy clauses to surface discrepancies and ensure all critical documentation is available, drastically reducing manual review times while ensuring fairness. 

## Architecture
The system employs a strict separation of concerns:
1. **Document Extraction:** Parses semi-structured text.
2. **Retrieval-Augmented Generation (RAG):** Local vector search over policy documents using `gemini-embedding-001`.
3. **Deterministic Rule Engine:** Hardcoded business logic checks against extracted structured parameters (e.g., matching vehicle registrations and time windows).
4. **Contradiction Engine:** LLM-based semantic checks across multiple documents.
5. **Escalation Orchestrator:** Synthesizes results and determines whether human intervention is required, ensuring fraud is not explicitly accused but flagged as a "potential inconsistency".

## Technology Stack
- **Backend:** Python 3.11, FastAPI
- **Frontend:** Vanilla JS, HTML5, CSS3 (No external build tools needed)
- **AI/LLM:** Google Gemini API (`gemini-1.5-flash`, `gemini-embedding-001`) via `google-genai`
- **Data:** Local filesystem storage (no complex DB dependencies)

## How to Run
1. Ensure Python 3.11 is installed.
2. Clone the repository and install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set your environment variables in `.env` (or let it run in fallback mode).
4. Start the application:
   ```bash
   python app.py
   ```
5. Open your browser to `http://localhost:8000/`.

## Environment Variables
The application looks for a `.env` file at the root. The required variable is:
- `GEMINI_API_KEY`: Your Google Gemini API key.

No API keys are committed to this repository. If the key is missing, the application will degrade gracefully and continue processing deterministic rules without LLM insights.

## Data and Documents
Data is loaded from the `data/` directory, containing sample claim scenarios (`claim_001`, `claim_002`, `claim_003`). Each claim includes:
- Claim Form
- Incident Description
- Repair Estimate or FIR
- Policy Documents

## AI / RAG Pipeline
The pipeline generates vector embeddings for policy clauses using `gemini-embedding-001`. Incoming claim evidence is embedded and matched using cosine similarity. The retrieved policy clauses are then injected into a prompt for `gemini-1.5-flash` to execute a final structured analysis of the evidence context.

## Deterministic Rule Engine
The application enforces policy guidelines using hardcoded deterministic rules, ensuring the AI cannot hallucinate critical boundaries. Rules cover reporting windows, documentation completeness, deductible thresholds, and vehicle registration matching.

## Contradiction Detection
An independent LLM task processes the documents strictly to identify inconsistencies (e.g., date mismatches between a claim form and a repair bill). Discrepancies are highlighted visually without fabricating assumptions. 

## Human Escalation
Uncertain cases, missing critical information, or severe contradictions trigger a formal escalation pathway. The system will explicitly flag the claim for "Human investigator review required" and detail the exact reason.

## Demo Scenarios
The UI provides 3 pre-built scenarios based on the `data/claims/` directory:
1. **Claim 001 (Normal):** Everything matches. Recommendation: APPROVE.
2. **Claim 002 (Missing Documents):** Missing mandatory repair estimates/FIRs. Recommendation: REQUEST INFORMATION.
3. **Claim 003 (Contradiction):** Date and registration inconsistencies exist. Recommendation: ESCALATE (Review required).

## API Endpoints
- `GET /api/health`: Health status.
- `GET /api/health/gemini`: Gemini connection status.
- `POST /api/claims/review`: Accepts structured claim text payloads and returns the comprehensive audit report and recommendation.

## Project Structure
```
.
├── app.py                   # Main entry point (FastAPI + Static UI)
├── requirements.txt         # Required dependencies
├── README.md                # Project documentation
├── backend/                 # API Routes, Models, and Services
│   ├── rules/               # Deterministic rule engine
│   └── services/            # Retrieval, Gemini, and Analysis services
├── frontend/                # Vanilla HTML/CSS/JS interface
└── data/                    # Sample claims and policy data
```

## Demo Video
[Link to Demo Video]
