# CrimeAlert UI Design Guide

## 1. Purpose and design direction

CrimeAlert is a mobile-first crime location reporting system for members of the public and authorised security administrators. Its interface should make reporting feel calm, private, and fast, while making verified incident information clear and actionable.

The visual direction is **modern civic technology**: restrained, trustworthy, map-led, accessible, and professional. It should never resemble a sensational news feed or expose sensitive information unnecessarily.

### Design principles

1. **Safety before speed** - make emergency action immediately visible, and never imply that submitting a report replaces contacting emergency services.
2. **Report in minutes** - use short, progressive steps; save a draft; ask only for information needed to act on a report.
3. **Map with context** - maps should pair location with status, time, category, and risk indicators; do not rely on markers alone.
4. **Verified information first** - distinguish submitted, under-review, verified, rejected, and expired reports in every relevant view.
5. **Privacy by default** - anonymous reporting must be explicit and understandable. Public map views must generalise sensitive locations when appropriate.
6. **Calm clarity** - use plain language, generous spacing, clear headings, and a deliberately limited use of red.
7. **Accessible everywhere** - design for touch, small screens, keyboard use, screen readers, reduced motion, low bandwidth, and colour-vision differences.

## 2. Users and primary jobs

| User | Primary jobs | UI implication |
| --- | --- | --- |
| Public reporter | Submit an incident, share location/evidence, track its status, find urgent help | Prominent “Report incident” action, short guided form, visible privacy choices, report history |
| Community viewer | Understand nearby verified risk and safety context | Map-first home, filters, clear legend, non-alarmist summaries |
| Administrator | Verify reports, classify risk, monitor hotspots, manage data | Information-dense desktop dashboard with a strong review queue and auditability |

## 3. Information architecture

### Public app

Primary navigation on mobile: **Home**, **Map**, **Report**, **Updates**, **Profile**. Keep “Report” as the visually prominent centre action.

- Home: current-area summary, emergency action, map preview, recent verified alerts, quick reporting entry points.
- Map: live verified incidents, hotspots, filters, legend, selected-incident details.
- Report: guided crime reporting flow with save-and-resume support.
- Updates: report-status updates and area alerts, grouped by date.
- Profile: anonymous/privacy preference, report history, saved areas, help and settings.
- Emergency contacts: always reachable from Home and the report flow; also available from Profile.

### Admin app

Desktop-first left navigation: **Overview**, **Report management**, **Crime map analytics**, **User management**, and **Settings**. Trend analytics and the CSV export belong on **Overview**; they are not a separate navigation destination.

The report queue is the operational centre. A reviewer should be able to open a report, inspect its timeline and evidence, set classification/risk/status, leave an internal note, and complete a decision without losing queue context.

## 4. Core screen guidance

### Home

- Top area selector and a compact account/profile control.
- Persistent emergency card: “In immediate danger? Contact emergency services.” Include locally configurable numbers; never promise a response time.
- Primary CTA: **Report an incident**. Secondary CTA: **View nearby incidents**.
- Map preview with an area-level safety summary and a link to the full map.
- Show only verified public alerts by default; label their age clearly.

### Report incident flow

Use a five-step, resumable wizard with a step indicator:

1. **What happened?** Category selection with common options (theft, robbery, kidnapping, suspicious activity, other).
2. **Where?** GPS permission request with a manual map pin and address/landmark alternative. Confirm the pin before continuing.
3. **When?** Date and time, with “happening now” where appropriate.
4. **Details and evidence** Short description, optional image/video upload, and clear media limits.
5. **Privacy and review** Anonymous or identified submission, consent, summary of entered data, and submit action.

Requirements:

- Make optional fields visibly optional; do not mark them with an asterisk alone.
- Preserve completed work on navigation or connection loss.
- On success, display a reference ID, the initial status “Submitted for review,” next-step expectations, and links to emergency help and report history.
- Do not show an exact reporter location on public-facing surfaces.

### Incident map

- Default to the user’s selected area, not precise device location until consent is granted.
- Provide filters for time range, category, verification status (admin only for non-public states), and risk level.
- Use clustering at low zoom; reveal individual incident cards only at a useful level of detail.
- Include a persistent legend and an accessible list alternative to map markers.
- A selected marker opens a bottom sheet on mobile / side panel on desktop with category, approximate location, reported time, verified status, risk, and safety guidance.
- Hotspots should be labelled as trend information, not predictions or proof of danger.

### Report history and updates

- Each report card shows reference ID, category, submitted date, current status, and a short next action.
- Status sequence: **Submitted** → **Under review** → **Verified** / **Needs more information** / **Closed**. Use **Rejected** only in admin-facing terminology unless policy requires it for reporters.
- Never expose reviewer identities or internal notes to public users.

### Admin overview and queue

- Overview: KPI cards for total reports, pending reports, verified incidents, and leading category; a report-management-style filter bar; daily/weekly/monthly trend analytics; a server-side CSV export of the currently filtered authorized dataset; and a full-width hotspot map. The overview hotspot map mirrors the administrative map and includes every report status.
- Queue: filterable table/list with status, category, submitted time, approximate area, risk, reporter preference, and assigned reviewer.
- Detail view: structured incident facts, map, evidence preview, status history, related reports, audit trail, and decision controls.
- Destructive or consequential actions (reject, delete, publish, change risk) require confirmation and capture a reason where appropriate.
- Export screens must make data scope, date range, redaction level, and format explicit before download.

## 5. Visual system

### Colour

Use a deep navy and clean blue as the core identity, with neutral surfaces and semantic risk colours. The following starter tokens meet the desired tone; validate final contrast in implementation.

| Token | Hex | Use |
| --- | --- | --- |
| `brand-900` | `#102A43` | Header, strong text, authority |
| `brand-700` | `#1E5AA8` | Primary actions, links, active state |
| `brand-100` | `#E8F1FC` | Informational surfaces |
| `neutral-950` | `#17212B` | Primary text |
| `neutral-600` | `#52606D` | Secondary text |
| `neutral-100` | `#F2F5F7` | App background / subtle fills |
| `surface` | `#FFFFFF` | Cards and inputs |
| `success` | `#16803C` | Low risk / confirmed completion |
| `warning` | `#B45309` | Medium risk / review needed |
| `danger` | `#B42318` | High risk / destructive actions |
| `info` | `#1769AA` | Informational status |

Risk indicators must pair colour with text and an icon/pattern. Reserve red for high-risk context, errors, and destructive actions; it must not become the dominant brand colour.

### Typography

- Use **Inter** (or a similar neutral sans-serif) for interface text; system sans-serif is the fallback.
- Use a 16 px base size; never render essential body text below 14 px.
- Suggested scale: 12, 14, 16, 20, 24, 32 px. Use weight and spacing for hierarchy before increasing font sizes excessively.
- Use sentence case for labels and buttons. Prefer direct verbs: “Submit report,” “Choose location,” “Review report.”

### Layout and components

- Work on an 8 px spacing grid. Typical page padding: 16 px mobile, 24 px tablet, 32-48 px desktop.
- Use cards sparingly: one clear surface for each meaningful group, with 12 px radius, subtle border (`neutral-200`), and minimal shadow.
- Mobile controls should have a minimum 44 × 44 px touch target. Primary CTAs should be full width where that improves reachability.
- Desktop admin content should use a max-width around 1440 px and support a dense-but-readable data-table mode.
- Standardise: buttons, text fields, select menus, chips, status badges, alerts, empty states, skeleton loading, bottom sheets, tables, map pins, and confirmation dialogs.

## 6. Content and status language

Use factual, respectful wording. Avoid language that promises investigation, response, or safety.

| Avoid | Prefer |
| --- | --- |
| “Crime confirmed” | “Verified report” |
| “Danger zone” | “Higher reported activity” |
| “Your report is being handled” | “Your report is under review” |
| “Report now!” | “Report an incident” |

Every empty state should explain why the view is empty and offer one relevant next action. Example: “No verified incidents match these filters. Try expanding the date range.”

## 7. Accessibility, privacy, and trust requirements

- Target WCAG 2.2 AA contrast, semantic HTML, visible keyboard focus, and complete keyboard operation.
- Provide text/list equivalents for maps and charts. Charts need labelled axes, tooltips that can be focused, and a summary of the key insight.
- Respect `prefers-reduced-motion`; avoid auto-rotating content and flashing alert effects.
- Ask for location and notification permissions only in context, explain why, and offer a functional manual alternative.
- Clearly explain who can see a report and what changes once it is verified. Redact sensitive details from public views.
- Show upload progress, file errors, and connection failures in plain language. Never silently discard an in-progress report.
- Use an audit log for admin decisions and data exports; design this as a read-only record.

## 8. Responsive behaviour

| Breakpoint | Behaviour |
| --- | --- |
| Mobile (< 640 px) | Bottom navigation, full-screen report steps, map bottom sheet, one-column cards |
| Tablet (640-1023 px) | Two-column summaries where useful; expandable side panels |
| Desktop (≥ 1024 px) | Admin sidebar, persistent map/detail split view, tables and multi-column analytics |

Design the public flow at 360 px wide first, then expand. The admin workspace may prioritise desktop, but its essential review actions must remain usable on tablet.

## 9. Key states to design before implementation

- First use and location-permission education
- Anonymous and signed-in reporting
- Draft, upload in progress, offline, submission success, and submission failure
- No incidents, filtered-empty map, loading map, and map unavailable
- Every report status and “needs more information” response
- Admin: no queue items, conflict/duplicate warning, evidence unavailable, confirmation dialogs, and export success/failure
- Notification preferences, unread updates, and no notifications

## 10. Design handoff checklist

Before development, the design file should include:

- Public mobile flows for Home, Map, full report wizard, history, updates, profile, and emergency contacts.
- Desktop admin flows for overview, queue, report detail/review, map analytics, users, exports, logs, and settings.
- Component library with normal, hover, focus, disabled, loading, error, and success states.
- Responsive annotations, empty/loading/error states, and copy for permission and privacy decisions.
- Map behaviour rules: data freshness, marker clustering, precision/redaction policy, risk legend, and filter logic.
- Accessibility annotations and a contrast check for all colour combinations.
- A review with the project owner/security stakeholder to validate emergency contact wording, moderation policy, public-data redaction, and risk-level definitions.

## 11. First design milestone

Create the public mobile reporting journey and the admin report-review journey first. These two flows establish the shared status system, location handling, privacy model, and core component set. Once approved, extend the same system to maps, analytics, notifications, and settings.
