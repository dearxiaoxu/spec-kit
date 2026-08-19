/**
 * 测试数据生成器
 * 统一生成带时间戳的测试数据，避免并发/重复执行时数据冲突
 */

/** 当前时间戳（用于数据唯一性） */
function ts() {
  return Date.now().toString(36);
}

/** 生成唯一标题 */
function uniqueTitle(prefix) {
  return `[测试]${prefix}-${ts()}`;
}

/** 生成需求测试数据（字段结构依据前端表单模型） */
function requirementData(overrides = {}) {
  return {
    title: uniqueTitle('需求'),
    description: '测试用需求描述',
    acceptanceCriteria: '验收标准：流程可正常流转',
    businessBackground: '测试用业务背景描述',
    businessGoal: '测试目标',
    nonGoals: '非目标',
    userRoles: '测试人员',
    coreFlow: '核心流程',
    dataScope: '数据范围',
    interfaceImpact: '接口影响',
    boundaryConditions: '边界条件',
    riskPoints: '风险点',
    category: 'feature',          // feature/business/technical/non_functional/ui_ux
    urgency: 3,                    // 1/3/5
    importance: 3,                 // 1/3/5
    estimatedCfp: 0,
    requirementLevel: '',
    forceFullSdd: false,
    source: 'internal',            // internal/...
    reviewerId: '',
    ...overrides,
  };
}

/** 生成待办测试数据 */
function taskData(overrides = {}) {
  return {
    title: uniqueTitle('待办'),
    priority: 'P2',
    dueDate: null,
    ...overrides,
  };
}

/** 生成 SDD 项目测试数据 */
function sddProjectData(overrides = {}) {
  return {
    name: uniqueTitle('SDD项目'),
    description: '测试用规范驱动项目',
    ...overrides,
  };
}

/** 生成文档上传数据（需与 playwright file payload 结合） */
function docPayload(overrides = {}) {
  return {
    name: `${uniqueTitle('文档')}.md`,
    mimeType: 'text/markdown',
    buffer: Buffer.from('# 测试文档\n\n这是自动测试生成的文档内容。'),
    ...overrides,
  };
}

module.exports = {
  ts,
  uniqueTitle,
  requirementData,
  taskData,
  sddProjectData,
  docPayload,
};
