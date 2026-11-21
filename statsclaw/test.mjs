// Tests for the statsclaw bundle: `node --test test.mjs`.

import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { existsSync, mkdirSync, mkdtempSync, readdirSync, readFileSync, rmSync, statSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
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

test('language packs: Stata and Python directories plus single-file profiles', () => {
  const profiles = join(skillDir, 'references', 'profiles')
  assert.deepEqual(readdirSync(profiles).sort(), ['c-library.md', 'cpp-library.md', 'go-module.md', 'julia-package.md',
    'maintainer.md', 'python', 'r-package.md', 'rust-crate.md', 'stata', 'typescript-package.md'])
  assert.deepEqual(readdirSync(join(profiles, 'stata')).sort(), ['conventions.md', 'helpfile-and-packaging.md', 'maintainer.md',
    'pitfalls.md', 'profile.md', 'run_stata.sh', 'simulation.md', 'stata_pkg_check.py', 'templates', 'testing.md'])
  assert.deepEqual(readdirSync(join(profiles, 'stata', 'templates')).sort(), ['cert_template.do', 'helpfile.sthlp', 'package.pkg'])
  assert.deepEqual(readdirSync(join(profiles, 'python')).sort(), ['maintainer.md', 'profile.md'])
  assert.ok(statSync(join(profiles, 'stata', 'run_stata.sh')).mode & 0o100, 'run_stata.sh stays executable')
})

test('the Stata pack gives every role a section and its file table matches what it ships', () => {
  const dir = join(skillDir, 'references', 'profiles', 'stata')
  const profile = readFileSync(join(dir, 'profile.md'), 'utf8')
  for (const spec of ROLES) assert.match(profile, new RegExp(`^### ${spec.role}$`, 'm'), spec.role)
  const table = profile.slice(profile.indexOf('## 文件'), profile.indexOf('## 识别'))
  assert.ok(table.length > 100, 'profile.md has a file table')
  for (const m of table.matchAll(/`((?:templates\/)?[\w-]+\.(?:md|sh|py|do|sthlp|pkg))`/g)) {
    if (existsSync(join(dir, m[1])) || existsSync(join(dir, 'templates', m[1]))) continue
    assert.fail(`profile.md mentions ${m[1]}, which the pack does not ship`)
  }
  const pitfalls = readFileSync(join(dir, 'pitfalls.md'), 'utf8')
  assert.equal([...pitfalls.matchAll(/^\| \d+ \|/gm)].length, 27, 'profile.md promises 27 pitfalls')
  for (const f of ['testing.md', 'helpfile-and-packaging.md']) {
    assert.doesNotMatch(readFileSync(join(dir, f), 'utf8'), /<SCRIPTS>|skill 自带/, `${f} still uses an old path`)
  }
})

test('maintainer templates are marked unfilled and state the precedence', () => {
  const profiles = join(skillDir, 'references', 'profiles')
  for (const rel of ['maintainer.md', 'stata/maintainer.md', 'python/maintainer.md']) {
    const text = readFileSync(join(profiles, rel), 'utf8')
    assert.match(text.split('\n')[0], /^<!-- statsclaw:maintainer-template 未填写/, rel)
    assert.match(text, /隔离|容差/, `${rel} must say it cannot override isolation or tolerance rules`)
  }
  assert.match(skill, /statsclaw:maintainer-template 未填写/)
  for (const spec of ROLES) {
    const text = readFileSync(join(skillDir, 'references', 'roles', `${spec.role}.md`), 'utf8')
    assert.match(text, /## 语言包与维护者规范/, spec.role)
    assert.match(text, /\.statsclaw\/context\.md` > 该语言的 `maintainer\.md` > 跨语言的 `maintainer\.md`/, spec.role)
    assert.match(text, new RegExp(`"各角色须知"里 \\*\\*${spec.role}\\*\\* 一节`), spec.role)
    assert.match(text, /任何规范都不能覆盖/, spec.role)
    assert.doesNotMatch(text, /语言 profile/, `${spec.role} still says 语言 profile`)
  }
  assert.match(skill, /\| 8 \| 发布检查 \|/)
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

// --- scripts --------------------------------------------------------------------

const stataPack = join(skillDir, 'references', 'profiles', 'stata')
const runner = join(stataPack, 'run_stata.sh')
const checker = join(stataPack, 'stata_pkg_check.py')
const hasPython = spawnSync('python3', ['--version']).status === 0
const PY = { skip: !hasPython && 'python3 not found' }

function fixture(t, files) {
  const dir = mkdtempSync(join(tmpdir(), 'stpkg-'))
  t.after(() => rmSync(dir, { recursive: true, force: true }))
  for (const [rel, body] of Object.entries(files)) {
    mkdirSync(dirname(join(dir, rel)), { recursive: true })
    writeFileSync(join(dir, rel), body)
  }
  return dir
}

function lint(dir) {
  const res = spawnSync('python3', ['-I', checker, '--json', dir], { encoding: 'utf8' })
  return { status: res.status, report: res.stdout ? JSON.parse(res.stdout) : null, stderr: res.stderr }
}

const GOOD_ADO = `*! version 1.0.0  21nov2026
program define mycmd, eclass sortpreserve
    version 16
    syntax varlist(min=2 numeric) [if] [in]
    marksample touse
    // comments with */ are fine
    ereturn local cmd "mycmd"
end
program _mycmd_helper
    display "private"
end
mata:
real scalar twice(real scalar x) {
    /* a Mata block comment */
    return(2 * x)
}
end
`

test('pkg check: a clean package passes with no findings', PY, (t) => {
  const dir = fixture(t, {
    'mycmd.ado': GOOD_ADO,
    'mycmd.sthlp': '{smcl}\n{* *! version 1.0.0  21nov2026}{...}\n{title:Title}\n',
    'mycmd.pkg': 'v 3\nd mycmd: test\nf mycmd.ado\nf mycmd.sthlp\n',
    'stata.toc': 'v 3\np mycmd test\n',
    'cert/cert_mycmd.do': 'program define notmatching\nend\n',
  })
  const { status, report } = lint(dir)
  assert.equal(status, 0)
  assert.deepEqual(report.issues, [])
})

test('pkg check: silent-error hazards and packaging gaps are reported', PY, (t) => {
  const dir = fixture(t, {
    'other.ado': 'program define wrongname, eclass\n    syntax varlist\n    * save to out/*.dta\n    set seed 123\n    merge m:m id using x\nend\n',
    'mycmd.ado': GOOD_ADO.replace('1.0.0', '1.1.0'),
    'mycmd.sthlp': '{smcl}\n{* *! version 1.0.0  21nov2026}{...}\n',
    'bad.pkg': 'v 2\nf missing.ado\nf mycmd.ado\n',
    'stata.toc': 'v 3\np ghost x\n',
  })
  const { status, report } = lint(dir)
  assert.equal(status, 1)
  const has = (level, file, re) => report.issues.some(i => i.level === level && i.file === file && re.test(i.message))
  assert.ok(has('ERROR', 'other.ado', /no program named other/))
  assert.ok(has('ERROR', 'other.ado', /silently skipped/))
  assert.ok(has('ERROR', 'other.ado', /no help file/))
  assert.ok(has('WARN', 'other.ado', /set seed/))
  assert.ok(has('WARN', 'other.ado', /merge m:m/))
  assert.ok(has('WARN', 'other.ado', /\*! version/))
  assert.ok(has('ERROR', 'bad.pkg', /"v 3"/))
  assert.ok(has('ERROR', 'bad.pkg', /missing\.ado/))
  assert.ok(has('ERROR', 'stata.toc', /ghost/))
  assert.ok(has('WARN', 'mycmd.sthlp', /differs/))
  assert.ok(has('WARN', 'mycmd.sthlp', /not listed/))
  assert.ok(!report.issues.some(i => i.file === 'mycmd.ado' && i.level === 'ERROR'), 'the clean ado stays clean')
})

test('pkg check: eclass without e(cmd) and a missing version statement warn', PY, (t) => {
  const dir = fixture(t, {
    'est.ado': '*! version 0.1.0  1jan2026\nprogram est, eclass\n    syntax varlist\n    ereturn post\nend\n',
    'est.sthlp': '{smcl}\n',
  })
  const { status, report } = lint(dir)
  assert.equal(status, 0)
  assert.ok(report.issues.some(i => /never sets e\(cmd\)/.test(i.message)))
  assert.ok(report.issues.some(i => /no "version" statement/.test(i.message)))
})

test('pkg check: bad arguments exit 2', PY, () => {
  assert.equal(spawnSync('python3', ['-I', checker, '/nonexistent/dir']).status, 2)
  assert.equal(spawnSync('python3', ['-I', checker, '--bogus']).status, 2)
})

test('the templates pass the package check together', PY, (t) => {
  const tpl = (f) => readFileSync(join(stataPack, 'templates', f), 'utf8')
  const dir = fixture(t, {
    'mycmd.ado': GOOD_ADO,
    'mycmd.sthlp': tpl('helpfile.sthlp'),
    'mycmd.pkg': tpl('package.pkg'),
  })
  const { status, report } = lint(dir)
  assert.equal(status, 0, JSON.stringify(report.issues))
  assert.deepEqual(report.issues, [])
})

test('runner rejects bad arguments before starting Stata', () => {
  const none = spawnSync('bash', [runner], { encoding: 'utf8' })
  assert.equal(none.status, 2)
  const missing = spawnSync('bash', [runner, '/nonexistent.do'], { encoding: 'utf8' })
  assert.equal(missing.status, 2)
  assert.match(missing.stderr, /do-file not found/)
})

const hasStata = spawnSync('bash', [runner, '--which-stata']).status === 0
const STATA = { skip: !hasStata && 'Stata not found', timeout: 300_000 }

test('Stata: the cert template machinery runs against regress', STATA, (t) => {
  const dir = fixture(t, {
    'mycmd.ado': '*! version 1.0.0  21nov2026\nprogram define mycmd, eclass\n    version 16\n    syntax varlist(min=2 numeric)\n    regress `varlist\'\n    ereturn local cmd "mycmd"\nend\n',
    'cert_mycmd.do': readFileSync(join(stataPack, 'templates', 'cert_template.do'), 'utf8')
      .replaceAll('<cmd>', 'mycmd').replace('<what this script certifies>', 'template smoke test'),
  })
  const res = spawnSync('bash', [runner, '--tail', '5', 'cert_mycmd.do'], { cwd: dir, encoding: 'utf8', timeout: 300_000 })
  assert.equal(res.status, 0, res.stdout + res.stderr)
  assert.match(readFileSync(join(dir, 'cert_mycmd.log'), 'utf8'), /CERT PASSED/)
})
