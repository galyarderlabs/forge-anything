import assert from 'node:assert/strict';
import { readdir, readFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import test from 'node:test';

const __dirname = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(__dirname, '../..');
const pluginPath = resolve(repoRoot, '.opencode/plugins/forge-anything.js');
const agentsDir = resolve(repoRoot, '.opencode/agents');

async function loadPlugin() {
  const mod = await import(pathToFileURL(pluginPath).href + `?cachebust=${Date.now()}-${Math.random()}`);
  const plugin = await mod.ForgeAnythingPlugin({ client: {}, directory: repoRoot });
  return plugin;
}

test('config hook injects every rendered agent as a native subagent', async () => {
  const plugin = await loadPlugin();
  assert.equal(typeof plugin.config, 'function', 'plugin must expose config');

  const config = {};
  await plugin.config(config);

  const files = (await readdir(agentsDir)).filter((f) => f.endsWith('.md'));
  assert.ok(files.length === 54, `expected 54 agent renders, found ${files.length}`);
  assert.ok(config.agents, 'config.agents must exist after the config hook');
  assert.equal(Object.keys(config.agents).length, 54, 'every agent must be injected');

  for (const file of files) {
    const slug = file.slice(0, -3);
    const agent = config.agents[slug];
    assert.ok(agent, `agent ${slug} missing from config.agents`);
    assert.equal(agent.mode, 'subagent', `${slug} must be a subagent`);
    assert.ok(agent.description && agent.description.length > 20, `${slug} needs a description`);
    assert.match(agent.description, /Use when/, `${slug} description must say when to delegate`);
    assert.ok(agent.prompt.includes('# SOUL'), `${slug} prompt must be the soul`);
  }
});

test('config hook keeps pre-existing agents and skills paths', async () => {
  const plugin = await loadPlugin();
  const config = {
    agents: { custom: { description: 'mine', mode: 'subagent', prompt: 'do it' } },
    skills: { paths: ['/already/there'] },
  };
  await plugin.config(config);

  assert.equal(config.agents.custom.description, 'mine', 'pre-existing agent must survive');
  assert.ok(config.agents.research, 'rendered agents must be added alongside');
  assert.ok(config.skills.paths.includes('/already/there'), 'pre-existing skill path must survive');
});

test('injected agent prompt matches the rendered file body', async () => {
  const plugin = await loadPlugin();
  const config = {};
  await plugin.config(config);

  const rendered = await readFile(resolve(agentsDir, 'research.md'), 'utf8');
  const body = rendered.replace(/^---\n[\s\S]*?\n---\n/, '').trim();
  assert.equal(config.agents.research.prompt, body, 'research prompt is the rendered body');
});
