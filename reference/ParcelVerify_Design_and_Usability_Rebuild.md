# ParcelVerify: Design and Usability Rebuild

## 0. Your assignment

Rebuild the presentation and interaction layer of the existing ParcelVerify application. Deliver working code, a usable end-to-end flow, and screenshots of the actual running result. Do not stop at a plan, a static mockup, a new landing page, or a colour change.

This is the authoritative design brief for this iteration. It supersedes conflicting visual, navigation and interaction instructions in `ParcelVerify_UI_Refactor.md` and earlier UI prompts. Preserve existing business rules, authorization, evidence integrity and data unless an explicit requirement below changes presentation only.

All product copy, reports and exports must be English. Communicate implementation progress to the user concisely. Work in the existing project, not a disconnected replacement project.

## 1. Locate and understand the reference

The user will place the visual reference alongside this brief in the project's `reference` directory, or an existing equivalent such as `references`. Inspect the available images rather than relying on attachment order or a filename guessed from a chat.

Identify the primary reference by its visible content:

- GREENWAY branding.
- Headline: “Leading the way in logistics solutions”.
- White background, dark typography and deep green accents.
- A wide photograph of a green delivery truck.
- A numbered three-step section accompanied by parcel imagery.
- Green feature sections and a restrained horizontal navigation bar.

If it retains its original name, the expected reference is `image(20261013-115730).png`; the earlier identical reference was `image(20261013-075946).png`. These are discovery hints, not required names. If more than one file matches, use the clearest matching image. Do not ask the user to identify it when its contents are unambiguous. If no matching image is available, state that limitation and continue using this written specification without claiming to have inspected it.

Use the reference as a visual composition guide. Do not insert a screenshot of the reference into the application. Do not reproduce GREENWAY's identity, unsupported statistics, testimonials or marketing claims.

## 2. What ParcelVerify is

ParcelVerify helps a logistics company understand unusual activity involving its outsourced carriers, warehouses and delivery operators.

It combines two evidence streams:

1. Shipment checks: records before dispatch, at transfer and at delivery, including quantity, weight, seals, photos, location and recipient confirmation.
2. Data-access checks: whether partner accounts access shipment/customer information within their authorization and assigned work, and whether recorded behaviour needs review.

Both lead into the same investigation experience: identify an issue, compare evidence, use AI to help explain it, propose a next step, obtain the required human decision and retain the activity history.

Keep this product identity. Do not turn the application into a generic parcel tracking service or a freight quotation website. Do not imply that a discrepancy proves fraud or identifies the responsible party.

The interface must be understandable to a first-time nontechnical adult. The user's request that “a child could understand it” means simple wording and obvious cause and effect, not a childish appearance.

## 3. Why the current design needs rebuilding

The current screenshots already have fewer pages and green accents, but they still look like a minimally styled administrative form. Specific defects:

- A narrow radio-button sidebar beside a large unused gutter.
- Nearly identical outlined rectangles for metrics, list entries and controls.
- Small text inside very wide rows, making related information feel disconnected.
- Repeated “Review case” buttons with little explanation of what will be reviewed.
- Abstract navigation labels and numbers without a clear introduction to the product.
- Essential evidence hidden while an unexplained decision form is immediately visible.
- “Confirm weight” and “Submit for approval” do not explain the actor, effect or next state.
- An issue sentence is repeated in several places without providing additional understanding.

Fix hierarchy, composition and interaction together. Changing font, border radius and colour alone is not a successful result.

## 4. Visual system and composition

### Reference qualities to implement

| Reference quality | Application implementation |
|---|---|
| Confident, large headline | A clear product statement on Home; descriptive task headings inside the workspace |
| Photography with intentional cropping | One quality logistics image on Home, integrated with the layout rather than dropped into a card |
| Strong white/green contrast | White working surfaces, emerald calls to action and one purposeful green feature region |
| Different section proportions | Split introduction, compact summary strip, structured issue list and focused detail layout |
| Numbered steps | A short explanation of the review process, connected to actual application behaviour |
| Restrained controls | One dominant action per task area; secondary links and clearly labelled alternatives |

Use a primarily white canvas (#FFFFFF), deep green (#075E49), near-black green text (#142B24), secondary text (#52645C), subtle dividers (#DFE6E1) and occasional pale green surfaces (#EEF5F0). Warning/error colours remain semantic, not decorative. Verify contrast in rendered combinations.

Use a clean modern sans-serif: preferably Manrope for prominent headings and Inter for UI/body, or a coherent available equivalent. Provide system fallbacks; the app must remain usable if fonts fail to load. Body text should generally be 16px, secondary copy 14px, operational headings 28–36px. Home may use a 48–64px desktop headline, reducing appropriately on mobile.

Use a consistent spacing rhythm, moderate corner radii and minimal shadows. Lists should use alignment and dividers instead of separate oversized pill-shaped containers. Do not wrap every section in a card. Use intentional whitespace between groups without abandoning most of the viewport.

Brand imagery belongs on Home. Operational pages should give space to real evidence and decisions. Marketing images must never be displayed as shipment evidence. Use project-owned or appropriately licensed imagery and record its source; if image generation is available, a clearly decorative generated image is acceptable. Do not depend on fragile remote hotlinks.

Do not reproduce the screenshot's floating pets, input-method overlays or assistant notifications. Hosting controls are outside the design scope unless legitimately configurable.

## 5. Navigation and screen architecture

Use a horizontal header: ParcelVerify brand at left, `Home`, `Issues`, `Partners`, and a compact secondary account/settings menu. Use clear links with an active state, not radio controls. Move search into the relevant screen; remove the permanently duplicated sidebar search. On mobile, collapse navigation into an accessible labelled menu.

Exactly three primary destinations remain. Shipment details and partner details are contextual views, not extra top-level modules. Help, demo controls and administrative diagnostics are secondary.

### Home: understand the service and start work

Desktop composition:

- Header around 72–80px tall.
- A compact two-column introduction: approximately 55% text/actions and 45% logistics photograph, with aligned visual weight. Use a deliberate image crop and a restrained height rather than a full-screen banner.
- A compact summary strip below it, followed by the first actionable issue rows.
- A short three-step explanation below the operational content, visually related to the reference's numbered section.

Recommended copy:

**Check every handoff. Understand every issue.**

“Review shipment evidence and unusual data access across your delivery partners.”

Primary action: `Review issues`.
Secondary action: `Find a shipment`.

The primary action opens the actionable Issues view. The secondary action reveals or opens shipment search with an example format. It must be possible to locate a shipment that has no issue.

Use the summary strip for three meaningful values, such as `Needs review`, `Waiting for approval`, and `Resolved`, mapped to actual states. Make them shortcuts to matching filters. Do not label reviewed-but-open work as resolved.

At 1440 × 900, at least the first actionable issue and its action should be visible without scrolling. At 390px, the main actions should appear before the photograph so that imagery does not delay access to work.

The numbered explanation should say:

01 — **Find an issue**: See which records need a closer look.
02 — **Compare the evidence**: Check shipment records, photos or account activity.
03 — **Choose the next step**: Request information or submit a decision for approval.

This is an explanation, not an extra onboarding gate or a forced wizard on every visit. Do not add pricing, testimonials, shipping quotes or ornamental maps.

### Issues: understand the queue

Heading: `Issues to review`.
Supporting text: “Check what happened and decide what information is needed next.”

Use one search field for shipment, partner or issue. Keep status and issue-type filters compact, with secondary partner filtering if needed. Preserve filters and scroll position when returning from a detail view.

Desktop list columns: Shipment / Partner / What needs checking / Status / Action. Use an actual aligned header. On mobile, convert each entry to a compact labelled block with a clear action.

Example evidence-backed entries:

| Issue | Short explanation | Action |
|---|---|---|
| Weight changed | 2.00 kg before dispatch → 1.85 kg at handover | Compare weights |
| Photo may have been reused | This photo matches another recorded submission | Compare photos |
| Access outside assigned work | A partner account viewed a shipment outside its recorded assignment | Review access |
| Delivery information missing | A required location or recipient confirmation is not recorded | See missing information |

Only show explanations supported by the actual records. Different issues on the same shipment must be distinguishable by issue type and a friendly issue reference where necessary. Do not merge or delete unrelated issues for cosmetic simplicity.

### Issue detail: evidence first, action second

Use a descriptive heading such as `Check a weight difference`; put the shipment reference, partner and status below it. Include an obvious Back link.

The main reading order is:

1. What happened?
2. What evidence is available or missing?
3. What should happen next?
4. What has already been done?

Use a roughly two-thirds evidence / one-third action layout on desktop. Stack the action panel after essential evidence on mobile. Keep history and technical details expandable. Do not hide the primary comparison inside a default-closed accordion or an unselected tab.

For the weight case, prominently compare `Before dispatch: 2.00 kg` and `At handover: 1.85 kg`, with stage, recorded time, source and relevant evidence thumbnails. Show `150 g lower` and a short factual explanation. Missing photos should have a clear missing-evidence state. Clicking a thumbnail opens a larger accessible view.

A simple shipment journey may summarize actual recorded stages. Do not imply unrecorded events occurred. For data-access issues, use an account/access comparison instead: account, shipment, assigned scope, observed access, time and authorization result. Do not force a delivery timeline into every issue type.

Keep legitimate explanations such as approved repackaging visible. Distinguish `Matches`, `Different`, `Missing` and `Not checked`. Evidence present does not mean evidence verified.

Expose a secondary `Explain this issue with AI` action with the explanation: “Summarize the available evidence and suggest what to check next.” AI output should show findings, uncertainty/counter-evidence and suggested next step, with supporting evidence links. Preserve manual review when AI is unavailable.

### Partners: connect organizations to actionable work

Heading: `Delivery partners`.
Supporting text: “Review the carriers, warehouses and delivery operators working with your company.”

Use a compact directory with partner name, role if known, shipments in the selected period and open issues. Selecting a partner opens a brief profile and their related issues. Do not turn this page into another full duplicate of Home.

Use only real supported partner metadata. Do not invent trust scores, star ratings, logos, location maps or performance trends.

## 6. Action design: specify the actor and consequence

Before rendering a user-facing action, trace its actual backend effect. Map it to clear wording. Do not rename a backend action to something easier but inaccurate.

| Actual operation | Appropriate wording |
|---|---|
| Ask for a fresh weighing | Request a new weight check |
| Record an existing measurement | Add a weight measurement |
| Ask for an additional photo | Request a photo |
| Upload evidence locally | Add evidence |
| Submit a proposed action to a supervisor | Send request for approval |
| Approve a pending proposal | Approve request |
| Close an authorized completed review | Close issue, only if this is the actual state transition |

For a request, show a plain-English explanation, who reviews it, who would receive it after approval, and what is expected. Use actual configured parties; show an honest unassigned state if none exists.

For the example weight case:

- Suggested next step: `Request a new weight check`.
- Explanation: “Ask the delivery partner to weigh this parcel again and provide a photo.”
- Editable draft reason, derived from the records: “The handover weight is 150 g lower than the dispatch record.”
- Submission preview: shipment, request, reviewer and intended next state.
- Button: `Send request for approval` when approval is required.
- Success: “Request submitted. Waiting for supervisor approval.”

Do not claim the partner has received a request when it is merely saved internally. In the isolated prototype, add the concise contextual note `Demo only — no message will be sent`. Keep a small global demo badge; avoid long repeated disclaimers.

For authorized supervisors, show the actual proposal and relevant evidence with `Approve request`, `Reject request`, and a supported way to request more information. Preserve existing separation of duties and permissions. Approval, execution and issue closure are separate concepts unless the current backend explicitly combines them.

Offer only actions relevant to the issue, role and state. Keep uncommon supported actions under `Other actions`. Avoid presenting a large unexplained dropdown as the main interaction.

Preserve evidence submission through a small contextual form: stage, relevant facts, photo/note, review and submit. Use existing supported ingestion routes; do not invent external integrations or introduce a new full logistics-management module.

## 7. Scope and integrity

Preserve both shipment and data-access detection, AI investigation, human approval and audit history. Keep server-side identity and authorization, assignment restrictions, historical/expiry checks, approved repackaging handling, transactional integrity and duplicate prevention. A hidden button is not an authorization control.

Do not remove backend functions or historical records to simplify screens. Reduce exposed choices and reorganize access instead. Defer bulk operations, rule editors and elaborate analytics from the primary experience.

Check two concrete data issues visible in the current screenshots:

- Some partners have 20 shipments and 21 open cases. This can be valid when multiple issues concern one shipment. Verify definitions and label them clearly. If useful, show `21 open issues across N shipments`, computing N from real data.
- A completed `Last activity` appears as 2 Nov 2026 in screenshots taken on 13 Oct 2026. Investigate future demo events, scheduled records or timestamp handling. Use a correct label or coherent demo timeline, never silently rewrite historical production facts.

Use one reporting period and consistent authorized data for counts and lists. A demo should include understandable normal and exceptional examples, clearly labelled, without falsifying metrics to make the screen attractive.

## 8. HCI behaviours to implement

- Recognition: clear issue titles, labelled evidence and visible next steps; users should not need to remember IDs between pages.
- Visibility: distinguish loading, submitted, awaiting approval, rejected, executed, failed and closed states accurately.
- Feedback: each mutation gives a specific result near the affected content and updates the relevant status/count.
- Error prevention: validate beside fields, explain missing input, prevent duplicate submissions and preserve drafts after failure.
- User control: Back and Cancel are obvious; preserve context. Confirm consequential decisions with a specific preview, not generic repeated popups.
- Progressive disclosure: default to relevant evidence and actions; expose history and technical details when requested.
- Accessibility: semantic labels, keyboard access, visible focus, useful image alt text, colour plus text/icon for status, normal-text contrast of at least 4.5:1 and practical 44px action targets.
- Consistency: use the same terms and status meanings across navigation, counts, forms and exports. Show local time with its timezone and measurements with units.

Keep UUIDs, hashes, JSON, stack traces, raw scores and provider configuration in permission-appropriate secondary details. Retain provenance for investigators. Avoid presenting None, True, snake_case identifiers or empty raw tables in normal views.

AI failure wording: “AI explanation is unavailable. You can still review the evidence.” Offer retry when appropriate and manual review. Do not endlessly retry authorization errors or disguise rules/sample text as live AI output. Avoid triggering AI on every UI rerender.

## 9. Implementation sequence and practical constraints

1. Inspect project instructions, current source, framework, data contracts and existing deployment. Preserve unrelated work. Save a recoverable checkpoint before substantial restructuring.
2. Inspect the GREENWAY reference and record a short implementation checklist covering composition, typography, imagery, spacing and controls.
3. Build shared design tokens, header/navigation and core UI components. Preserve working backend integration.
4. Implement one complete, polished weight-issue flow from Home through evidence and submission feedback. Then implement the data-access variant and apply shared components to Issues and Partners.
5. Verify the actual running UI with screenshots and interaction checks. Fix visual/functional defects found before handing off.

Keep Streamlit and the existing architecture if they can support the result. Use maintainable components and shared styling, not scattered fragile selectors, fake HTML buttons or a single screenshot masquerading as UI. All visible navigation, forms and actions must work.

Do not migrate the entire stack merely to get a new appearance. If a verified framework limitation materially prevents the required interaction or layout, explain it and propose a bounded alternative with deployment implications. Do not quietly deliver the same default layout while claiming the reference is matched.

UI completion may proceed while the existing Gemini/deployment blocker is documented. Keep the integration and resume its verification after the UI is stable. Do not label AI or online deployment verified without evidence. Follow the existing publishing authorization and workflow; do not create a second deployment merely for a cosmetic iteration.

## 10. Acceptance criteria

### Visual

- The primary header is horizontal and the old radio sidebar is gone.
- Home visibly reflects the reference through confident typography, intentional photography, white/green composition and a numbered explanation.
- Issues and detail screens share the same identity; they are not unchanged default forms behind a new Home page.
- Lists use compact aligned information, avoiding one enormous outlined card for every record.
- Main body copy is readable and related information is visually grouped.
- No decorative image substitutes for evidence; no artificial claims or metrics.

### Functional

- A first-time user can start an issue review from Home within two interactions.
- Shipment lookup works for a shipment with no issue.
- Both shipment and data-access issues can be opened and reviewed.
- Essential evidence is visible before a consequential decision.
- Request wording matches the actual operation and identifies the review/recipient context.
- Submission shows the correct resulting state and survives supported refresh/navigation behaviour.
- AI failure leaves the manual workflow usable.
- Authorization and rejection behaviour remain correct; duplicate clicks do not create duplicate work.
- Summary counts and filtered lists reconcile.

### Verification and delivery

Use existing meaningful tests and targeted checks for changed logic. Inspect actual rendered screens at 1440 × 900, 1024 × 768 and approximately 390 × 844. Check navigation, keyboard focus, field validation, image viewing, loading/error states and horizontal overflow.

Capture Home, Issues, a weight-issue detail, a data-access detail and Partners. Compare the implemented Home beside the reference for typography, image balance, white/green contrast and section rhythm. Do not assert a visual match based on source code alone.

Report changed files, what now works, validation actually performed, screenshots and the usable preview/current application address when available. Clearly separate local verification, deployed UI verification and real AI verification.

If a human usability check becomes possible, ask a new user to explain the product, open one issue, describe the evidence and predict the main button's effect without coaching. Treat these as goals until observed; do not claim user-tested HCI compliance from automated tests alone.

The final result should feel like a coherent logistics product with a clear job to do. Every screen should make its purpose, evidence and next action understandable.
