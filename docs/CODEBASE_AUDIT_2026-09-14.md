# MerchantOS full codebase audit — 14 September 2026

## Result

The tracked application, configuration, documentation, fixture, and test files were reviewed individually. Operational and financial policy is centralized in `src/config.py`, documented in `.env.example`, and validated at startup. No secret, user-specific absolute path, direct environment read outside the configuration module, or provider/deployment default outside the configuration boundary was found.

“No hardcoding” in this audit means no duplicated operational, deployment, provider, regulatory, financial, workflow-window, or scoring value in application logic. Constants that define a data format or algorithm remain local by design: CSV aliases, supported date formats and statuses, HTTP/OAuth protocol values, INR display precision, UI text and geometry, and deterministic test fixtures.

## Findings corrected

1. Reconciliation balance and zero-value tolerances were embedded in the engine. They are now validated environment-backed settings.
2. Settlement timing used an import-time copy of the configured window. It now reads the active configuration during analysis.
3. Citation confidence used an import-time copy of its threshold. Retrieval and confidence now use active configuration and reject invalid thresholds.
4. Retrieval accepted zero or negative result counts. It now rejects them before storage or embedding work.
5. The command center’s capital-to-review figure omitted fee and settlement-difference exposure. Shared state now persists the complete review and recovery totals plus exception counts.
6. Generated Agent 2 wording conflated gross held/pending value with the actually outstanding amount. Cards, notes, recovery letters, timing details, and singular/plural wording now reflect transaction-level values.
7. Pricing and dispute references embedded in agent logic were moved to configuration.
8. Public KYC and escalation catalog results exposed mutable global dictionaries/lists. Callers now receive copies.
9. PDF documents were not guaranteed to close after extraction errors. Parsing now uses a managed document context.
10. Optional semantic and LLM fallbacks swallowed failures without diagnostics. Debug logging now preserves the fallback behavior while making failures observable.
11. The default consumer-help URL lacked a scheme. All configured external and OAuth URLs are now validated.
12. Configuration now validates tolerances, weights, penalties, workflow windows, hold-duration ordering, required identifiers, and escalation acknowledgement ordering.
13. Unused imports and accidental pointless formatted strings were removed across executable files.

## File-by-file review

| File | Review result |
| --- | --- |
| `.env.example` | Every application-owned environment key is documented; added pricing and reconciliation tolerance settings and removed the obsolete fee-dispute minimum. |
| `.gitignore` | Secrets, local state, caches, logs, generated output, and QA artifacts are excluded. |
| `.streamlit/config.toml` | Framework boot defaults and presentation theme only; no reconciliation business rule. Streamlit’s environment variables can override server settings. |
| `README.md` | Setup, limitations, CSV contract, runtime state, and configuration ownership are accurately described. Localhost URLs are documented examples, not application defaults. |
| `CODEBASE_ANALYSIS.md` | Historical architecture analysis only; no executable configuration. |
| `requirements.txt` | Dependency floors only; no embedded credentials or environment-specific path. |
| `index.html` | Landing structure and accessibility copy only. |
| `landing.css` | Presentation tokens, layout, and responsive geometry only. |
| `landing.js` | Landing interaction and configured endpoint discovery; no financial/provider rule. |
| `home.py` | Dashboard aggregation reviewed and corrected to use complete shared review totals. |
| `launch.py` | Fixed internal service topology with ports/URLs sourced from configuration; child cleanup and readiness flow reviewed. |
| `serve_frontend.py` | Authentication, same-origin checks, cookie flags, request limits, OAuth state/nonce, and CSP reviewed; provider and URL values come from configuration. |
| `ingest_docs.py` | Configured document/index paths and supported file handling reviewed. |
| `Agent1/app.py` | Workflow state, evidence refresh, activity persistence, and rendering reviewed; unused import removed. |
| `Agent1/kyc_agent.py` | Every selectable branch is covered; policy reference is configured and returned catalog data is isolated. |
| `Agent1/ticket_drafter.py` | All diagnosis-specific drafts reviewed for configured provider/regulatory values and safe fallback wording. |
| `Agent2/app.py` | Summary, exception table, ledger, report, evidence, state publishing, and download views reviewed; outstanding amounts and wording corrected. |
| `Agent2/reconciliation_agent.py` | CSV aliases, numeric/date parsing, duplicate/invalid-row behavior, fee/tax math, status aliases, outstanding values, balance variance, timing, health, recovery totals, and letter generation audited and expanded. |
| `Agent2/sample_data/sample_settlement.csv` | Deterministic sample fixture; values are test/demo evidence rather than production policy. |
| `Agent3/app.py` | Saved-case lifecycle, draft display, evidence fallback, and diagnostics reviewed. |
| `Agent3/escalation_agent.py` | Tier boundaries, issue types, checklists, grievance/Ombudsman/legal drafts, configured references, and catalog isolation reviewed. |
| `src/__init__.py` | Package marker only. |
| `src/activity_history.py` | SQLite schema, user/workspace scoping, parameterized values, fixed-section filtering, retention, deletion, and summaries reviewed. |
| `src/auth.py` | PBKDF2 hashing, constant-time verification, session rotation/revocation, account validation, and configured lifetime reviewed. |
| `src/citation_validator.py` | Citation/source validation and refusal behavior reviewed; dynamic threshold validation added. |
| `src/config.py` | Sole owner of environment reads and operational defaults; types, URLs, paths, ranges, and cross-setting invariants validated. |
| `src/embedder.py` | Model/path configuration, Chroma collection behavior, batching, metadata, and client reconnection reviewed. |
| `src/llm_agent.py` | Grounding instructions, citation validation, configured model limits, and deterministic extractive fallback reviewed; fallback logging added. |
| `src/pdf_parser.py` | Upload-name containment, extension/size/page validation, extraction, chunking, and resource closure reviewed. |
| `src/policy_evidence.py` | Current-local-source extraction, semantic selection, confidence labels, fallback, and diagnostic logging reviewed. |
| `src/retriever.py` | Dynamic top-k, cosine conversion/clamping, threshold filtering, output ordering, and invalid-input rejection reviewed. |
| `src/shared_state.py` | Atomic state publication and normalization reviewed; complete reconciliation exposure now persisted. |
| `src/ui.py` | Shared navigation, authentication gate, page setup, and configured routes reviewed. |
| `src/styles.css` | Shared presentation system only; no business policy. |
| `docs/DESIGN_SYSTEM.md` | Presentation guidance only. |
| `docs/ipv_and_complaint_process.txt` | Local evidence snapshot; treated as source data and not executable policy. |
| `docs/merchant_recovery_playbook.txt` | Local evidence snapshot; treated as source data and not executable policy. |
| `docs/razorpay_policies.txt` | Local evidence snapshot with verification metadata; not executable configuration. |
| `docs/rbi_pa_2025_knowledge.txt` | Local regulatory summary with source metadata; not executable configuration. |
| `docs/CODEBASE_AUDIT_2026-09-13.md` | Prior audit record retained unchanged. |
| `tests/__init__.py` | Test package marker only. |
| `tests/test_core.py` | Core financial, parser, state, authentication, activity, PDF, and policy behavior reviewed and extended. |
| `tests/test_ui.py` | Streamlit rendering/state flows reviewed through mocked UI tests. |
| `tests/test_agent1_exhaustive.py` | Covers all 3,136 selectable decision paths, local/semantic evidence, active threshold changes, and retrieval validation. |
| `tests/test_agent2_exhaustive.py` | Covers every status/method alias combination, settlement variants, tolerance boundaries, dynamic timing, parser reuse, and configuration ownership. |
| `tests/test_agent3_exhaustive.py` | Covers every escalation tier boundary/predecessor, all draft/issue combinations, and mutation isolation. |
| `chroma_db/**` | Tracked generated vector-index data was treated as runtime evidence, not source code. Audit reads changed local access metadata; those binary changes are excluded from the commit. |

## Verification

- `python -m compileall -q Agent1 Agent2 Agent3 src home.py launch.py serve_frontend.py ingest_docs.py tests`
- `python -m ruff check Agent1 Agent2 Agent3 src home.py launch.py serve_frontend.py ingest_docs.py tests --select F,E9`: passed
- `python -m pytest -q tests`: **61 passed, 31 parameterized subtests passed**
- Agent 1 decision matrix: **3,136 selectable combinations**
- Agent 2 matrix: every supported payment/status alias combination plus accounting, tolerance, timing, parser-reset, and configuration-ownership boundaries
- Nine-file CSV acceptance suite: fixtures 01–06 parsed without warnings; fixture 07 retained 3 valid rows with 3 intended warnings; fixture 08 retained its valid control row with 13 intended invalid-row warnings; fixture 09 was correctly rejected for its missing required `tax` column
- Agent 3 matrix: every tier boundary and every draft/issue combination
- `git diff --check`: passed

The single test warning originates in ChromaDB’s installed telemetry dependency using an API deprecated for future Python 3.16; it does not indicate an application failure.

## Operational boundary

The audit establishes configuration ownership and tested behavior for the current code. Provider pages, legal rules, model packages, and dependency behavior can change externally; re-verify evidence snapshots and negotiated merchant settings before production use. Generated letters remain decision-support output and require review against the merchant’s actual agreement and facts.
