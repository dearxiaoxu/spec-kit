# Platform Modules Coverage Design

## Objective

Represent the 14 browser-observed Spec-Kit module surfaces as first-class governed assets and connect them to discovery, coverage gates, candidate test generation, and reviewable Case output without pretending that UI routes are API contracts.

## Source and scope

The source is the authorized read-only browser scan recorded in `spec-kit-pipeline/artifacts/discovery/live-platform-20260824/`. The governed module surfaces are:

1. Inbox
2. Requirement Assistant
3. Dashboard
4. Requirements
5. Task Projects
6. SDD
7. Documents
8. Team Board
9. History
10. Tutorial
11. Admin Users
12. Admin AI
13. Admin SDD Prompts
14. Admin COSMIC

The change does not perform production writes, AI calls, imports, exports, role changes, password resets, archiving, or deletion.

## Architecture

### Module registry

Add `spec-kit-pipeline/assets/platform-modules.json` as the authoritative registry. Each module records:

- stable module ID and display name;
- UI route and applicable space;
- observed capabilities;
- risk classification;
- permitted probe mode;
- linked API evidence, if confirmed;
- expected test references;
- coverage policy and manual/blocking reason.

UI routes remain separate from `assets/contract/key-contracts.json`. `api_evidence_refs` only link confirmed evidence; absence of a link must remain explicit.

### Discovery

`discover.py` accepts a module registry, validates it is inside the authorized workspace, and emits modules under `assets.modules`. Existing endpoint discovery remains unchanged. Module evidence records the registry path and content hash.

`discovered-assets.schema.json` and the manual validator require unique IDs, relative routes, valid spaces, valid risk/probe values, and explicit coverage policy.

### Coverage gate

Extend `contract_diff` in fallback mode to report module coverage independently from API coverage. A module is acceptable when it has at least one matching automated test reference or explicitly declares `manual-only`/`blocked` with a non-empty reason. Missing, contradictory, or silently uncovered modules fail the required release gate.

Gate metrics distinguish:

- automated;
- candidate;
- manual-only;
- blocked;
- missing.

### Case generation

`generate_cases.py` produces module candidates in addition to endpoint candidates. Default dimensions are:

- page reachability;
- authorization boundary;
- empty-state rendering;
- navigation/filter behavior;
- safe read-only capability checks.

High-risk capabilities such as create, approve, delete, archive, import/export, role change, password reset, model connection test, and AI generation never become automatically executable. Their cases remain `CANDIDATE` or `BLOCKED`, carry human confirmations, and identify the required isolated environment or manual procedure.

### Validation and compatibility

Existing endpoint documents without `assets.modules` remain readable for compatibility, but validation of a scan configured with a module registry requires exactly the registry contents. Candidate IDs remain deterministic and use `case_id`.

## Error handling

- Duplicate module IDs or routes: validation failure.
- Absolute or traversal routes: policy failure.
- Unknown capability/risk/probe value: validation failure.
- Missing expected test reference: gate failure unless explicitly manual-only or blocked with reason.
- UI route with no API evidence: allowed and reported, never converted into an endpoint.
- High-risk module marked automatically executable: policy failure.

## Tests

Add focused Python tests for:

- registry contains exactly 14 unique modules;
- registry parsing and evidence hashing;
- discovered schema/manual validation;
- module coverage status classification;
- missing coverage gate failure;
- deterministic Case generation for all modules;
- high-risk capabilities never self-approve;
- existing endpoint discovery and Case generation remain compatible.

Run Python tests, Python compilation, JSON validation, ESLint, Playwright unit tests, mutation tests when affected, and `pipeline.py --stage release`.

## Acceptance criteria

- validated discovery emits 14 modules;
- generated candidate output represents all 14 module IDs;
- every module has automated, candidate, manual-only, or blocked status;
- no high-risk case is `AUTOMATABLE` without explicit review and supported cleanup;
- fallback contract metrics report API and module coverage separately;
- no production state is changed during validation;
- required test suites and release gate pass.
