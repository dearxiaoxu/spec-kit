class ResourceTracker {
  constructor() {
    this.resources = [];
    this.cleanupFailures = [];
  }

  track({ type, id, title = '', cleanup }) {
    if (!type || !id || typeof cleanup !== 'function') {
      throw new Error('资源登记必须包含 type、id 和 cleanup');
    }
    this.resources.push({ type, id, title, cleanup });
    return id;
  }

  async cleanupAll() {
    const leftovers = [];
    for (const resource of [...this.resources].reverse()) {
      try {
        const response = await resource.cleanup(resource);
        const status = response && typeof response.status === 'function' ? response.status() : 204;
        if (![200, 202, 204, 404].includes(status)) {
          throw new Error(`HTTP ${status}`);
        }
      } catch (error) {
        const failure = { type: resource.type, id: resource.id, title: resource.title, error: error.message };
        this.cleanupFailures.push(failure);
        leftovers.push(failure);
      }
    }
    this.resources = [];
    if (leftovers.length) {
      throw new Error(`资源清理失败: ${JSON.stringify(leftovers)}`);
    }
  }
}

async function safeCleanup(label, operation) {
  let response;
  try {
    response = await operation();
  } catch (error) {
    throw new Error(`资源清理失败 ${label}: ${error.message}`);
  }
  const status = response && typeof response.status === 'function' ? response.status() : 204;
  if (![200, 202, 204, 404].includes(status)) {
    throw new Error(`资源清理失败 ${label}: HTTP ${status}`);
  }
  return response;
}

module.exports = { ResourceTracker, safeCleanup };
