const { execFileSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const output = execFileSync('npx', ['playwright', 'test', '--list'], {
  encoding: 'utf8',
  env: { ...process.env, SKIP_REMOTE_SETUP: 'true' },
});
const lines = output.split('\n').filter((line) => /^\s*\[/.test(line));
const projects = {};
for (const line of lines) {
  const match = line.match(/^\s*\[([^\]]+)\]/);
  if (match) projects[match[1]] = (projects[match[1]] || 0) + 1;
}
const inventory = { generatedAt: new Date().toISOString(), totalExecutions: lines.length, projects };
const serialized = `${JSON.stringify(inventory, null, 2)}\n`;
if (process.argv.includes('--write')) {
  const target = path.resolve(__dirname, '../docs/test-inventory.json');
  fs.writeFileSync(target, serialized);
  console.log(`测试清单已更新: ${target}`);
} else {
  console.log(serialized.trim());
}
