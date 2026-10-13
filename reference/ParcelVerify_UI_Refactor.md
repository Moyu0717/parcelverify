# ParcelVerify — Human-Centred UI and Scope Refactor

## Execution instruction

Implement this brief in the existing ParcelVerify repository. Inspect AGENTS.md, the current app entry point, data model, permissions, tests and deployment configuration first. Then implement, run, inspect and fix the application. Do not stop at a plan or produce a disconnected mockup. Preserve working integrations and existing records. All product UI, reports and exports must remain English.

This brief was prepared from the user's project history and 13 screenshots, not from source-code inspection. Verify implementation details against the repository. The screenshots suggest Streamlit; the earlier stack was Python, Streamlit and SQLite, with AI integration evolving from local Ollama to a hosted provider. Preserve the current working provider and deployment contract; do not revert based on older history.

## 1. Product promise and scope

ParcelVerify helps logistics companies review unusual activity involving outsourced carriers, warehouses and delivery partners. Its core experience is: find an issue, understand the evidence, choose the next step and record the decision.

Keep both detection paths:

- Data access: check whether a partner accesses permitted shipments and customer information, and flag suspicious access behaviour.
- Shipment evidence: compare evidence before dispatch, during transfers and at delivery, including quantity, weight, seals, photos, location and recipient authorization.

Both feed the same case review experience. AI helps explain evidence and proposes next steps. Authorized people make decisions. An anomaly is a reason to check, not proof of fraud, leakage or responsibility.

“A child could understand it” means clear language, obvious actions and low cognitive load. The actual users remain adult operations staff, investigators and supervisors. Use a professional visual identity.

## 2. Current issues to fix

- Six module-based pages force users to repeatedly select the same shipment or case.
- UUIDs, snake_case fields, JSON, hashes, ISO timestamps, model names and execution traces dominate normal screens.
- Large partner metric cards bury the actionable review queue below the fold.
- Raw metrics such as 45 points or 100 affected shipments per 1,000 lack immediate meaning.
- Evidence is presented as backend output rather than an understandable comparison.
- AI provider HTTP 403 errors and setup instructions appear in the operational interface.
- Role switching and demo persistence occupy primary navigation space.
- The screenshot shows unresolved counts that warrant checking against case states; do not assume the underlying calculation is correct or incorrect without inspecting it.

Ignore the floating pets, input-method widget and WorkBuddy progress bubbles in the screenshots: these appear to be external overlays, not ParcelVerify components to reproduce.

## 3. Navigation: exactly three primary destinations

| Destination | Purpose | Content |
|---|---|---|
| Overview | Know what needs attention | Three compact counters and a short actionable case queue |
| Cases | Complete a review | Searchable cases, case details, evidence, AI help, decision and history |
| Partners | Understand partner activity | Compact partner list and filtered partner details |

Settings and Help belong in a small secondary menu. Demo controls belong under Settings > Demo tools. Keep a quiet “Demo workspace” badge visible when applicable. Preserve a clear note that operational actions are simulated in the demo.

Existing-page migration:

| Existing page | New location |
|---|---|
| Partner Overview | Overview summary + Partners |
| Shipment Timeline | Case detail > Evidence > Shipment journey |
| Access Monitoring | Case detail > Evidence > Data access; administrative logs in Settings |
| Handoff Verification | Case detail > Evidence > Shipment checks |
| AI Investigation | Case detail > AI summary |
| Approvals & Audit | Case detail > Next step + Activity; awaiting-approval filter in Cases |

Preserve shipment lookup without creating a fourth main destination. A search field labelled “Find a shipment or case” can open a shipment record, including one with no case. A normal shipment must not be assigned a fake case merely for navigation.

## 4. Main screens

### Overview

Use the title “Your review overview” and one sentence explaining the current reporting period. Show only three compact metrics: “Needs review”, “Awaiting approval”, and “Resolved”. These counts must link to the corresponding case filters and derive from the same authorized data and period.

Place “Needs your attention” immediately beneath the metrics, visible on a typical laptop without scrolling. Show approximately five rows with shipment reference, partner, a plain-English issue, status and “Review case”. Example issue: “Recorded weight is 150 g lower”. Include both data-access and shipment-evidence cases in the demo.

No large marketing hero, decorative world map, invented trends, decorative charts or long introductory policy paragraphs. An empty queue should say “You're all caught up” and offer shipment search.

### Cases

Provide search and a small filter row: status and issue type (“All”, “Shipment checks”, “Data access”). Partner filtering may appear when entering from a partner record. Keep completed cases available but default to work needing attention.

Use columns: Shipment, Partner, Issue, Status, Updated, action. Use friendly case references only when needed; keep internal identifiers in secondary details. Preserve filters and selection when navigating back.

Case detail should answer, in order:

1. What needs checking?
2. Which evidence supports or challenges the concern?
3. What can I do next?

Header: shipment reference, partner, status badge, one-sentence issue and Back to cases. Use two main tabs, “Summary” and “Evidence”, with Activity as a collapsed section rather than another primary page.

Summary: concise factual finding; a compact “AI summary” section; “Next step” controls. Keep one visually dominant next action appropriate to the current user and case state. Secondary actions can remain outlined or in a labelled menu.

AI summary structure: “What we found”, “What is missing”, “Suggested next step”. Link claims to the supporting evidence. Include relevant counter-evidence and approved changes. Never label a deterministic rules result or sample text as a live AI result.

Evidence: open the relevant group first. For shipment cases, show a readable journey such as Prepared → Handed over → Delivered, accurately reflecting the actual recorded stages. For access cases, show who accessed which shipment, when, whether permitted, and why it was flagged. Do not force a physical-delivery timeline onto a data-access-only case.

For shipment comparisons, use labelled rows for Quantity, Weight, Seal, Location and Recipient confirmation. Display “Before” and “At handover” or the actual applicable stages, plus “Matches”, “Different”, “Missing” or “Not checked”. Do not conflate missing evidence with a mismatch or successful verification.

Example from the screenshot: “Before: 2.00 kg”; “At handover: 1.85 kg”; “Difference: 150 g lower”. Surface “Confirm the weight” only when supported by the actual workflow. Approved repackaging or other legitimate explanations must remain visible.

Show photo thumbnails with stage, caption and time; allow enlargement. Use clear empty states for unavailable photos. Clearly label demonstration images; do not present coloured placeholder cards or stock photos as verified parcel evidence.

### Partners

Use a compact list: partner name, shipments in the selected period, open cases and last activity. Selecting a partner shows related cases and a short evidence-based summary. Count distinct cases and shipments correctly. Avoid “fraud score”, unsupported partner rankings or “100% safe”.

Move detailed rate calculations and methodology into secondary details. Any retained comparison must use the same reporting period and include denominators. “Evidence complete” must not imply “Evidence verified”.

## 5. Simplify the working loop

Default demonstration path: Overview → Review case → Read evidence → Generate AI summary if wanted → Submit a next step → Authorized approval → Recorded result.

Keep these operations functional:

- Search shipments and cases.
- Open relevant evidence and enlarged photos.
- Add evidence through a short form from the shipment/case: select stage, enter only relevant facts, attach photo or note, review and submit. Reuse the existing supported ingestion route; show unsupported integrations honestly.
- Run AI review on demand with clear loading and retry states.
- Request more evidence, submit a proposed action, and allow an authorized supervisor to approve or reject it.
- Close a reviewed case only with the required authorization and reason.
- View activity and download a readable case summary with a concise evidence/decision record.

Use the existing state machine and approval requirements. Do not invent a shortcut that executes an action merely because the interface says “Resolve”. Match labels to effects: “Submit for approval” is not “Apply action”; “Approve request” is not “Action completed”. Record execution outcome separately when applicable. Rejected proposals cannot execute.

Reduce default-visible action types to the useful supported subset: request a photo, confirm weight, confirm recipient, request an explanation, or submit/record a review decision. Contextually display only applicable actions; map them to existing backend operations. Defer batch management, generalized rule editors, elaborate role administration and extra analytics dashboards from the main prototype experience.

Keep backend authorization, server-trusted identity, assigned-shipment restrictions, historical authorization/contract checks, expiry handling, audit integrity, idempotent case creation and transactional failure behaviour. UI simplification must not weaken these. The earlier queue rule was score >= 30 OR blocking issue; verify the current authoritative rule and preserve it unless separately authorized to change it. Scores may be hidden without changing detection logic.

## 6. Plain English and progressive disclosure

| Internal value | User-facing wording |
|---|---|
| pending_review | Needs review |
| review_completed | Review complete |
| request_reweigh | Confirm weight |
| actual_gps missing | Delivery location is missing |
| recipient_authorization unknown | Recipient approval has not been confirmed |
| Tool execution trace | Technical details, collapsed and permission-appropriate |
| supplementary_statement | Additional information |
| authorized | Access allowed |

Use “Resolved” only when the actual case state means closed/resolved; do not rename all completed reviews as resolved. Format dates as “13 Oct 2026, 3:50 pm MYT” when displaying Malaysian local time, retaining original timestamps in records. Show units and useful precision. Avoid True, False, None and underscores in ordinary copy.

Put JSON, hashes, full UUIDs, raw logs, provider/model names and stack traces in permission-appropriate technical details. Keep sufficient source provenance accessible to investigators. Replace repeated paragraphs with one short note near AI conclusions: “Flags need review. They do not prove wrongdoing.”

For AI failure show: “AI summary is unavailable. You can still review the evidence.” Offer Retry and manual review. Give administrators diagnostic details separately. Do not fake success, repeatedly retry authorization failures, or run AI on every rerender. Reuse valid saved results and show when new evidence makes them outdated.

## 7. Visual direction

Use the final white-and-green logistics reference as the primary design direction. Borrow the black-and-yellow reference's clear hierarchy and restrained contrast. The other references support generous spacing, concise headings and a coherent logistics identity. Translate these qualities into an operational workspace; do not copy their long marketing pages, quote calculators or promotional statistics.

Design tokens:

- Page background: #F6F8F7; surfaces: #FFFFFF.
- Primary text: #142A25; secondary text: #53645F.
- Brand/action: #08624B with white text; subtle brand surface: #E8F3EE.
- Borders: #DFE7E3. Separate semantic amber/red treatments for warnings/errors.
- Inter or a comparable available sans-serif, with system fallback.
- Body 16px, secondary labels 14px, page title 28–32px; avoid oversized dashboard headings.
- Consistent 8px spacing rhythm; 24–32px page padding; 16–24px card padding.
- Cards 12–16px corner radius, buttons 8–10px, restrained shadows and borders.
- Desktop navigation around 216–232px; content comfortably constrained without wasting most of the screen.

Use consistent line icons paired with text. Colour must never be the only status indicator. Prefer compact meaningful rows over one enormous card per record. Animation should be subtle and respect reduced-motion preferences. Use real evidence imagery where relevant; marketing photography is optional and must not push work below the fold.

## 8. HCI implementation requirements

- Recognition over recall: preserve case context and show the next action where the evidence appears.
- Progressive disclosure: show finding, evidence and next step first; advanced details on request.
- Visibility of state: loading, submission, success, error, missing data and empty states all need deliberate copy.
- Error prevention: validate beside fields, retain input after errors and prevent duplicate submission.
- User control: allow Back and Cancel without losing drafts; confirm consequential decisions with a specific summary.
- Consistency: identical labels, units, controls and status meanings throughout.
- Accessibility targets: keyboard operation, visible focus, labelled fields and controls, meaningful reading order, normal-text contrast at least 4.5:1 and practical 44px interaction targets. Verify, do not simply claim compliance.
- Responsive behaviour: usable at 1440px, 1024px and 390px; stack evidence comparisons and actions on small screens, avoid whole-page horizontal scrolling and overlapping controls.

## 9. Implementation strategy

Keep the existing architecture where feasible. If Streamlit is confirmed, implement a shared theme, app shell, readable rendering helpers and explicit selected-case state. Avoid scattering brittle CSS selectors throughout pages. Do not undertake an unsolicited React/FastAPI migration. If a concrete framework limitation blocks a requirement, report it with the achieved result.

First complete one polished end-to-end case flow, then apply the same components to Overview and Partners. Separate presentation changes from domain behaviour. Use a small display adapter for friendly labels and formatting. Keep readable data views distinct from raw diagnostic output.

Audit metric definitions before displaying counters. Ensure repeated evidence submission or AI runs do not duplicate cases; partner totals and case lists must reconcile. Preserve existing data during the refactor. Keep the existing live-build/start command working and document any necessary deployment change.

## 10. Acceptance checks and final handoff

Verify with meaningful existing tests and targeted checks:

1. Exactly three primary navigation destinations; both detection paths remain discoverable.
2. A user can open an actionable case within two interactions from Overview.
3. No raw JSON, UUID-heavy table, hashes or execution trace in default operational views.
4. A shipment mismatch and an unauthorized-access case can both complete the applicable review path.
5. Missing photo, missing recipient confirmation and approved repackaging are correctly distinguished.
6. AI failure leaves evidence and manual review usable; successful AI claims link to evidence.
7. Unauthorized actions fail server-side; rejecting a proposal prevents execution.
8. Repeated clicks do not duplicate cases, decisions or audit records.
9. Overview counts agree with filtered lists; refresh preserves supported saved state.
10. Inspect the three target viewport sizes and the actual rendered primary screens. Check keyboard focus, text contrast, truncation and overflow.
11. Confirm the existing deployment/start path still builds and runs.

Report changed files, the implemented user flow, checks performed, any remaining blockers and screenshots of the finished operational screens. Distinguish verified implementation from suggested usability goals. Do not claim that users understand the design without observing user testing.

For a later five-minute usability check, ask a first-time user to find a case, explain the concern, locate a photo and identify the next action. Record hesitation and mistakes; adjust labels and grouping accordingly.
