# MerchantOS codebase audit — 13 September 2026

## Scope

The audit covered the shared configuration and UI layer, the home dashboard, all three agent workspaces, document generation, settlement parsing and calculations, local policy retrieval, authentication/activity helpers, launcher configuration, and the automated test suite.

## Configuration and hardcoded-value review

- Deployment ports, hosts, public workspace URLs, provider identity, provider contact routes, regulatory references, fee rates, tax rate, settlement expectations, escalation windows, health-score thresholds, upload limits, model settings, and runtime paths are owned by `src/config.py` and can be overridden through environment variables.
- No production source file outside `src/config.py` and `.env.example` contains the local ports, localhost deployment address, current provider entity name, or provider nodal email.
- No tracked source contained a private-key marker or common API-secret prefix during the static secret scan.
- No production source contains a user-specific absolute Windows path.
- UI copy, field placeholders, examples, SVG geometry, layout dimensions, and test fixtures remain literals by design; they are presentation or test data, not deployment or financial policy.

## Correctness findings resolved

1. Updated the default payment-aggregator entity to Razorpay Payments Private Limited, including its current CIN and published address.
2. Replaced the old single grievance step with the current provider sequence: Level 1 support, Level 2 Assistant Nodal escalation, Level 3 Nodal escalation, then a separate RBI Ombudsman eligibility review.
3. Removed draft wording that presented every hold as a confirmed regulatory violation or demanded release under an assumed RBI provision.
4. Centralized the configurable Ombudsman and consumer-law references used by generated correspondence.
5. Corrected the example environment file so its pricing, settlement timing, provider URLs, and workflow windows match the application defaults.
6. Hardened reconciliation input handling for header aliases, payment/status aliases, currency-formatted amounts, duplicate IDs, invalid values, missing dates, settlement shortfalls/excesses, and configured fee tolerances.
7. Kept settlement timing explicitly unassessed when the report does not provide both transaction and settlement dates.

## Verification performed

- `python -m compileall -q Agent1 Agent2 Agent3 src home.py launch.py`
- `python -m pytest -q tests`: **42 passed**
- Agent 1 exhaustive decision test: **3,136 selectable answer combinations**
- Agent 2 CSV matrix: eight valid scenario files parsed/analyzed; the intentionally malformed ninth file was rejected for its missing `tax` column
- Known 15-row reconciliation fixture: 15 transactions, ₹184,000 gross, ₹123,514.60 settled, 2 held, 2 pending, ₹57,500 gross review amount, ₹56,143 net recovery, and no fee overcharge under the configured benchmark
- Live health checks: landing `4173` and Streamlit services `8501`, `8502`, `8503`, and `8504` returned HTTP 200; each Streamlit health endpoint returned `ok`
- `git diff --check`: no whitespace errors

## Source references rechecked

- Razorpay grievance redressal policy: <https://razorpay.com/grievance-redressal/payments/>
- Razorpay payment-business transfer notice: <https://razorpay.com/notice/>
- Razorpay corporate information: <https://razorpay.com/corporate-information/>
- RBI Payment Aggregator Directions, 2025: <https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=12896>
- RBI Complaint Management System: <https://cms.rbi.org.in>

## Operational note

Provider policy and regulatory defaults are configuration, not legal conclusions. Re-verify them before a production release and override them for negotiated merchant pricing or a different provider. Generated letters must be reviewed against the actual agreement, complaint history, entity coverage, and current source material before sending.
