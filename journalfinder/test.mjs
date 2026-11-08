// Tests for the journalfinder bundle: `node --test test.mjs`.
// The Python tests run only when the runner finds python3 (or python) 3.10+.

import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { test } from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

import * as plugin from './index.js'

const root = dirname(fileURLToPath(import.meta.url))
const skillDir = join(root, 'skills', 'find-journal')
const scripts = join(skillDir, 'scripts')
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

test('skill frontmatter name matches its directory and resources ship with it', () => {
  const text = readFileSync(join(skillDir, 'SKILL.md'), 'utf8')
  const front = text.match(/^---\n([\s\S]*?)\n---\n/)
  assert.ok(front, 'SKILL.md needs YAML frontmatter')
  assert.match(front[1], /^name: find-journal$/m)
  assert.match(front[1], /^description: /m)
  assert.doesNotMatch(text, /~\/\.claude/, 'SKILL.md must not point at a Claude Code install path')
  for (const file of [
    'scripts/query_db.py', 'scripts/parse_manuscript.py', 'scripts/runtime_paths.py',
    'data/journals_ssci.json', 'data/business_rankings.json',
    'references/data-schema.md', 'references/ACKNOWLEDGMENTS.md', 'references/LICENSE.txt',
  ]) {
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

// --- Python integration: the bundled scripts find the bundled data from any cwd.

const python = ['python3', 'python'].find((bin) => {
  const r = spawnSync(bin, ['-c', 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'])
  return r.status === 0
})

function runPy(script, args) {
  const env = { ...process.env }
  delete env.JOURNAL_FINDER_DATA_DIR
  const r = spawnSync(python, [join(scripts, script), ...args], {
    cwd: tmpdir(), env, encoding: 'utf8', maxBuffer: 64 << 20,
  })
  assert.equal(r.status, 0, r.stderr || r.stdout)
  return JSON.parse(r.stdout)
}

test('Python: keyword query returns ranked journals from the bundled data', { skip: !python && 'python not found' }, () => {
  const out = runPy('query_db.py', ['--keywords', 'minimum wage,youth employment,labor market', '--top', '5'])
  assert.equal(out.total_in_database, 5183)
  assert.equal(out.query.data_dir, join(skillDir, 'data'))
  assert.equal(out.query.semantic_search, false)
  assert.equal(out.query.business_rankings.loaded, true)
  assert.equal(out.quality.status, 'ok')
  assert.equal(out.results.length, 5)
  for (const r of out.results) {
    assert.ok(r.name && r.issn_l, 'each result has a name and ISSN-L')
    assert.equal(typeof r._final_score, 'number')
  }
})

test('Python: UTD24 filter keeps only UTD24 journals', { skip: !python && 'python not found' }, () => {
  const out = runPy('query_db.py', ['--keywords', 'corporate finance,capital structure', '--utd24-only', '--top', '5'])
  assert.ok(out.results.length > 0)
  for (const r of out.results) assert.equal(r.utd24, true, `${r.name} should be UTD24`)
})

test('Python: a text manuscript is parsed and drives the query', { skip: !python && 'python not found' }, () => {
  const dir = mkdtempSync(join(tmpdir(), 'jf-'))
  try {
    const file = join(dir, 'paper.txt')
    writeFileSync(file, [
      'Minimum Wages and Youth Employment: Evidence from China',
      '',
      'Abstract',
      'We study how minimum wage increases affect youth employment using a difference-in-differences design and county panel data from China.',
      '',
      'Keywords: minimum wage; youth employment; labor market',
      '',
      '1. Introduction',
      'Minimum wage policy is debated. '.repeat(200),
      '',
      'References',
      'Card, D. and Krueger, A. (1994). Minimum wages and employment. American Economic Review.',
    ].join('\n'))
    const parsed = runPy('parse_manuscript.py', [file])
    assert.match(parsed.title, /Minimum Wages/)
    assert.ok(parsed.word_count_body > 500)
    const out = runPy('query_db.py', ['--manuscript', file, '--top', '3'])
    assert.equal(out.query.manuscript.keyword_source, 'manuscript')
    assert.ok(out.results.length > 0)
    assert.ok(out.results[0]._word_limit_check.status)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})
