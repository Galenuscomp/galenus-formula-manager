# Migration from Base44 — what changed and why

Source reviewed: `galenuscomp/master-formula-manager` (Base44 export, ~10k lines).
The UI design (teal/slate palette, sidebar + bottom navigation, cards, status badges,
field-by-field extraction comparison) is preserved. The platform dependencies are replaced.

## Why the Base44 app got stuck

| Symptom | Cause in the Base44 code | Fix here |
|---|---|---|
| Search spins forever | `startFormulaSourceSearch` was awaited from the browser and called a Render worker synchronously (cold start 30–60 s). If Base44 killed the function, the job stayed `Searching`; `catch {}` hid the error. MEDISCA jobs were created but nothing ever ran them. | Searches are background jobs with a lease, retry with backoff, cooldown on HTTP 429 and a terminal state. Only sources with automation get jobs; others are shown as "upload PDF". The UI polls only while a job is active. |
| Extraction lost / repeated | `DraftExtractionPanel` called `ExtractDataFromUploadedFile` from the browser, sequentially, holding results in React state; `autoStart` could re-run it. | Extraction runs on the server, is stored, and is cached by file SHA-256 + provider + model + schema version. Leaving the page loses nothing. |
| Approving was slow / PDF failed | 1,148 lines of jsPDF ran in the browser, then uploaded the result. | ReportLab renders on the server at approval time; the PDF hash is stored on the approval record. |
| Inconsistent statuses | Draft and request were updated in two separate writes. | Request status is derived from its jobs/drafts in the same transaction. |
| Slow pages | Lists of 100–200 records fetched and filtered client-side; the same data re-fetched on several pages. | Server-side search/filter/pagination; one detail payload per page. |
| Editing active ingredients threw errors | The page passed `onChange` but the component expected `onChanged`; updates were sent to `FormulaActiveIngredient` records with undefined IDs; ingredients were stored twice (array + entity). | One source of truth (draft content); ingredients get stable client IDs. |
| Extracted dosage form disappeared | A fixed `<Select>` list could not display values not in the list. | Free text with suggestions. |

## Review and approval rules (server-enforced)

- Roles are assigned by an admin on the server: `technician` prepares, `pharmacist` prepares and decides, `admin` manages users.
- The approver must differ from the person who submitted the draft.
- The approver's name and licence number come from their user profile, not from a typed field.
- The approval binds the SHA-256 of the exact content the pharmacist saw; any edit after
  submission sends the draft back to preparation.
- Approved drafts are never modified. Changes create a new version linked to its predecessor.
- Decisions (approve / return / reject) are append-only records; reject/return require a note.
- An audit event is written for every state change.

This is an identified approval record, **not** a qualified electronic signature, and no
regulatory compliance is claimed.

## Not carried over

- Base44 auth (Google login, OTP registration, password reset e-mails). Accounts are created
  by an admin; users can change their own password. SSO can be added later.
- Stripe, three.js, leaflet, quill, recharts, moment, html2canvas, jsPDF — unused or replaced.
- Existing Base44 data is not migrated automatically. Export entities from Base44 and import
  with a one-off script if historical records are needed.
