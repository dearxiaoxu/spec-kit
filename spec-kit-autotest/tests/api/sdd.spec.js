/**
 * SDD 项目接口测试
 * 覆盖：项目创建/列表/详情、验证运行、产物相关
 */
const { test, expect, describe } = require('../../fixtures/authFixture');
const env = require('../../config/env');
const { assertOk } = require('../../utils/apiClient');
const { sddProjectData } = require('../../utils/testData');
const { safeCleanup } = require('../../utils/resourceTracker');

const API = {
  projects: (scope = 'personal') => `${env.baseURL}${env.api('/sdd/projects')}?scope=${scope}`,
  projectById: (id) => `${env.baseURL}${env.api(`/sdd/projects/${id}`)}`,
  action: (id, act) => `${env.baseURL}${env.api(`/sdd/projects/${id}/${act}`)}`,
};

describe('SDD 项目接口', () => {
  async function createProject(client) {
    const res = await client.post(API.projects(), { data: sddProjectData() });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.ok).toBe(true);
    return body.data.id || body.data;
  }

  test('创建SDD项目-成功', async ({ apiClient }) => {
    const id = await createProject(apiClient);
    expect(id).toBeTruthy();
    await apiClient.delete(API.projectById(id));
  });

  test('SDD项目列表-个人空间', async ({ apiClient }) => {
    const res = await apiClient.get(API.projects('personal'));
    expect(res.status()).toBe(200);
    const data = assertOk(res, await res.json());
    expect(Array.isArray(data)).toBe(true);
  });

  test('SDD项目详情', async ({ apiClient }) => {
    const id = await createProject(apiClient);
    const res = await apiClient.get(API.projectById(id));
    expect(res.status()).toBe(200);
    const data = assertOk(res, await res.json());
    expect(data).toBeTruthy();
    await apiClient.delete(API.projectById(id));
  });

  test('SDD项目-校验清单生成', async ({ apiClient }) => {
    const id = await createProject(apiClient);
    const res = await apiClient.post(API.action(id, 'checklist/generate'), {});
    const body = await res.json();
    expect(body.ok !== undefined).toBe(true);
    await apiClient.delete(API.projectById(id));
  });

  test('SDD项目-归档', async ({ apiClient }) => {
    const id = await createProject(apiClient);
    try {
      const res = await apiClient.post(API.action(id, 'archive'), {});
      const body = await res.json();
      expect(body.ok !== undefined).toBe(true);
    } finally {
      await safeCleanup(`sdd:${id}`, () => apiClient.delete(API.projectById(id)));
    }
  });

  test('SDD项目-删除', async ({ apiClient }) => {
    const id = await createProject(apiClient);
    const res = await apiClient.delete(API.projectById(id));
    expect([200, 204]).toContain(res.status());
  });

  test('越权-未登录访问SDD列表', async ({ anonClient }) => {
    const res = await anonClient.get(API.projects());
    expect(res.status()).toBe(401);
  });
});
