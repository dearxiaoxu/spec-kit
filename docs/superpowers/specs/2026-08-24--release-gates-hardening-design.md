# Release Gates Hardening Design

## Objective

Make the existing `release` stage pass for real without lowering its 70% mutation threshold or disabling required scanners.

## Scope

1. Provision Semgrep in the project-local `.tools/semgrep` environment already referenced by configuration.
2. Make `MutationCheckGate` read Stryker JSON reports first and support current and legacy console formats as fallbacks.
3. Add focused unit assertions for `apiClient`, `envGuard`, `resourceTracker`, and `testData` so meaningful mutants are killed.
4. Add Python regression tests for mutation-score parsing and threshold decisions.

No production API behavior, destructive suite, AI-cost suite, release threshold, or application business code will be changed.

## Design

### Semgrep

Keep the configured release command stable. Create the local virtual environment from `requirements-tools.txt`; treat a missing executable as a configuration error. Do not silently skip the scanner.

### Mutation report parsing

The gate resolves `reports/mutation/mutation.json` relative to `autotest_dir`. It computes the score from mutant statuses, counting `Killed` and `Timeout` as detected. If the report is unavailable or invalid, it falls back to `Final mutation score N` and then the legacy percentage format. A successful process without a parseable score is not sufficient to pass a required release gate.

### Test strengthening

Add behavioral assertions rather than broad snapshots:

- `envGuard`: status/content-type boundaries, missing response fields, error metadata, and throwing behavior.
- `testData`: exact defaults, override preservation, timestamp/title shape, and document payload contents.
- `resourceTracker`: invalid registration, allowed/rejected statuses, reverse-order continuation, failure metadata, clearing, and return values.
- `apiClient`: verb routing, option/header forwarding, and `assertOk` failure diagnostics.

### Validation

Run ESLint, Playwright unit tests, Python pipeline tests, Stryker, and finally `pipeline.py --stage release`. Success requires Semgrep execution, a parsed mutation score of at least 70%, and release exit code 0.

## Failure handling

Do not weaken thresholds or exclude difficult files merely to obtain green status. If the score remains below 70%, inspect surviving mutants and add the smallest evidence-backed assertions. Preserve existing unrelated working-tree changes.
