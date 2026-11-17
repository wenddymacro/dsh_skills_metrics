// sfcmodeler 插件的测试：`node --test test.mjs`。
// Python 集成测试只在找到装有依赖的 Python 时运行；用 SFC_PYTHON 指定解释器（默认 python3）。

import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { existsSync, mkdtempSync, readFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { test } from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

import * as plugin from './index.js'

const root = dirname(fileURLToPath(import.meta.url))
const skillDir = join(root, 'skills', 'sfc-modeler')
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

test('skill frontmatter name matches its directory and the resources ship', () => {
  const text = readFileSync(join(skillDir, 'SKILL.md'), 'utf8')
  const front = text.match(/^---\n([\s\S]*?)\n---\n/)
  assert.ok(front, 'SKILL.md needs YAML frontmatter')
  assert.match(front[1], /^name: sfc-modeler$/m)
  assert.match(front[1], /^description: /m)
  for (const file of [
    'reference.md', 'scripts/sfc_run.py', 'scripts/sfc_doctor.py', 'vendor/LICENSE',
    'vendor/SFCmodeler/__init__.py', 'vendor/SFCmodeler/SFCmodel.py',
    'examples/sim.py', 'examples/pc.py', 'examples/pc_matrices.py', 'examples/lp.py',
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

// --- Python 集成测试：四个示例都要求解成功、恒等式全部通过。

const python = process.env.SFC_PYTHON || 'python3'
const doctor = spawnSync(python, [join(skillDir, 'scripts', 'sfc_doctor.py')], { encoding: 'utf8' })
const hasPython = doctor.status === 0
const skip = !hasPython && `no Python with SFCmodeler's dependencies (${python}); set SFC_PYTHON`

function runModel(example, args) {
  const out = mkdtempSync(join(tmpdir(), 'sfc-test-'))
  try {
    const res = spawnSync(python, [join(skillDir, 'scripts', 'sfc_run.py'), join(skillDir, 'examples', example), ...args, '--out', out],
      { encoding: 'utf8', maxBuffer: 16 << 20 })
    assert.equal(res.status, 0, res.stderr)
    const summary = readFileSync(join(out, 'summary.md'), 'utf8')
    // 在删除临时目录之前把全部 CSV 读进来
    const tables = {}
    for (const name of ['results.csv', 'baseline.csv', 'diff.csv', 'checks.csv']) {
      const path = join(out, name)
      if (existsSync(path)) tables[name] = readFileSync(path, 'utf8').trim().split('\n').map((l) => l.split(','))
    }
    const csv = (name) => {
      assert.ok(tables[name], `${name} should be written`)
      return tables[name]
    }
    return { summary, csv, stdout: res.stdout }
  } finally {
    rmSync(out, { recursive: true, force: true })
  }
}

function lastValue(rows, column) {
  const i = rows[0].indexOf(column)
  assert.ok(i > 0, `column ${column}`)
  return Number(rows.at(-1)[i])
}

test('Python: SIM reaches Y* = G/theta = 100 and passes every identity', { skip, timeout: 300_000 }, () => {
  const { summary, csv } = runModel('sim.py', ['--warmup', '400', '--periods', '1'])
  assert.match(summary, /已到达稳态/)
  assert.doesNotMatch(summary, /不通过/)
  assert.ok(Math.abs(lastValue(csv('results.csv'), 'Y') - 100) < 1e-3)
})

test('Python: PC steady state matches Godley & Lavoie and a rate rise raises output', { skip, timeout: 300_000 }, () => {
  const { summary, csv } = runModel('pc.py', ['--warmup', '500', '--periods', '60', '--shock', 'Rbar=0.035@5'])
  assert.doesNotMatch(summary, /不通过/)
  const base = lastValue(csv('baseline.csv'), 'Y')
  assert.ok(Math.abs(base - 106.4865) < 1e-2, `PC baseline Y = ${base}`)
  assert.ok(lastValue(csv('diff.csv'), 'Y') > 0, 'higher interest income should raise Y in model PC')
})

test('Python: the matrix-built PC reproduces the hand-written PC exactly', { skip, timeout: 300_000 }, () => {
  const a = runModel('pc.py', ['--warmup', '500', '--periods', '20', '--shock', 'Rbar=0.035@5']).csv('results.csv')
  const b = runModel('pc_matrices.py', ['--warmup', '500', '--periods', '20', '--shock', 'Rbar=0.035@5'])
  assert.doesNotMatch(b.summary, /不通过/)
  assert.match(b.summary, /列和：政府/)
  const rows = b.csv('results.csv')
  for (const col of ['Y', 'C', 'V', 'Bh', 'Hh', 'Bs', 'Bcb', 'Hs']) {
    assert.ok(Math.abs(lastValue(a, col) - lastValue(rows, col)) < 1e-9, col)
  }
})

test('Python: LP starts at the book steady state and a bond-price fall passes every identity', { skip, timeout: 300_000 }, () => {
  const { summary, csv } = runModel('lp.py', ['--periods', '40', '--shock', 'Pblbar=15@10'])
  assert.doesNotMatch(summary, /不通过|警告/)
  assert.ok(lastValue(csv('diff.csv'), 'V') > 0, 'lower bond prices raise long-run household wealth in model LP')
})

test('Python: bad input is rejected with exit code 2', { skip, timeout: 120_000 }, () => {
  const run = (...args) => spawnSync(python, [join(skillDir, 'scripts', 'sfc_run.py'), join(skillDir, 'examples', 'sim.py'), ...args], { encoding: 'utf8' })
  const notParam = run('--shock', 'Y=3@2')
  assert.equal(notParam.status, 2)
  assert.match(notParam.stderr, /只能冲击参数/)
  const unknown = run('--set', 'nope=1', '--describe')
  assert.equal(unknown.status, 2)
  assert.match(unknown.stderr, /没有名为 'nope' 的项/)
})
