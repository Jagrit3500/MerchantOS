# 🛡️ MerchantOS: Autonomous Multi-Agent Settlement & Compliance Recovery Copilot

> **Track 3: AI Revenue Recovery** | *Built for Indian MSMEs & Merchants operating on Payment Aggregators (Razorpay)*

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/frontend-Streamlit-FF4B4B.svg)](https://streamlit.io/)
[![ChromaDB](https://img.shields.io/badge/vector--db-ChromaDB-purple.svg)](https://www.trychroma.com/)
[![Gemini 2.5](https://img.shields.io/badge/LLM-Gemini%202.5%20Flash-4285F4.svg)](https://ai.google.dev/)
[![RBI PA 2025 Compliant](https://img.shields.io/badge/regulatory-RBI%20PA%202025%20%7C%20Ombudsman%202021-green.svg)](https://www.rbi.org.in/)

---

## 📌 Executive Summary & Problem Statement

Indian merchants—especially fast-growing D2C brands, freelancers, and small businesses—frequently encounter sudden settlement holds, unexplained fee deductions, and frozen settlement accounts on payment aggregators like Razorpay.

When holds happen:
- **Merchants are kept in the dark**: Generic support tickets take weeks, citing vague 'risk parameters' with no actionable remediation steps.
- **Working capital is paralyzed**: Up to weeks of revenue remain trapped in escrow accounts, causing payroll and inventory defaults.
- **Fee variances go unnoticed**: Hidden interchange rates, GST rounding discrepancies, and MDR variance leak significant margin.
- **Appeals lack legal grounding**: Merchants submit angry emails instead of legally grounded complaints referencing the **RBI Master Directions on Payment Aggregators (effective September 2025)** and **Card Network Rules (Visa VDMP / Mastercard ECP)**.

**MerchantOS** solves this by acting as an **Autonomous Merchant Compliance & Settlement Resolution Copilot**. It audits merchant transactions, diagnoses fund holds, detects fee leakage, generates audit-ready resolution dossiers, and drafts legally airtight escalation notices—transforming trapped capital into recovered cash flow.

---

## 🚀 Live Demonstration: ₹94,688.00 Trapped Capital Action Card

In our live sample portfolio, MerchantOS instantly flags and segregates:
- **₹75,000.00**: High-risk ticket KYC hold pending In-Person Verification (IPV).
- **₹18,500.00**: Escrow settlement delay past statutory T+2 TAT.
- **₹1,188.00**: Unauthorized MDR fee variance and GST over-deduction.
- **Total Immediate Actionable Value**: **₹94,688.00**

---

## 🏛️ System Architecture

`mermaid
graph TD
    A[Merchant Data & Policy Inputs] --> B[Unified Home Command Center :8501]
    
    subgraph Multi-Agent Ecosystem
        B --> C[Agent 1: KYC & Fund Hold Copilot :8502]
        B --> D[Agent 2: Settlement Reconciliation Copilot :8503]
        B --> E[Agent 3: Regulatory Escalation Copilot :8504]
    end

    subgraph RAG & Policy Grounding Engine
        F[(ChromaDB Vector Store)] -->|RBI PA 2025 Directions| C
        F -->|Razorpay Merchant Agreements| C
        F -->|Visa VDMP / Mastercard ECP Rules| D
        F -->|RBI Integrated Ombudsman Scheme 2021| E
        G[Google Gemini 2.5 Flash] <--> F
    end

    C --> H[Resolution Dossier & Razorpay Support Ticket]
    D --> I[Arithmetic Balance Audit & Fee Variance Dispute]
    E --> J[Nodal Officer & RBI Ombudsman Legal Notice]
`

---

## 🤖 The Three Specialized Copilots

### 1️⃣ Agent 1: KYC & Fund Hold Diagnosis Copilot (Port 8502)
*Automates diagnosis of frozen accounts, classifies risk tiers, and builds audit-ready compliance dossiers.*
- **Dynamic Risk Scoring**: Evaluates business structure, GST registration, high-ticket transactions, and dispute volume to calculate an audit risk score (0-100).
- **Evidence Checklist Builder**: Generates precise required documentation (e.g., GST Certificate, Cancelled Cheque, In-Person Verification video script).
- **Automated Ticket Drafter**: Formats structured support tickets citing Razorpay Merchant Onboarding norms.
- **🛡️ Statutory Guardrail Refusal**: If a merchant refuses statutory obligations (e.g., refuses mandatory In-Person Verification under RBI Master Direction 2025), Agent 1 **honestly refuses** to generate false evasion appeals and guides the merchant to proper compliance.

### 2️⃣ Agent 2: Settlement Reconciliation & Fee Variance Auditor (Port 8503)
*Line-by-line financial audit comparing gross transactions against settled payouts and agreed MDR.*
- **Multi-Issue Transaction Deduplication**: Combines overlapping issues (e.g., a transaction that is both ON HOLD and has a FEE VARIANCE) into a single grouped record with stacked badges—eliminating double-counting.
- **Deterministic Arithmetic Balance Strip**:
  Gross Volume = Settled + Held/Pending + Fees & Tax + Fee Variance (✓ Reconciled)
- **Settlement Health Index**:
  Health Index = 100 - (Hold Deductions + TAT Penalties + Fee Discrepancies)
- **Audit-Ready Dispute Notice**: Formats itemized dispute tables with expected vs. charged MDR percentages ready for settlement dispute teams.

### 3️⃣ Agent 3: Regulatory Escalation & Ombudsman Copilot (Port 8504)
*Structured legal escalations adhering to the 3-Tier Grievance Redressal Framework.*
- **Tier 1**: Level 1 Support Escalation with Razorpay Ticket ID reference.
- **Tier 2**: Razorpay Principal Nodal Officer (PNO) Formal Notice (citing Clause 13.2 Grievance Redressal).
- **Tier 3**: RBI Integrated Ombudsman Scheme (2021) Form Draft.
- **⚖️ Commercial Decision Exclusion Grounding**: Adheres to Clause 10 of the RBI Ombudsman Scheme. Rather than arguing aggregators subjective commercial risk appetite, appeals are anchored strictly to **procedural defaults**:
  - Failure to provide mandatory 24-hour prior written notice before freezing funds.
  - Failure to communicate specific compliance deficiencies within statutory TAT.
  - Breach of T+2 settlement transfer rules without recorded regulatory orders.

---

## 🔍 Verified Regulatory Grounding

MerchantOS does **not** rely on unverified claims or LLM hallucinations:
| Claim / Metric | Regulatory Source & Grounding |
| :--- | :--- |
| **0.5% Chargeback Cap (Myth)** | **Corrected**: The 0.5% statutory cap was an ungrounded myth. In MerchantOS, chargeback thresholds are strictly mapped to Card Network rules: **Visa Dispute Monitoring Program (VDMP at 0.9%)** and **Mastercard Excessive Chargeback Program (ECP at 1.0%)**. |
| **Settlement Escrow Timelines** | **RBI Master Directions on Payment Aggregators (Sept 2025)**: Escrow settlement cycles mandate funds to be credited to merchant bank accounts within statutory T+2 cycles unless held under written compliance notice. |
| **Ombudsman Jurisdiction** | **RBI Integrated Ombudsman Scheme (2021)**: Complaints are framed around procedural lapses (absence of written notification, TAT violation) to comply with Scheme exclusions regarding commercial discretion. |

---

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.11 or higher
- Google Gemini API Key (GEMINI_API_KEY)

### 1. Clone the Repository
`ash
git clone https://github.com/Jagrit3500/MerchantOS.git
cd MerchantOS
`

### 2. Set Up Virtual Environment & Dependencies
`ash
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
`

### 3. Configure Environment Variables
Create a .env file in the root directory:
`env
GEMINI_API_KEY=your_gemini_api_key_here
PORT_HOME=8501
PORT_AGENT1=8502
PORT_AGENT2=8503
PORT_AGENT3=8504
MERCHANTOS_HOST=localhost
`

### 4. Ingest Regulatory Knowledge Base
Initialize and embed the regulatory documents into ChromaDB:
`ash
python ingest_docs.py
`

### 5. Launch the Platform
You can run all components simultaneously:

`ash
# Terminal 1: Home Command Center
streamlit run home.py --server.port 8501

# Terminal 2: Agent 1 - KYC & Fund Hold Diagnosis
streamlit run Agent1/app.py --server.port 8502

# Terminal 3: Agent 2 - Settlement Reconciliation
streamlit run Agent2/app.py --server.port 8503

# Terminal 4: Agent 3 - Regulatory Escalation
streamlit run Agent3/app.py --server.port 8504
`

Access the platform at http://localhost:8501.

---

## 🧪 Verification & Audit Integrity
- **100% Policy-Driven**: All recommendations, document checklists, and dispute letters are dynamically linked to ChromaDB document chunks with verifiable citation metadata.
- **Zero Hardcoding**: All URLs, ports, dates, and file paths are dynamically resolved via system environment variables and Python standard os.path.
- **Pre-tested & Validated**: End-to-end multi-agent workflow verified with live headless browser subagents and recorded demonstration sessions.

---

## 🏆 Hackathon Alignment: Track 3 (AI Revenue Recovery)
1. **Direct Financial Impact**: Instantly identifies and initiates recovery on trapped capital (e.g., ₹94,688 in sample portfolio) that would otherwise sit idle or be written off.
2. **Defensible Legal Architecture**: Builds mutual confidence between merchants and payment aggregators through transparent procedural compliance rather than adversarial confrontation.
3. **Autonomous Multi-Agent Collaboration**: From initial diagnosis to settlement reconciliation to statutory escalation, each agent handles a distinct phase of the financial recovery lifecycle.

---

## 📄 License
This project is licensed under the MIT License.
