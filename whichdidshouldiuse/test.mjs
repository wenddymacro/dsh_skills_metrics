// Tests for the whichdidshouldiuse bundle: `node --test test.mjs`.
// The Stata integration tests run only when the runner finds a Stata binary.

import assert from 'node:assert/strict'
import { execFileSync, spawnSync } from 'node:child_process'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { test } from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

import * as plugin from './index.js'

const root = dirname(fileURLToPath(import.meta.url))
const skillDir = join(root, 'skills', 'which-did-should-i-use')
const runner = join(skillDir, 'scripts', 'run_whichdid.sh')
const pkg = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'))

test('manifest declares a bundle that ships its runtime files', () => {
  assert.equal(pkg.type, 'module')
  assert.equal(pkg.dsh.bundle.patch, './cordis.patch.yml')
  assert.equal(pkg.exports['.'], './index.js')
  assert.equal(pkg.exports['./locale/*.json'], './locale/*.json')
  for (const file of ['index.js', 'cordis.patch.yml', 'locale/*.json', 'icon.svg', 'skills']) {
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
  assert.match(front[1], /^name: which-did-should-i-use$/m)
  assert.match(front[1], /^description: /m)
  assert.match('which-did-should-i-use', /^[a-z0-9]+(?:-[a-z0-9]+)*$/)
  for (const file of ['stata/whichdidshouldiuse.ado', 'stata/whichdidshouldiuse.sthlp', 'stata/LICENSE', 'scripts/run_whichdid.sh']) {
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

test('runner rejects bad arguments before starting Stata', () => {
  const missing = spawnSync('bash', [runner, '/nonexistent.dta', 'y', 'g', 't', 'd'], { encoding: 'utf8' })
  assert.equal(missing.status, 2)
  assert.match(missing.stderr, /data file not found/)
  const short = spawnSync('bash', [runner, join(skillDir, 'data', 'wolfers2006_didtextbook.dta'), 'y'], { encoding: 'utf8' })
  assert.equal(short.status, 2)
})

// --- Stata integration: the four textbook panels must reproduce the README's designs.

const hasStata = spawnSync('bash', [runner, '--which-stata']).status === 0

const PIERCE_PREP = [
  'gen lemp2001 = lemp2000 + delta2001', 'gen lemp2002 = lemp2000 + delta2002',
  'gen lemp2004 = lemp2000 + delta2004', 'gen lemp2005 = lemp2000 + delta2005',
  'reshape long lemp, i(indusid) j(year)', 'replace ntrgap = 0 if year <= 2000',
].join('; ')

const CASES = [
  { file: 'moser_voena_didtextbook.dta', vars: ['patents', 'subclass', 'year', 'twea'], design: 'CLA' },
  { file: 'wolfers2006_didtextbook.dta', vars: ['div_rate', 'state', 'year', 'udl'], design: 'SAD' },
  { file: 'gentzkowetal_didtextbook.dta', vars: ['prestout', 'cnty90', 'year', 'numdailies'], design: 'SFSD', sub: ['sfsd_case', 'shared-baseline'] },
  { file: 'pierce_schott_didtextbook.dta', vars: ['lemp', 'indusid', 'year', 'ntrgap'], design: 'HAD', sub: ['had_case', 'quasi-stayers'], prep: PIERCE_PREP },
]

for (const c of CASES) {
  test(`Stata: ${c.file} is ${c.design}`, { skip: !hasStata && 'Stata not found', timeout: 600_000 }, (t) => {
    const args = [runner, ...(c.prep ? ['--prep', c.prep] : []), join(skillDir, 'data', c.file), ...c.vars]
    const out = execFileSync('bash', args, { encoding: 'utf8', maxBuffer: 16 << 20 })
    assert.match(out, new RegExp(`r\\(design\\) : "${c.design}"`))
    assert.doesNotMatch(out, /Serial number|Licensed to/, 'the Stata banner must be stripped')
    if (!c.sub) return
    // An SSC did_had older than the `_no_updates` option fails with rc 198, which the
    // command reports as `undetermined`: a machine problem, not a classification one.
    if (/r\(had_why\) : "did_had did not return a QS test \(rc = 198\)"/.test(out)) {
      t.skip('installed did_had is outdated; run `ssc install did_had, replace` in Stata')
      return
    }
    assert.match(out, new RegExp(`r\\(${c.sub[0]}\\) : "${c.sub[1]}"`))
  })
}
