// marcobis 插件的测试：`node --test test.mjs`。
// Python 部分只在找到 python3（或 python）3.10+ 且装有 numpy、pandas、PyYAML 时运行；
// 不联网（国家统计局接口的联网测试见 framework/tests/test_nbs.py，需要 --runslow）。

import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { dirname, join } from 'node:path'
import { test } from 'node:test'
import { fileURLToPath, pathToFileURL } from 'node:url'

import * as plugin from './index.js'
import './update-check.test.mjs'

// apply() starts a background update check; keep these tests off the network.
process.env.DSH_SKILLS_METRICS_UPDATE_CHECK = '0'

const root = dirname(fileURLToPath(import.meta.url))
const pkg = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'))
const framework = join(root, 'framework')
const SKILLS = ['marco-bis', 'nbs-data']

test('manifest declares a bundle that ships its runtime files', () => {
  assert.equal(pkg.type, 'module')
  assert.equal(pkg.dsh.bundle.patch, './cordis.patch.yml')
  assert.equal(pkg.exports['.'], './index.js')
  assert.equal(pkg.exports['./locale/*.json'], './locale/*.json')
  for (const file of ['index.js', 'cordis.patch.yml', 'locale/*.json', 'icon.svg', 'skills', 'framework', 'LICENSE', 'NOTICE']) {
    assert.ok(pkg.files.includes(file), `files should include ${file}`)
  }
  assert.ok(!pkg.dependencies, 'the bundle must not depend on packages DSH ships')
  assert.equal(pkg.license, 'Apache-2.0', 'upstream MaRCo@BIS is Apache-2.0')
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

test('upstream licence and notice ship with the plugin and the framework', () => {
  for (const dir of [root, framework]) {
    assert.match(readFileSync(join(dir, 'LICENSE'), 'utf8'), /Apache License/)
    assert.match(readFileSync(join(dir, 'NOTICE'), 'utf8'), /BANK FOR INTERNATIONAL SETTLEMENTS/)
  }
  assert.ok(existsSync(join(framework, 'MODIFICATIONS.md')), 'Apache-2.0 §4(b): modified files must be marked')
})

test('each mounted skill has frontmatter whose name matches its directory', () => {
  for (const name of SKILLS) {
    const text = readFileSync(join(root, 'skills', name, 'SKILL.md'), 'utf8')
    const front = text.match(/^---\n([\s\S]*?)\n---\n/)
    assert.ok(front, `${name}/SKILL.md needs YAML frontmatter`)
    assert.match(front[1], new RegExp(`^name: ${name}$`, 'm'))
    assert.match(front[1], /^description: /m)
    assert.doesNotMatch(text, /~\/\.claude/, 'SKILL.md must not point at a Claude Code install path')
  }
  assert.ok(existsSync(join(root, 'skills', 'marco-bis', 'scripts', 'marco_workspace.py')))
})

test('framework template is complete and outside the mounted skills directory', () => {
  for (const file of [
    'CLAUDE.md', 'config.yaml', 'requirements.txt',
    'skills/orchestrator/SKILL.md', 'skills/data-retrieval/SKILL.md',
    'scripts/lib/__init__.py', 'scripts/lib/data/nbs_client.py', 'scripts/lib/data/fetchers/nbs.py',
    'scripts/lib/preprocess/china.py', 'scripts/tools/nbs_update.py', 'scripts/tools/nbs_tool.py',
    'data/registry.yaml', 'data/nbs_m/panel.yaml', 'data/nbs_q/panel.yaml', 'data/nbs_a/panel.yaml',
    'data/nbs_m/UPDATE.md', 'data/nbs_q/UPDATE.md', 'data/nbs_a/UPDATE.md',
  ]) {
    assert.ok(existsSync(join(framework, file)), `framework/${file} should ship`)
  }
  // 框架里的子 skill 不能被 DSH 的 skill 目录扫描到（只挂载 skills/）
  assert.equal(plugin.skillsDir(), join(root, 'skills'))
  for (const file of ['dataset.csv', 'raw.csv', 'metadata.yaml']) {
    for (const panel of ['nbs_m', 'nbs_q', 'nbs_a']) {
      assert.ok(!existsSync(join(framework, 'data', panel, file)), `generated ${panel}/${file} must not ship`)
    }
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

// --- Python：工作区管理与清洗函数（不联网） ---------------------------------

const python = ['python3', 'python'].find((bin) => {
  const r = spawnSync(bin, ['-c', 'import sys, numpy, pandas, yaml; sys.exit(0 if sys.version_info >= (3, 10) else 1)'])
  return r.status === 0
})
const skipPy = !python && 'python 3.10+ with numpy/pandas/PyYAML not found'
const workspaceScript = join(root, 'skills', 'marco-bis', 'scripts', 'marco_workspace.py')

function runPy(args, opts = {}) {
  const r = spawnSync(python, args, { encoding: 'utf8', maxBuffer: 64 << 20, ...opts })
  return r
}

test('Python: workspace init copies the framework and upgrade keeps user edits', { skip: skipPy }, () => {
  const dir = mkdtempSync(join(tmpdir(), 'marco-'))
  const ws = join(dir, 'ws')
  try {
    let r = runPy([workspaceScript, 'status', '--workspace', ws])
    assert.equal(r.status, 0, r.stderr)
    assert.equal(JSON.parse(r.stdout).initialized, false)

    r = runPy([workspaceScript, 'init', '--workspace', ws])
    assert.equal(r.status, 0, r.stderr || r.stdout)
    const created = JSON.parse(r.stdout)
    assert.equal(created.action, 'created')
    for (const file of ['CLAUDE.md', 'scripts/lib/data/nbs_client.py', 'data/nbs_m/panel.yaml', '.marco-workspace.json']) {
      assert.ok(existsSync(join(ws, file)), `${file} should be in the workspace`)
    }
    assert.ok(existsSync(join(ws, 'scripts', 'applications')))

    // 再次 init 不改动
    r = runPy([workspaceScript, 'init', '--workspace', ws])
    assert.equal(JSON.parse(r.stdout).action, 'exists')

    // 用户改过的框架文件在升级时保留，新版本另存为 .new
    const edited = join(ws, 'config.yaml')
    writeFileSync(edited, readFileSync(edited, 'utf8') + '\n# user edit\n')
    const manifest = JSON.parse(readFileSync(join(ws, '.marco-workspace.json'), 'utf8'))
    manifest.files['config.yaml'] = 'stale-hash-from-older-version'
    writeFileSync(join(ws, '.marco-workspace.json'), JSON.stringify(manifest))
    r = runPy([workspaceScript, 'upgrade', '--workspace', ws])
    assert.equal(r.status, 0, r.stderr || r.stdout)
    const up = JSON.parse(r.stdout)
    assert.deepEqual(up.conflicts, ['config.yaml'])
    assert.match(readFileSync(edited, 'utf8'), /# user edit/)
    assert.ok(existsSync(edited + '.new'))
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('Python: init refuses a non-empty directory that is not a workspace', { skip: skipPy }, () => {
  const dir = mkdtempSync(join(tmpdir(), 'marco-'))
  try {
    writeFileSync(join(dir, 'something.txt'), 'x')
    const r = runPy([workspaceScript, 'init', '--workspace', dir])
    assert.notEqual(r.status, 0)
    assert.equal(JSON.parse(r.stdout).ok, false)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('Python: panel definitions parse and nbs_update --list works offline', { skip: skipPy }, () => {
  const r = runPy([join(framework, 'scripts', 'tools', 'nbs_update.py'), '--panel', 'all', '--list'])
  assert.equal(r.status, 0, r.stderr || r.stdout)
  for (const id of ['cpi_index', 'ip_yoy', 'm2', 'gdp', 'gdp_real']) {
    assert.match(r.stdout, new RegExp(`\\b${id}\\b`))
  }
})

test('Python: China cleaning helpers behave as documented', { skip: skipPy }, () => {
  const code = `
import importlib.util, json, sys
import numpy as np, pandas as pd
spec = importlib.util.spec_from_file_location("china", sys.argv[1])
china = importlib.util.module_from_spec(spec); spec.loader.exec_module(china)
idx = pd.date_range("2020-01-01", "2021-12-01", freq="MS")
flow = pd.Series(10.0, index=idx)
cum = flow.groupby(idx.year).cumsum()
cum[cum.index.month == 1] = np.nan          # 1 月不公布，2 月是 1–2 月合计
per = china.cumulative_to_period(cum, "M")
assert np.allclose(per.values, 10.0), per
comb = china.cumulative_to_period(cum, "M", jan_feb="combined")
assert np.isnan(comb.iloc[0]) and comb.iloc[1] == 20.0
rate = pd.Series(np.where(idx.month == 1, np.nan, 5.0), index=idx)
assert china.fill_january(rate).notna().all()
true = pd.Series(100 * 1.002 ** np.arange(36), index=pd.date_range("2018-01-01", periods=36, freq="MS"))
mom = true / true.shift(1) * 100
yoy = true / true.shift(12) * 100
level = china.chain_index(mom=mom.iloc[20:], yoy=yoy, base=2019)
assert level.attrs["chain_check"]["max_abs_diff_pp"] < 1e-8, level.attrs
ref = true / true[true.index.year == 2019].mean() * 100
assert np.allclose(level.dropna().values, ref.loc[level.dropna().index].values), (level, ref)
print("ok")
`
  const r = runPy(['-c', code, join(framework, 'scripts', 'lib', 'preprocess', 'china.py')])
  assert.equal(r.status, 0, r.stderr || r.stdout)
  assert.match(r.stdout, /ok/)
})
