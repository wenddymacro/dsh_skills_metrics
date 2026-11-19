// Tests for the statadiagnose bundle: `node --test test.mjs`.
// The Stata integration tests run only when the runner finds a Stata binary.

import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { test } from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

import * as plugin from './index.js'

const root = dirname(fileURLToPath(import.meta.url))
const skillDir = join(root, 'skills', 'stata-diagnose')
const runner = join(skillDir, 'scripts', 'run_stata.sh')
const pkg = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'))

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

test('patch mounts this package and carries no machine-specific path', () => {
  const patch = readFileSync(join(root, 'cordis.patch.yml'), 'utf8')
  assert.match(patch, new RegExp(`name: '${pkg.name}'`))
  assert.doesNotMatch(patch, /customSkillDirs|\/Users\/|[A-Z]:[\\/]/)
})

test('locale metadata is present in English and Chinese', () => {
  for (const lang of ['en', 'zh']) {
    const { meta } = JSON.parse(readFileSync(join(root, 'locale', `${lang}.json`), 'utf8'))
    assert.ok(meta.title?.trim(), `${lang} title`)
    assert.ok(meta.description?.trim(), `${lang} description`)
  }
})

test('skill frontmatter name matches its directory and is kebab-case', () => {
  const text = readFileSync(join(skillDir, 'SKILL.md'), 'utf8')
  const front = text.match(/^---\n([\s\S]*?)\n---\n/)
  assert.ok(front, 'SKILL.md needs YAML frontmatter')
  assert.match(front[1], /^name: stata-diagnose$/m)
  assert.match(front[1], /^description: /m)
  assert.match('stata-diagnose', /^[a-z0-9]+(?:-[a-z0-9]+)*$/)
  for (const file of ['scripts/run_stata.sh', 'UPSTREAM-LICENSE.txt']) {
    assert.ok(existsSync(join(skillDir, file)), `${file} should ship with the skill`)
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
})

test('apply rejects a provider module that is not a plugin', async () => {
  const ctx = { loader: { import: async () => ({}) }, plugin() { assert.fail('must not mount') } }
  await assert.rejects(plugin.apply(ctx), /did not resolve to a plugin/)
})

test('skill text carries no machine-specific path or Claude-only tool', () => {
  const text = readFileSync(join(skillDir, 'SKILL.md'), 'utf8')
  assert.doesNotMatch(text, /~\/Desktop|\$ARGUMENTS|allowed-tools|argument-hint|TaskStop|run_in_background/)
  assert.match(text, /scripts\/run_stata\.sh/)
})

test('runner rejects bad arguments before starting Stata', () => {
  const none = spawnSync('bash', [runner], { encoding: 'utf8' })
  assert.equal(none.status, 2)
  const missing = spawnSync('bash', [runner, '/nonexistent.do'], { encoding: 'utf8' })
  assert.equal(missing.status, 2)
  assert.match(missing.stderr, /do-file not found/)
  const notdo = spawnSync('bash', [runner, join(root, 'package.json')], { encoding: 'utf8' })
  assert.equal(notdo.status, 2)
  assert.match(notdo.stderr, /not a do-file/)
})

// --- Stata integration: the runner must report success, errors and silent-result warnings.

const hasStata = spawnSync('bash', [runner, '--which-stata']).status === 0

function runDo(t, body) {
  const dir = mkdtempSync(join(tmpdir(), 'runstata-'))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  writeFileSync(join(dir, 'case.do'), body)
  const res = spawnSync('bash', [runner, '--tail', '5', 'case.do'], { cwd: dir, encoding: 'utf8', timeout: 300_000 })
  assert.ok(existsSync(join(dir, 'case.log')), 'batch mode should leave case.log in the cwd')
  return res
}

const STATA = { skip: !hasStata && 'Stata not found', timeout: 300_000 }

test('Stata: a clean do-file exits 0', STATA, (t) => {
  const res = runDo(t, 'sysuse auto, clear\nregress price mpg weight\n')
  assert.equal(res.status, 0, res.stdout + res.stderr)
  assert.match(res.stdout, /^log: .*case\.log$/m)
  assert.doesNotMatch(res.stdout, /ERROR:/)
})

test('Stata: an error code exits 1 and is located', STATA, (t) => {
  const res = runDo(t, 'sysuse auto, clear\nregress price nosuchvar\n')
  assert.equal(res.status, 1)
  assert.match(res.stdout, /ERROR: Stata stopped with r\(111\)/)
  assert.match(res.stdout, /nosuchvar/)
})

test('Stata: collinearity is flagged as a warning', STATA, (t) => {
  const res = runDo(t, 'sysuse auto, clear\ngen mpg2 = 2*mpg\nregress price mpg mpg2\n')
  assert.equal(res.status, 0)
  assert.match(res.stdout, /WARNINGS[\s\S]*omitted because of collinearity/)
})

test('Stata: the batch log lands next to a do-file in a subfolder', STATA, (t) => {
  const dir = mkdtempSync(join(tmpdir(), 'runstata-'))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  mkdirSync(join(dir, 'analysis_x'))
  writeFileSync(join(dir, 'analysis_x', '01_a.do'), 'sysuse auto, clear\nsave "analysis_x/auto_copy.dta", replace\n')
  const res = spawnSync('bash', [runner, '--tail', '0', 'analysis_x/01_a.do'], { cwd: dir, encoding: 'utf8', timeout: 300_000 })
  assert.equal(res.status, 0, res.stdout + res.stderr)
  assert.ok(existsSync(join(dir, 'analysis_x', '01_a.log')), 'log should sit beside the do-file')
  assert.ok(!existsSync(join(dir, '01_a.log')), 'no batch log should be left in the project root')
  assert.ok(existsSync(join(dir, 'analysis_x', 'auto_copy.dta')), 'paths in the do-file resolve against the cwd')
})

test('Stata: --version reports a version number', STATA, () => {
  const res = spawnSync('bash', [runner, '--version'], { encoding: 'utf8', timeout: 120_000 })
  assert.equal(res.status, 0)
  assert.match(res.stdout.trim(), /^\d+(\.\d+)?$/)
})
