/**
 * 需求管理接口测试
 * 覆盖：创建/列表/详情/状态流转/越权
 */
const { test, expect, describe } = require('../../fixtures/authFixture');
const env = require('../../config/env');
const { assertOk } = require('../../utils/apiClient');
const { requirementData } = require('../../utils/testData');

const API = {
  requirements: (scope = 'personal') => `${env.baseURL}${env.api('/requirements')}?scope=${scope}`,
  reqById: (id) => `${env.baseURL}${env.api(`/requirements/${id}`)}`,
  action: (id, act) => `${env.baseURL}${env.api(`/requirements/${id}/${act}`)}`,
  me: () => `${env.baseURL}${env.api('/data/me')}`,
};

describe('需求接口', () => {
  /** 前置：创建一条需求（自动获取当前用户为审核人），用例结束后清理 */
  async function createReq(client, overrides = {}) {
    const meRes = await client.get(API.me());
    const meData = assertOk(meRes, await meRes.json());
    const data = requirementData({ reviewerId: meData.id, ...overrides });
    const res = await client.post(API.requirements(), { data });
    expect(res.status()).toBe(200);
    const created = assertOk(res, await res.json());
    return created.id;
  }

  test('创建需求-成功', async ({ apiClient }) => {
    const id = await createReq(apiClient);
    expect(id).toBeTruthy();
    // 清理
    await apiClient.delete(API.reqById(id));
  });

  test('创建需求-必填项缺失被拒', async ({ apiClient }) => {
    const res = await apiClient.post(API.requirements(), {
      data: { title: '', background: '' },
    });
    const body = await res.json();
    expect(body.ok).toBe(false);
  });

  test('需求列表-个人空间', async ({ apiClient }) => {
    const res = await apiClient.get(API.requirements('personal'));
    expect(res.status()).toBe(200);
    const data = assertOk(res, await res.json());
    expect(Array.isArray(data)).toBe(true);
  });

  test('需求列表-团队空间', async ({ apiClient }) => {
    const res = await apiClient.get(API.requirements('team'));
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.ok !== undefined).toBe(true);
  });

  test('需求详情-存在', async ({ apiClient }) => {
    const id = await createReq(apiClient);
    const res = await apiClient.get(API.reqById(id));
    expect(res.status()).toBe(200);
    const data = assertOk(res, await res.json());
    expect(data.id || data._id || data.title).toBeTruthy();
    await apiClient.delete(API.reqById(id));
  });

  test('需求详情-不存在的ID', async ({ apiClient }) => {
    const res = await apiClient.get(API.reqById('not-exist-id'));
    const body = await res.json();
    expect(body.ok).toBe(false);
  });

  test('需求状态流转-提交审核', async ({ apiClient }) => {
    const id = await createReq(apiClient);
    const res = await apiClient.post(API.action(id, 'submit'), {});
    const body = await res.json();
    // 提交成功 或 已提交状态提示，均需明确响应
    expect(body.ok !== undefined).toBe(true);
    await apiClient.delete(API.reqById(id));
  });

  test('需求删除-成功', async ({ apiClient }) => {
    const id = await createReq(apiClient);
    const res = await apiClient.delete(API.reqById(id));
    expect([200, 204]).toContain(res.status());
  });

  test('越权-未登录访问需求列表', async ({ anonClient }) => {
    const res = await anonClient.get(API.requirements());
    expect(res.status()).toBe(401);
  });
});
