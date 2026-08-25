# Document Center Upload, Read, and Performance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add business-valid API and UI tests for document upload/read across seven formats, plus a 10×1MB concurrency-3 performance baseline with strict P95 and cleanup guarantees.

**Architecture:** Extend the existing Playwright `ApiClient` with multipart support, add focused document fixture/statistics utilities, then build API-first lifecycle/format/failure/performance coverage and one Chromium UI smoke flow. Keep document tests behind the existing isolated/stateful safety gate and register every created document with `ResourceTracker` immediately after receiving its ID.

**Tech Stack:** Node.js CommonJS, Playwright Test, built-in `Buffer`, existing `ApiClient`, `ResourceTracker`, ESLint. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-25-document-center-upload-read-performance-design.md`

## Global Constraints

- Target environment must be `TEST_ENV_TYPE=isolated` with `ALLOW_STATEFUL_TESTS=true`.
- Do not add runtime or test dependencies.
- Performance workload is exactly 10 Markdown files of 1MB each with concurrency 3.
- Upload P95 must be at most 3000ms; read P95 must be at most 1000ms; failure rate must be 0%.
- Normal format matrix is `.md`, `.txt`, `.json`, `.csv`, `.pdf`, `.docx`, `.xlsx`.
- All fixtures contain synthetic test content only; credentials and tokens must not appear in fixtures or reports.
- Every successfully created document ID must be registered for exact cleanup; cleanup failures fail the test.
- API assertions must validate business payloads and content identity, not only HTTP status.

---

### Task 1: Multipart request support and deterministic performance statistics

**Files:**
- Modify: `spec-kit-autotest/utils/apiClient.js`
- Create: `spec-kit-autotest/utils/performanceStats.js`
- Modify: `spec-kit-autotest/tests/unit/utils.spec.js`

**Interfaces:**
- Consumes: existing `ApiClient.request_(method, url, options)` and Playwright `APIRequestContext`.
- Produces: multipart-aware `ApiClient.request_(method, url, { data, params, headers, multipart })`.
- Produces: `nearestRank(values: number[], percentile: number): number`.
- Produces: `summarizeDurations(values: number[]): { count, min, median, p95, max }`.

- [ ] **Step 1: Add failing multipart and statistics unit tests**

Add tests that verify multipart is passed unchanged and JSON `Content-Type` is removed so Playwright can generate the multipart boundary:

```js
test('multipart 请求透传文件并让 Playwright 生成 boundary', async () => {
  let options;
  const request = { post: async (_url, value) => { options = value; return response(200, {}); } };
  const client = new ApiClient(request);
  client.setTokens('access', 'refresh');
  const file = { name: 'case.md', mimeType: 'text/markdown', buffer: Buffer.from('marker') };
  await client.post('/docs/upload', { multipart: { file, scope: 'personal' } });
  expect(options.multipart).toEqual({ file, scope: 'personal' });
  expect(options.headers).toEqual({ Authorization: 'Bearer access' });
  expect(options.data).toBeUndefined();
});
```

Add exact percentile and invalid-input tests:

```js
test('性能统计使用 nearest-rank 并返回完整摘要', () => {
  expect(nearestRank([100, 20, 40, 60, 80], 0.95)).toBe(100);
  expect(summarizeDurations([50, 10, 30, 20, 40])).toEqual({
    count: 5, min: 10, median: 30, p95: 50, max: 50,
  });
});

test('性能统计拒绝空数组和非法耗时', () => {
  expect(() => summarizeDurations([])).toThrow(/至少一个耗时样本/);
  expect(() => summarizeDurations([10, -1])).toThrow(/非负有限数值/);
  expect(() => nearestRank([10], 0)).toThrow(/percentile/);
});
```

- [ ] **Step 2: Run the focused unit tests and verify RED**

Run:

```bash
cd spec-kit-autotest
SKIP_REMOTE_SETUP=true npx playwright test --project=unit tests/unit/utils.spec.js
```

Expected: failures because multipart is not forwarded and `performanceStats` does not exist.

- [ ] **Step 3: Implement multipart handling and statistics**

In `ApiClient.request_`, build request options without JSON content type for multipart:

```js
async request_(method, url, { data, params, headers, multipart } = {}) {
  const requestHeaders = this.headers(headers);
  if (multipart) delete requestHeaders['Content-Type'];
  return this.request[method](url, {
    ...(data !== undefined ? { data } : {}),
    ...(params !== undefined ? { params } : {}),
    ...(multipart !== undefined ? { multipart } : {}),
    headers: requestHeaders,
  });
}
```

Implement `performanceStats.js` with copied/sorted inputs and strict validation:

```js
function sortedSamples(values) {
  if (!Array.isArray(values) || values.length === 0) throw new Error('至少一个耗时样本');
  if (values.some((value) => !Number.isFinite(value) || value < 0)) {
    throw new Error('耗时必须为非负有限数值');
  }
  return [...values].sort((a, b) => a - b);
}

function nearestRank(values, percentile) {
  if (!(percentile > 0 && percentile <= 1)) throw new Error('percentile 必须在 (0, 1]');
  const samples = sortedSamples(values);
  return samples[Math.ceil(percentile * samples.length) - 1];
}

function summarizeDurations(values) {
  const samples = sortedSamples(values);
  return {
    count: samples.length,
    min: samples[0],
    median: nearestRank(samples, 0.5),
    p95: nearestRank(samples, 0.95),
    max: samples[samples.length - 1],
  };
}

module.exports = { nearestRank, summarizeDurations };
```

- [ ] **Step 4: Run unit tests and lint**

Run:

```bash
npm run test:unit
npm run lint
```

Expected: both commands exit 0.

- [ ] **Step 5: Commit the utility slice**

```bash
git add spec-kit-autotest/utils/apiClient.js spec-kit-autotest/utils/performanceStats.js spec-kit-autotest/tests/unit/utils.spec.js
git commit -m "test: add multipart and performance helpers"
```

---

### Task 2: Synthetic multi-format document fixtures

**Files:**
- Create: `spec-kit-autotest/tests/fixtures/documents/documentFixtures.js`
- Modify: `spec-kit-autotest/tests/unit/utils.spec.js`

**Interfaces:**
- Consumes: Node.js `Buffer` only.
- Produces: `documentFormatCases(marker: string): Array<{ extension, mimeType, name, buffer, expectedMarker, readMode }>`.
- Produces: `markdownPerformanceFile(index: number, sizeBytes?: number): { name, mimeType, buffer, marker }`.
- Produces: `invalidDocumentCases(marker: string)` for zero-byte and disguised-content inputs.

- [ ] **Step 1: Add failing fixture contract tests**

```js
test('文档 fixture 覆盖七种格式且不复用可变 Buffer', () => {
  const cases = documentFormatCases('marker-1');
  expect(cases.map((item) => item.extension)).toEqual(['md', 'txt', 'json', 'csv', 'pdf', 'docx', 'xlsx']);
  expect(cases.every((item) => item.name.includes('marker-1'))).toBe(true);
  expect(cases.every((item) => Buffer.isBuffer(item.buffer) && item.buffer.length > 0)).toBe(true);
  expect(new Set(cases.map((item) => item.buffer)).size).toBe(7);
});

test('性能 fixture 精确生成 1MB 且每份标记唯一', () => {
  const files = Array.from({ length: 10 }, (_, index) => markdownPerformanceFile(index));
  expect(files.every((file) => file.buffer.length === 1024 * 1024)).toBe(true);
  expect(new Set(files.map((file) => file.marker)).size).toBe(10);
  expect(files.every((file) => file.buffer.includes(Buffer.from(file.marker)))).toBe(true);
});
```

- [ ] **Step 2: Run focused tests and verify RED**

Run the unit project and confirm module-not-found or missing-function failures.

- [ ] **Step 3: Implement deterministic fixtures**

Use plain UTF-8 buffers for text formats. Store minimal valid PDF, DOCX and XLSX templates as in-source base64 constants, decode a fresh buffer per call, and replace a reserved ASCII marker token with an equal-length generated marker. Fail fixture construction if the token is absent or marker length differs, so binary corruption cannot become a fake green.

`markdownPerformanceFile` must allocate exactly `sizeBytes`, write a header containing `DOC-PERF-<index>-<run marker>`, and fill the remaining bytes with deterministic ASCII content.

- [ ] **Step 4: Run unit tests and lint**

Run `npm run test:unit && npm run lint`; expect exit 0.

- [ ] **Step 5: Commit fixture support**

```bash
git add spec-kit-autotest/tests/fixtures/documents/documentFixtures.js spec-kit-autotest/tests/unit/utils.spec.js
git commit -m "test: add synthetic document fixtures"
```

---

### Task 3: Document API lifecycle, format, failure, and performance cases

**Files:**
- Create: `spec-kit-autotest/tests/api/documents.spec.js`
- Modify: `spec-kit-autotest/fixtures/authFixture.js`

**Interfaces:**
- Consumes: `documentFormatCases`, `markdownPerformanceFile`, `invalidDocumentCases`, `summarizeDurations`, `ResourceTracker`, `apiLogin`.
- Produces: API coverage for `/docs/upload`, `/docs/list`, `/docs/view`, and `/docs/delete`.
- Produces: `adminClient` fixture authenticated with `env.adminUsername/env.adminPassword`.

- [ ] **Step 1: Add an admin client fixture and its failing unit-level contract check**

Extend `authFixture.js`:

```js
adminClient: async ({ request }, use) => {
  const client = await apiLogin(request, {
    username: env.adminUsername,
    password: env.adminPassword,
  });
  await use(client);
},
```

Import `env` in the fixture and verify the test file can list cases with `SKIP_REMOTE_SETUP=true npx playwright test --project=api tests/api/documents.spec.js --list` after the file is created.

- [ ] **Step 2: Write the API test skeleton with strict response helpers**

Define exact endpoints and helpers:

```js
const API = {
  list: () => `${env.baseURL}${env.api('/docs/list')}`,
  upload: () => `${env.baseURL}${env.api('/docs/upload')}`,
  view: () => `${env.baseURL}${env.api('/docs/view')}`,
  delete: () => `${env.baseURL}${env.api('/docs/delete')}`,
};

async function uploadDocument(client, file, tracker) {
  const started = performance.now();
  const response = await client.post(API.upload(), {
    multipart: { file, docType: 'personal', scope: 'personal' },
  });
  const durationMs = performance.now() - started;
  const body = await response.json();
  expect(response.status()).toBe(200);
  expect(body.ok).toBe(true);
  expect(body.data.id).toBeTruthy();
  tracker.track({
    type: 'document', id: body.data.id, title: file.name,
    cleanup: () => client.post(API.delete(), { data: { id: body.data.id } }),
  });
  return { document: body.data, durationMs };
}
```

`viewDocument` must parse `{ok:true,data}` and extract content from documented response fields. If no supported content field exists, fail with a diagnostic containing only field names, not document content.

- [ ] **Step 3: Add lifecycle and seven-format cases**

For lifecycle, assert ID, original filename, list membership, unique content marker, then delete explicitly and verify it disappears. Remove the explicitly deleted resource from tracker or make cleanup accept 404.

For each format case, upload and assert metadata. Text cases require exact unique marker in view content. PDF/DOCX/XLSX cases poll view every 500ms for at most 15 seconds and require either extracted marker content or a documented successful preview representation tied to the same document ID; a parse error or terminal failure fails immediately.

- [ ] **Step 4: Add failure-path cases**

Assertions:

```js
expect([400, 401, 403, 415, 422]).toContain(response.status());
expect(response.status()).toBeLessThan(500);
```

Cover anonymous upload, anonymous view, missing file field, zero-byte file, disguised extension and nonexistent ID. A server policy that accepts disguised content is allowed only if the response explicitly reports the detected type and view remains safe; otherwise the case fails.

- [ ] **Step 5: Add the 10×1MB concurrency-3 performance case**

Implement a local worker pool, not `Promise.all` of all ten requests:

```js
async function mapWithConcurrency(items, concurrency, worker) {
  const results = new Array(items.length);
  let nextIndex = 0;
  async function run() {
    while (nextIndex < items.length) {
      const index = nextIndex;
      nextIndex += 1;
      results[index] = await worker(items[index], index);
    }
  }
  await Promise.all(Array.from({ length: concurrency }, run));
  return results;
}
```

Assert ten unique IDs, ten successful marker reads, upload `p95 <= 3000`, read `p95 <= 1000`, and zero rejected operations. Attach JSON statistics with `testInfo.attach('document-performance', { body, contentType: 'application/json' })` and print the same summary without tokens or full content.

- [ ] **Step 6: Run list-only validation, then execute the API file**

Run:

```bash
SKIP_REMOTE_SETUP=true npx playwright test --project=api tests/api/documents.spec.js --list
npx playwright test --project=api tests/api/documents.spec.js
```

Expected: list discovery succeeds; execution either passes or reports a product defect with endpoint, status, business message, and measured timing. Do not weaken assertions to accommodate a failure.

- [ ] **Step 7: Commit API coverage**

```bash
git add spec-kit-autotest/fixtures/authFixture.js spec-kit-autotest/tests/api/documents.spec.js
git commit -m "test: cover document upload read and performance"
```

---

### Task 4: Document center UI smoke flow with API cleanup

**Files:**
- Create: `spec-kit-autotest/tests/ui/documents.spec.js`

**Interfaces:**
- Consumes: `uiLogin`, `docPayload`, Playwright page/request fixtures, document list/delete API.
- Produces: Chromium UI validation for page controls, upload result card, and preview content.

- [ ] **Step 1: Write the UI test with business assertions**

The test must:

1. Login and navigate to `/docs?scope=personal`.
2. Assert heading `文档中心`, tab `个人文档`, and enabled `上传文档` button.
3. Use `page.waitForResponse` around `setInputFiles` to capture the upload response and document ID.
4. Assert the card contains the exact unique filename and a non-empty size/type metadata value.
5. Click that card and assert the preview dialog title and unique marker content.
6. Register the response ID with `ResourceTracker` or delete it in `finally`, checking cleanup status.

Do not use fixed sleeps as success criteria. Wait on the upload response, exact card and exact preview marker.

- [ ] **Step 2: Verify test discovery before remote execution**

Run:

```bash
SKIP_REMOTE_SETUP=true npx playwright test --project=ui-chromium tests/ui/documents.spec.js --list
```

Expected: exactly the intended document UI cases are listed.

- [ ] **Step 3: Execute Chromium UI test**

Run:

```bash
npx playwright test --project=ui-chromium tests/ui/documents.spec.js
```

Expected: page controls, uploaded card and preview marker all pass; cleanup executes even if preview fails.

- [ ] **Step 4: Commit UI coverage**

```bash
git add spec-kit-autotest/tests/ui/documents.spec.js
git commit -m "test: cover document center upload preview flow"
```

---

### Task 5: Register the isolated document suite and run regression gates

**Files:**
- Modify: `spec-kit-autotest/scripts/run-suite.js`
- Modify: `spec-kit-autotest/package.json`
- Modify: `spec-kit-autotest/docs/test-inventory.json`
- Modify: `spec-kit-pipeline/assets/platform-modules.json`
- Modify: `spec-kit-pipeline/tests/test_governance.py`

**Interfaces:**
- Consumes: API and UI document test files from Tasks 3 and 4.
- Produces: `npm run test:documents` guarded by `stateful: true` and isolated environment checks.
- Produces: automated module coverage evidence for `documents`.

- [ ] **Step 1: Add a failing governance expectation for document coverage**

Update the governance test to require `documents` policy `automated` and exact references:

```python
documents = next(item for item in registry["modules"] if item["module_id"] == "documents")
self.assertEqual(documents["coverage_policy"], "automated")
self.assertEqual(
    documents["expected_test_refs"],
    ["tests/api/documents.spec.js", "tests/ui/documents.spec.js"],
)
```

Run the focused Python test and verify it fails against the current `candidate` registry entry.

- [ ] **Step 2: Register the suite and module evidence**

Add to `run-suite.js`:

```js
documents: {
  args: ['--project=api', 'tests/api/documents.spec.js'],
  stateful: true,
  isolatedOnly: true,
},
```

Add an `isolatedOnly` guard that rejects any non-isolated environment. Add package script:

```json
"test:documents": "node scripts/run-suite.js documents"
```

Change the module registry entry to `coverage_policy: "automated"`, describe API/UI coverage, and add both exact test references.

- [ ] **Step 3: Refresh inventory and run focused safety checks**

Run:

```bash
SAFETY_CHECK_ONLY=true npm run test:documents
npm run test:inventory:update
python3 -m unittest spec-kit-pipeline.tests.test_governance -v
```

Expected: safety check reports `isolated`; inventory includes new API/UI executions; governance reports zero missing module coverage.

- [ ] **Step 4: Run all relevant verification**

Run:

```bash
cd spec-kit-autotest
npm run lint
npm run test:unit
npm run test:documents
npx playwright test --project=ui-chromium tests/ui/documents.spec.js
npm run test:inventory
cd ../spec-kit-pipeline
python3 -m unittest discover -s tests -v
python3 pipeline.py --stage release
```

Expected: all commands exit 0. If a performance threshold fails, preserve measured statistics and report it as a product/environment performance defect; do not raise thresholds without user approval.

- [ ] **Step 5: Review secrets, cleanup, and diff**

Run:

```bash
git diff --check
git status --short
git diff -- spec-kit-autotest/tests/api/documents.spec.js spec-kit-autotest/tests/ui/documents.spec.js
```

Confirm no credential values, tokens, real document content, fixed production IDs, weak assertions, skip, or xfail were introduced.

- [ ] **Step 6: Commit suite integration**

```bash
git add spec-kit-autotest/scripts/run-suite.js spec-kit-autotest/package.json spec-kit-autotest/docs/test-inventory.json spec-kit-pipeline/assets/platform-modules.json spec-kit-pipeline/tests/test_governance.py
git commit -m "test: integrate isolated document suite"
```
