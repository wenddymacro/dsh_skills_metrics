// Tests for the statsclaw bundle: `node --test test.mjs`.

import assert from 'node:assert/strict'
import { existsSync, readdirSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { test } from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

import * as plugin from './index.js'
import { buildPatch, DISPATCH_TOOL, LEADER_ID, ROLE_IDS, ROLES, rolePersona } from './scripts/build-patch.mjs'

const root = dirname(fileURLToPath(import.meta.url))
const skillDir = join(root, 'skills', 'statsclaw')
const pkg = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'))
const patch = readFileSync(join(root, 'cordis.patch.yml'), 'utf8')
const skill = readFileSync(join(skillDir, 'SKILL.md'), 'utf8')

/** Every markdown file the skill ships, relative to the skill directory. */
function shippedMarkdown(dir = skillDir, prefix = '') {
  return readdirSync(dir, { withFileTypes: true }).flatMap(e => e.isDirectory()
    ? shippedMarkdown(join(dir, e.name), `${prefix}${e.name}/`)
    : e.name.endsWith('.md') ? [`${prefix}${e.name}`] : [])
}

test('manifest declares a bundle that ships its runtime files', () => {
  assert.equal(pkg.type, 'module')
  assert.equal(pkg.dsh.bundle.patch, './cordis.patch.yml')
  assert.equal(pkg.exports['.'], './index.js')
  assert.equal(pkg.exports['./locale/*.json'], './locale/*.json')
  for (const file of ['index.js', 'cordis.patch.yml', 'locale/*.json', 'icon.svg', 'skills', 'LICENSE', 'NOTICE']) {
    assert.ok(pkg.files.includes(file), `files should include ${file}`)
  }
  assert.ok(!pkg.dependencies, 'the bundle must not depend on packages DSH ships')
})

test('cordis.patch.yml is exactly what the generator produces', () => {
  assert.equal(patch, buildPatch(), 'run `node scripts/build-patch.mjs` after editing a role manual')
})

test('patch mounts this package and carries no machine-specific path', () => {
  assert.match(patch, new RegExp(`^ {4}- id: statsclaw-skill\\n {6}name: '${pkg.name}'$`, 'm'))
  assert.doesNotMatch(patch, /customSkillDirs|\/Users\/|\/home\/|[A-Z]:[\\/]/)
  assert.doesNotMatch(patch, /\t/, 'YAML must not contain tabs')
})

test('patch declares the leader preset and one preset per role, in order', () => {
  const ids = [...patch.matchAll(/^ {6}config:\n {8}id: (\S+)$/gm)].map(m => m[1])
  assert.deepEqual(ids, [LEADER_ID, ...ROLE_IDS])
  for (const id of ids) {
    assert.match(patch, new RegExp(`^ {4}- id: preset-${id}\\n {6}name: '@deepseek-ai/dsh-agent-preset'$`, 'm'))
  }
  assert.equal(ROLE_IDS.length, new Set(ROLE_IDS).size)
  for (const id of ROLE_IDS) assert.match(id, /^[a-z0-9]+(?:-[a-z0-9]+)*$/)
})

test('only the leader can dispatch, and only to the role presets', () => {
  const dispatch = patch.match(/- id: tool-statsclaw-dispatch\n([\s\S]*?)(?=\n {4}- id: |\n$)/)
  assert.ok(dispatch, 'dispatch tool row')
  assert.match(dispatch[1], /provider: spawn/)
  assert.match(dispatch[1], new RegExp(`toolName: ${DISPATCH_TOOL}`))
  const allowed = [...dispatch[1].matchAll(/^ {16}- (statsclaw-\S+)$/gm)].map(m => m[1])
  assert.deepEqual(allowed, ROLE_IDS)
  assert.match(dispatch[1], new RegExp(`agentPreset: ${ROLE_IDS[0]}`), 'an omitted agent_preset must not clone the leader')
  assert.equal(patch.match(/dsh-tool-subagent'/g).length, 1, 'role presets must not carry a delegation tool')
  assert.equal(patch.match(/dsh-tool-ask-user'/g).length, 1, 'only the leader may ask the user')
  const reviewer = patch.slice(patch.indexOf('- id: preset-statsclaw-reviewer'))
  assert.match(reviewer, /edit: false/, 'the reviewer cannot edit files')
})

test('personas never contain a prompt-variable brace group', () => {
  // DSH interpolates {{name}} strictly in persona text; an unknown name breaks the session.
  for (const spec of ROLES) assert.doesNotMatch(rolePersona(spec), /\{\{/, spec.role)
  assert.doesNotMatch(patch, /\{\{/)
})

test('each role manual exists and states its isolation rule', () => {
  const forbidden = {
    builder: ['test-spec.md', 'sim-spec.md'],
    tester: ['spec.md', 'implementation.md', 'sim-spec.md'],
    simulator: ['spec.md', 'test-spec.md', 'implementation.md'],
  }
  for (const spec of ROLES) {
    const text = readFileSync(join(skillDir, 'references', 'roles', `${spec.role}.md`), 'utf8')
    assert.match(text, new RegExp(`^# 角色：${spec.role}`), spec.role)
    for (const f of forbidden[spec.role] ?? []) {
      assert.match(text, new RegExp(`(不读|绝不读)[^\\n]*${f.replace('.', '\\.')}`), `${spec.role} must forbid ${f}`)
    }
  }
})

test('skill frontmatter name matches its directory', () => {
  const front = skill.match(/^---\n([\s\S]*?)\n---\n/)
  assert.ok(front, 'SKILL.md needs YAML frontmatter')
  assert.match(front[1], /^name: statsclaw$/m)
  assert.match(front[1], /^description: /m)
})

test('every file the skill points to ships with it', () => {
  const texts = [skill, ...ROLES.map(r => readFileSync(join(skillDir, 'references', 'roles', `${r.role}.md`), 'utf8'))]
  const refs = new Set(texts.flatMap(t => [...t.matchAll(/`(?:<SKILL>\/)?((?:references|templates)\/[\w./-]+\.md)`/g)].map(m => m[1])))
  assert.ok(refs.size >= 3, 'SKILL.md should point at its references')
  for (const ref of refs) assert.ok(existsSync(join(skillDir, ref)), `${ref} is referenced but missing`)
  for (const spec of ROLES) assert.match(skill, new RegExp(`statsclaw-${spec.role}|${spec.role}`))
  for (const t of ['status.md', 'log-entry.md', 'ARCHITECTURE.md']) assert.ok(existsSync(join(skillDir, 'templates', t)), t)
  assert.ok(existsSync(join(skillDir, 'UPSTREAM-LICENSE.txt')))
})

test('language profiles cover the upstream set without workspace-repo leftovers', () => {
  const profiles = readdirSync(join(skillDir, 'references', 'profiles')).sort()
  assert.deepEqual(profiles, ['c-library.md', 'cpp-library.md', 'go-module.md', 'julia-package.md', 'python-package.md',
    'r-package.md', 'rust-crate.md', 'stata-project.md', 'typescript-package.md'])
})

test('shipped text carries no Claude-Code-only machinery', () => {
  const banned = /AskUserQuestion|subagent_type|isolation: "worktree"|CLAUDE_PLUGIN|\.repos\/|gh pr create|brain-seedbank|credentials\.md|\$ARGUMENTS|allowed-tools/
  for (const rel of shippedMarkdown()) {
    const text = readFileSync(join(skillDir, rel), 'utf8')
    assert.doesNotMatch(text, banned, rel)
    assert.doesNotMatch(text, /~\/Desktop|\/Users\/[a-z]/, rel)
  }
})

test('locale metadata is present in English and Chinese', () => {
  for (const lang of ['en', 'zh']) {
    const { meta } = JSON.parse(readFileSync(join(root, 'locale', `${lang}.json`), 'utf8'))
    assert.ok(meta.title?.trim(), `${lang} title`)
    assert.ok(meta.description?.trim(), `${lang} description`)
  }
})

test('skillsDir resolves beside the module and fails loudly elsewhere', () => {
  assert.equal(plugin.skillsDir(), join(root, 'skills'))
  assert.throws(() => plugin.skillsDir(pathToFileURL('/nonexistent/index.js').href), /expected a skills\/ directory/)
})

test('apply mounts the shipped filesystem provider on skills/ only', async () => {
  const provider = { apply() {} }
  const mounted = []
  const ctx = {
    loader: {
      async import(spec) {
        assert.equal(spec, plugin.PROVIDER)
        return provider
      },
    },
    plugin(p, config) { mounted.push([p, config]) },
  }
  const result = await plugin.apply(ctx)
  assert.equal(result, undefined, 'apply must not return the child fiber')
  assert.deepEqual(mounted, [[provider, {
    providerName: plugin.PROVIDER_NAME,
    includeDefaultRoots: false,
    customSkillDirs: [join(root, 'skills')],
  }]])
  assert.deepEqual(plugin.inject, ['loader', 'skills'])
  assert.equal(plugin.name, 'statsclaw-skill')
})

test('apply rejects a provider module that is not a plugin', async () => {
  const ctx = { loader: { import: async () => ({}) }, plugin() { assert.fail('must not mount') } }
  await assert.rejects(plugin.apply(ctx), /did not resolve to a plugin/)
})
