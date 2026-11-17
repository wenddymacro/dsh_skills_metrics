// Tests of update-check.js, identical in every plugin folder; imported by test.mjs.
// No network: GitHub is replaced by a fake fetch, and DSH_HOME by a temporary directory.

import assert from 'node:assert/strict'
import { existsSync, mkdtempSync, readdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { basename, dirname, join } from 'node:path'
import { test } from 'node:test'
import { fileURLToPath } from 'node:url'

import * as plugin from './index.js'
import * as update from './update-check.js'

const root = dirname(fileURLToPath(import.meta.url))
const pkg = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'))
const FOLDER = basename(root)
const HOUR = 60 * 60 * 1000

/** A fake GitHub: answers `refs` (or throws `error`) and counts calls. */
function fakeFetch({ refs = [], error, status = 200 } = {}) {
  const calls = []
  const fetch = async (url, init) => {
    calls.push({ url, init })
    if (error) throw new Error(error)
    return { ok: status >= 200 && status < 300, status, json: async () => refs }
  }
  return { fetch, calls }
}

const tag = (folder, version) => ({ ref: `refs/tags/${folder}-v${version}` })

function withHome(run) {
  const home = mkdtempSync(join(tmpdir(), 'dsh-update-'))
  return Promise.resolve(run({ DSH_HOME: home }, home)).finally(() => rmSync(home, { recursive: true, force: true }))
}

test('update: package declares a release version, ships the checker, and FOLDER is its folder', () => {
  assert.ok(update.parseVersion(pkg.version), `version ${pkg.version} must be MAJOR.MINOR.PATCH`)
  assert.ok(pkg.files.includes('update-check.js'), 'files must ship update-check.js')
  assert.equal(plugin.FOLDER, FOLDER)
})

test('update: every plugin folder carries the same update-check.js and its tests', () => {
  for (const file of ['update-check.js', 'update-check.test.mjs']) {
    const mine = readFileSync(join(root, file), 'utf8')
    for (const sibling of ['journalfinder', 'marcobis', 'whichdidshouldiuse']) {
      const other = join(root, '..', sibling, file)
      if (sibling !== FOLDER && existsSync(other)) {
        assert.equal(readFileSync(other, 'utf8'), mine, `${sibling}/${file} differs from ${FOLDER}/${file}`)
      }
    }
  }
})

test('update: README and GUIDE install addresses name this version', () => {
  const spec = `github:${update.REPO}#${FOLDER}-v${pkg.version}&path:/${FOLDER}`
  for (const doc of ['README.md', join('docs', 'GUIDE.md')]) {
    const path = join(root, doc)
    if (!existsSync(path)) continue
    assert.ok(readFileSync(path, 'utf8').includes(spec), `${doc} should install ${spec}`)
  }
})

test('update: versions compare numerically and prereleases are not releases', () => {
  assert.ok(update.compareVersions('0.10.0', '0.9.9') > 0)
  assert.ok(update.compareVersions('v1.0.0', '1.0.0') === 0)
  assert.ok(update.compareVersions('0.1.0', '0.2.0') < 0)
  assert.ok(Number.isNaN(update.compareVersions('1.0.0-rc.1', '0.9.0')))
})

test('update: latestRelease picks the newest tag of this folder only', () => {
  const refs = [
    tag(FOLDER, '0.2.0'), tag(FOLDER, '0.10.0'), tag(FOLDER, '0.9.1'),
    tag(FOLDER, '1.0.0-rc.1'), tag(`${FOLDER}x`, '9.0.0'), { ref: 'refs/tags/v5.0.0' }, {},
  ]
  assert.deepEqual(update.latestRelease(refs, FOLDER), { tag: `${FOLDER}-v0.10.0`, version: '0.10.0' })
  assert.equal(update.latestRelease([], FOLDER), undefined)
  assert.equal(update.latestRelease({ message: 'Not Found' }, FOLDER), undefined)
})

test('update: a newer tag writes an offer the agent can act on', () => withHome(async (env, home) => {
  const gh = fakeFetch({ refs: [tag(FOLDER, '0.1.0'), tag(FOLDER, '9.9.9')] })
  const status = await update.checkForUpdate({ folder: FOLDER, packageName: pkg.name, installed: '0.2.0', fetch: gh.fetch, env, now: () => 0 })
  assert.equal(gh.calls.length, 1)
  assert.equal(gh.calls[0].url, `https://api.github.com/repos/${update.REPO}/git/matching-refs/tags/${FOLDER}-v`)
  assert.equal(status.updateAvailable, true)
  assert.equal(status.installed, '0.2.0')
  assert.equal(status.latest, '9.9.9')
  assert.equal(status.installSpec, `github:${update.REPO}#${FOLDER}-v9.9.9&path:/${FOLDER}`)
  assert.equal(status.package, pkg.name)
  const path = join(home, 'cache', 'dsh-skills-metrics', `${FOLDER}.json`)
  assert.equal(update.statusPath(FOLDER, env), path)
  assert.deepEqual(JSON.parse(readFileSync(path, 'utf8')), status)
}))

test('update: no newer tag means no offer', () => withHome(async (env) => {
  const gh = fakeFetch({ refs: [tag(FOLDER, '0.2.0')] })
  const status = await update.checkForUpdate({ folder: FOLDER, packageName: pkg.name, installed: '0.2.0', fetch: gh.fetch, env, now: () => 0 })
  assert.equal(status.updateAvailable, false)
  assert.equal(status.latest, '0.2.0')
}))

test('update: GitHub is asked at most once per TTL, and the offer follows the installed version', () => withHome(async (env) => {
  const gh = fakeFetch({ refs: [tag(FOLDER, '0.3.0')] })
  const base = { folder: FOLDER, packageName: pkg.name, fetch: gh.fetch, env }
  assert.equal((await update.checkForUpdate({ ...base, installed: '0.2.0', now: () => 0 })).updateAvailable, true)
  // The user updated: same cached answer, no network, no offer.
  assert.equal((await update.checkForUpdate({ ...base, installed: '0.3.0', now: () => HOUR })).updateAvailable, false)
  assert.equal(gh.calls.length, 1)
  await update.checkForUpdate({ ...base, installed: '0.3.0', now: () => update.TTL_MS + 1 })
  assert.equal(gh.calls.length, 2)
}))

test('update: a network failure keeps the last known release and retries sooner', () => withHome(async (env) => {
  const base = { folder: FOLDER, packageName: pkg.name, installed: '0.2.0', env }
  await update.checkForUpdate({ ...base, fetch: fakeFetch({ refs: [tag(FOLDER, '0.3.0')] }).fetch, now: () => 0 })
  const down = fakeFetch({ error: 'getaddrinfo ENOTFOUND api.github.com' })
  const failed = await update.checkForUpdate({ ...base, fetch: down.fetch, now: () => update.TTL_MS + 1 })
  assert.equal(failed.updateAvailable, true, 'a pending update stays visible')
  assert.match(failed.error, /ENOTFOUND/)
  await update.checkForUpdate({ ...base, fetch: down.fetch, now: () => update.TTL_MS + 1 + update.RETRY_MS / 2 })
  assert.equal(down.calls.length, 1, 'no retry before RETRY_MS')
  await update.checkForUpdate({ ...base, fetch: down.fetch, now: () => update.TTL_MS + 2 + update.RETRY_MS })
  assert.equal(down.calls.length, 2)
  const http = await update.checkForUpdate({ ...base, fetch: fakeFetch({ status: 403 }).fetch, now: () => 10 * update.TTL_MS })
  assert.match(http.error, /HTTP 403/)
}))

test('update: a corrupt status file is replaced, never thrown', () => withHome(async (env) => {
  const path = update.statusPath(FOLDER, env)
  await update.checkForUpdate({ folder: FOLDER, packageName: pkg.name, installed: '0.2.0', fetch: fakeFetch().fetch, env, now: () => 0 })
  writeFileSync(path, '{not json')
  const status = await update.checkForUpdate({ folder: FOLDER, packageName: pkg.name, installed: '0.2.0', fetch: fakeFetch().fetch, env, now: () => 1 })
  assert.equal(status.updateAvailable, false)
}))

test('update: the opt-out switch skips the network and the file', () => withHome(async (env) => {
  for (const value of ['0', 'false', 'OFF', 'no']) {
    const gh = fakeFetch({ refs: [tag(FOLDER, '9.0.0')] })
    const status = await update.checkForUpdate({
      folder: FOLDER, packageName: pkg.name, installed: '0.2.0', fetch: gh.fetch, env: { ...env, [update.OPT_OUT_ENV]: value },
    })
    assert.equal(status, undefined)
    assert.equal(gh.calls.length, 0)
  }
  assert.equal(existsSync(update.statusPath(FOLDER, env)), false)
}))

test('update: startUpdateCheck reports the installed package version', () => withHome(async (env) => {
  const gh = fakeFetch({ refs: [tag(FOLDER, '99.0.0')] })
  const status = await plugin.startUpdateCheck({ fetch: gh.fetch, env, now: () => 0 })
  assert.equal(status.installed, pkg.version)
  assert.equal(status.package, pkg.name)
  assert.equal(status.updateAvailable, true)
}))

test('update: each SKILL.md tells the agent where the status file is and how to update', () => {
  const skills = join(root, 'skills')
  const names = readdirNames(skills)
  assert.ok(names.length > 0)
  for (const name of names) {
    const text = readFileSync(join(skills, name, 'SKILL.md'), 'utf8')
    assert.ok(text.includes(`cache/dsh-skills-metrics/${FOLDER}.json`), `${name}/SKILL.md must name the status file`)
    assert.match(text, /plugin_manager/, `${name}/SKILL.md must name the plugin_manager tool`)
    assert.match(text, /install_bundle/)
    assert.match(text, /installSpec/)
  }
})

function readdirNames(dir) {
  return readdirSync(dir).filter((name) => existsSync(join(dir, name, 'SKILL.md')))
}
