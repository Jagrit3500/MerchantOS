# MerchantOS — The Merchant's Desk

## Design direction

A white financial workspace with the character of a carefully typeset account book. The composition is built around navigation, transaction records, and focused tasks.

Reference research:
- [Stripe Payments](https://stripe.com/payments): product examples alongside financial information.
- [Stripe dashboard design](https://docs.stripe.com/stripe-apps/design): overview, list, and object-specific workflows.
- [Razorpay Payment Gateway](https://razorpay.com/payment-gateway/): consolidated payment operations.
- [Wise Business](https://wise.com/us/business/): plain-language amounts, fees, and actions.

These are information-design references. MerchantOS has its own typography, palette, mark, and layout.

## Typography

**Primary: Instrument Sans**, 400–700. Controls, navigation, labels, tables, and financial figures. Tabular numerals for aligned amounts.

**Secondary: Newsreader**, optical sizes 6–72, weights 400–500. Reserved for page titles, the main balance, and occasional supporting notes. Never used for dense tables.

**Utility: IBM Plex Mono**, 400–500. Transaction references and step numbers.

Fallbacks: Segoe UI for the primary face, Georgia for the secondary face, system monospace for identifiers. Web fonts are requested through Google Fonts; layouts must remain usable without them.

Scale:
- Page heading: 32–48 px, regular serif, compact leading.
- Main balance: 43–66 px, regular serif.
- Section heading: 18 px, semibold sans.
- Financial summary: 23–34 px, medium sans.
- Body and controls: 12–14 px.
- Supplemental metadata: 10–11 px.

## Palette

| Role | Value |
| --- | --- |
| Canvas | #FFFFFF |
| Navigation / supporting wash | #F6F8F5 |
| Primary ink | #202D29 |
| Muted text | #63706A |
| Dividers | #E3E8E3 |
| Primary action | #195846 |
| Balance accent | #E6EE9F |
| Settled status | #3D7841 on #EDF6ED |
| Pending status | #97641B on #FCF5E6 |
| Hold status | #AE5547 on #FCF0ED |

Citron is a supporting accent in the balance composition. Buttons retain one consistent green across all pages. Status colors always include a text label.

## Composition

- A 236 px desktop navigation rail, with a native collapsible sidebar on narrow screens.
- White main canvas, thin dividers, generous section spacing.
- Content width capped at 1440 px; desktop gutters 53 px, mobile gutters 18 px.
- 5–9 px corner radius. No decorative shadows or gradients.
- A small three-stroke brand mark repeats as the balance-panel motif.
- Real Streamlit containers group widgets. Do not split HTML opening and closing tags around native widgets.
- Financial tables use restrained headers, row rules, right-aligned amounts, and compact status markers.

## Page templates

### Overview
Compact title → sample label and report action → main balance beside a complete amount breakdown → three financial figures → searchable settlement ledger beside recovery actions and payment-method volumes.

All sample figures are calculated from the included CSV. The sample is explicitly labeled. The amount breakdown uses deductions on settled rows to avoid counting charges on unpaid rows twice.

### KYC
Compact title → three-stage progress → one question with native radio selection and navigation → contextual explanation beside the question.

Results use action-plan, support-request, and evidence tabs.

### Reconciliation
Three-stage progress → upload, manual, and sample modes in a bordered working area → explanatory rail.

Results use financial figures and tabs for exceptions, the complete ledger, exports, and policy context.

### Escalation
Case details, evidence, and correspondence occupy the main column. The narrower column shows elapsed days, the recommended contact, and the escalation sequence.

## Interaction and accessibility

- Each stage has one primary action.
- Native controls retain labels and keyboard operation.
- Focus rings are visible.
- Decorative SVGs are hidden from assistive technology.
- Tables retain native heading and cell semantics.
- Dynamic text inserted into HTML is escaped.
- Search and filtering use native inputs.
- Tables scroll horizontally on narrow displays; sidebar navigation collapses.
- Reduced-motion settings are respected.
- Check startup and result screens with Streamlit AppTest. Visual browser QA is a separate check and must not be claimed from HTTP responses or AppTest alone.

## Implementation

- src/ui.py: navigation and component helpers.
- src/styles.css: the complete visual system and responsive rules.
- .streamlit/config.toml: native widget colors.
- home.py and Agent1–3/app.py: page composition.

Business engines, provider integrations, and the vector database are outside the design layer.
