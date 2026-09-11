# MerchantOS

MerchantOS is a local recovery workspace for merchants dealing with payment-account restrictions, held settlements, payout discrepancies, and formal escalation. It combines a public two-section landing page with a command center and three focused Streamlit workflows.

## What is implemented

- KYC and fund-hold diagnosis through a six-question decision tree.
- Editable document checklists and support-request drafts.
- CSV settlement reconciliation with configurable fee, tax, and turnaround rules.
- Independent fee and tax overcharge detection, including zero-rate payment methods.
- Held/pending payout tracking, health scoring, balanced audit totals, and CSV export.
- A zero-state command center that updates automatically from the latest successful reconciliation.
- Grievance, RBI Ombudsman, and legal-notice draft generators.
- A local ChromaDB knowledge base with semantic retrieval, optional Groq answers outside Agent 1, and citation validation.
- Agent 1 evidence is extracted from the current local policy files; semantic matching supplies source selection and a visible cosine match score without adding freeform legal claims.
- Automatic semantic policy evidence after each completed workflow, with a refresh action and a current-local-file fallback.
- Persistent, per-user and per-workspace activity history for completed diagnoses, reconciliations, and explicitly saved escalation cases, with record-level deletion, clear-history confirmation, and links back to the originating workspace. Agent 1 history links reopen the selected saved diagnosis result through the current rules.
- A contribution-style command-center activity map with 12-month totals, active days, current streak, and workflow distribution instead of exposing detailed records on the overview page.
- Local email/password registration and sign-in with PBKDF2 password hashing, revocable server-side sessions, and an HttpOnly cookie shared across the workspace services.
- Shared runtime configuration for ports, URLs, paths, provider details, financial rules, workflow timing, retrieval, scoring, and landing-page media.

MerchantOS is a decision-support prototype. Its authentication is intended for a single local deployment; it does not provide roles, tenant isolation, or password recovery. Google OpenID Connect is supported when a web OAuth client is configured. The app does not submit complaints, connect to a payment-provider account, persist a complete shared case across services, or replace legal/accounting review. Verify generated correspondence and policy claims before sending.

## Services

| Service | Default URL |
| --- | --- |
| Public landing page | `http://localhost:4173` |
| Command center | `http://localhost:8501` |
| KYC and fund-hold diagnosis | `http://localhost:8502` |
| Settlement reconciliation | `http://localhost:8503` |
| Formal escalation | `http://localhost:8504` |

All ports and public URLs can be overridden in `.env`.

## Run locally

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python launch.py
```

The launcher waits for all five services, opens the landing page when enabled, and stops its child processes on `Ctrl+C`.
Use `python launch.py --no-browser` when starting it from a background process or service.

To run only the landing page:

```powershell
python serve_frontend.py
```

## Configuration

Copy `.env.example` to `.env`. The example documents:

- model and API settings;
- embedding, chunking, and retrieval behavior;
- service ports and public URLs;
- provider/workspace identity;
- fee, tax, scoring, and turnaround rules;
- escalation deadlines;
- input paths and interface tuning;
- landing-page videos and autoplay retry timing;
- authentication, registration, session lifetime, rate limiting, cookie security, and optional email-domain restrictions.

Operational configuration is centralized in `src/config.py`. Application modules do not read environment variables directly. Restart the services after changing `.env` because settings are loaded at process startup.

Authentication is enabled by default. Accounts and hashed credentials are stored in the ignored local SQLite database configured by `AUTH_DB_PATH`; plaintext passwords are never stored. Set `AUTH_SECURE_COOKIE=1` whenever the landing page and Streamlit services are served over HTTPS. Because the session cookie is shared by hostname across the service ports, use the same hostname (for example, consistently `localhost`) in every configured public URL.

### Google sign-in

Create an OAuth 2.0 **Web application** client under Google Auth Platform > Clients, then add the exact callback shown by `GOOGLE_REDIRECT_URI` to its authorized redirect URIs. Use the web client ID ending in `.apps.googleusercontent.com`; an IAM Workforce OAuth client is a different credential type and will not work with Google Sign-In. For the default local setup, the callback is:

```text
http://localhost:4173/api/auth/google/callback
```

Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in `.env`, keep `GOOGLE_AUTH_ENABLED=1`, and restart MerchantOS. The Google button stays visible before setup and explains what is missing; it becomes active automatically once both credentials are present. Production deployments must use an HTTPS landing URL, an exactly matching HTTPS callback, and `AUTH_SECURE_COOKIE=1`.

Google's setup guide: <https://developers.google.com/identity/openid-connect/openid-connect>

Agent 2 publishes successful uploaded reports and manually entered transactions to the configured `SHARED_STATE_PATH`. The explicitly labelled bundled sample stays inside the reconciliation screen and never populates the command center. The command center polls state using `DASHBOARD_REFRESH_INTERVAL_SECONDS`; before the first real reconciliation, every financial metric is zero and the ledger is empty. Completed workflow activity is stored per user in the SQLite database configured by `ACTIVITY_DB_PATH`. Detailed records remain in their originating workspace, while the command center shows only aggregate activity. The local runtime directory is ignored by Git.

The evidence view always performs a fast query-ranked search over the current `.txt` files in `DOCS_DIR`. With `AUTO_FETCH_POLICY_EVIDENCE=1` (the default), Agent 1 also checks the Chroma index and displays the top cosine match as an evidence-relevance score. Its visible evidence remains extractive from the current files; the score is not a diagnosis probability or legal-certainty measure. **Refresh evidence** reruns the semantic check and updates the checked time. Set the option to `0` when startup latency matters more than semantic retrieval; local matching and its weighted term-coverage score remain available.

## Settlement CSV format

Required logical columns are:

```text
transaction_id, amount, fee, tax, settlement_amount, status, payment_method
```

Common aliases are accepted. Add `transaction_date` and `settlement_date` to enable turnaround checks. Invalid, negative, non-finite, or duplicate transaction rows are skipped with a visible warning.

## Knowledge-base ingestion

Place supported documents in the configured docs directory, then run:

```powershell
python ingest_docs.py
```

The embedding model is configured for offline loading by default. The repository includes a local ChromaDB index; re-ingest after changing source documents or embedding/chunk settings.

The bundled policy summaries were last verified on 12 September 2026 against the official RBI 2025 Payment Aggregator Master Direction and the provider documentation identified inside each source file. They are snapshots, not a live legal feed.

## Audit notes

See [CODEBASE_ANALYSIS.md](CODEBASE_ANALYSIS.md) for the file-by-file architecture review, hardcoded-value boundary, corrections, remaining limitations, and verification results.
