/**
 * Update check shared by every plugin in wenddymacro/dsh_skills_metrics.
 *
 * Each plugin folder carries an identical copy of this file (a bundle installed with
 * `&path:/<folder>` cannot import from a sibling folder); the plugins' tests fail when
 * the copies drift apart.
 *
 * A release of plugin `<folder>` is the git tag `<folder>-v<version>`, where `<version>` is
 * the `version` in `<folder>/package.json` at that tag. On load, the plugin asks GitHub for
 * its tags at most once per {@link TTL_MS}, then writes what it learnt to
 * `<DSH_HOME or ~/.dsh>/cache/dsh-skills-metrics/<folder>.json`. The plugin's SKILL.md tells
 * the agent to read that file once per session and, when `updateAvailable` is true, offer
 * the user the update through dsh's `plugin_manager` tool. Nothing is installed here.
 *
 * Set DSH_SKILLS_METRICS_UPDATE_CHECK=0 to turn the network check off.
 */

import { mkdir, readFile, rename, writeFile } from 'node:fs/promises'
import { homedir } from 'node:os'
import { join } from 'node:path'

/** GitHub repository that publishes the release tags. */
export const REPO = 'wenddymacro/dsh_skills_metrics'

/** How long one answer from GitHub is trusted before asking again. */
export const TTL_MS = 12 * 60 * 60 * 1000

/** After a failed check, ask again sooner than {@link TTL_MS}. */
export const RETRY_MS = 60 * 60 * 1000

/** Longest wait for GitHub; a slow or blocked network must not hold anything up. */
export const TIMEOUT_MS = 8000

/** Environment switch: `0`, `false`, `off` or `no` disables the network check. */
export const OPT_OUT_ENV = 'DSH_SKILLS_METRICS_UPDATE_CHECK'

/**
 * Parse `MAJOR.MINOR.PATCH`, ignoring a leading `v`; prerelease and build tags are not releases.
 * @param {string} text
 * @returns {[number, number, number] | undefined}
 */
export function parseVersion(text) {
  const match = /^v?(\d+)\.(\d+)\.(\d+)$/.exec(String(text).trim())
  return match ? [Number(match[1]), Number(match[2]), Number(match[3])] : undefined
}

/**
 * Compare two release versions.
 * @returns {number} negative when a < b, 0 when equal, positive when a > b; NaN when either is not a release.
 */
export function compareVersions(a, b) {
  const x = parseVersion(a)
  const y = parseVersion(b)
  if (!x || !y) return Number.NaN
  for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] - y[i]
  return 0
}

/**
 * The newest release among tag refs of the form `refs/tags/<folder>-v<version>`.
 * @param {Array<{ref?: string}>} refs - GitHub's `git/matching-refs` answer.
 * @param {string} folder - the plugin folder name.
 * @returns {{ tag: string, version: string } | undefined}
 */
export function latestRelease(refs, folder) {
  const prefix = `refs/tags/${folder}-v`
  let best
  for (const { ref } of Array.isArray(refs) ? refs : []) {
    if (typeof ref !== 'string' || !ref.startsWith(prefix)) continue
    const version = ref.slice(prefix.length)
    if (!parseVersion(version)) continue
    if (!best || compareVersions(version, best.version) > 0) best = { tag: ref.slice('refs/tags/'.length), version }
  }
  return best
}

/**
 * Where the status of plugin `folder` is written.
 * @param {string} folder
 * @param {NodeJS.ProcessEnv} [env]
 */
export function statusPath(folder, env = process.env) {
  const home = env.DSH_HOME?.trim() || join(homedir(), '.dsh')
  return join(home, 'cache', 'dsh-skills-metrics', `${folder}.json`)
}

/**
 * The status record the agent reads, derived from the installed version and the latest release.
 * @param {object} fields
 * @param {string} fields.folder
 * @param {string} fields.packageName
 * @param {string} fields.installed
 * @param {{ tag: string, version: string } | undefined} fields.latest
 * @param {number} fields.checkedAt - epoch milliseconds of the GitHub answer.
 * @param {string} [fields.error]
 */
export function buildStatus({ folder, packageName, installed, latest, checkedAt, error }) {
  const updateAvailable = latest !== undefined && compareVersions(latest.version, installed) > 0
  return {
    plugin: folder,
    package: packageName,
    installed,
    latest: latest?.version ?? null,
    tag: latest?.tag ?? null,
    updateAvailable,
    installSpec: latest ? `github:${REPO}#${latest.tag}&path:/${folder}` : null,
    changesUrl: latest ? `https://github.com/${REPO}/commits/${latest.tag}/${folder}` : null,
    checkedAt: new Date(checkedAt).toISOString(),
    ...(error === undefined ? {} : { error }),
  }
}

async function readStatus(path) {
  try {
    return JSON.parse(await readFile(path, 'utf8'))
  } catch {
    return undefined
  }
}

async function writeStatus(path, status) {
  await mkdir(join(path, '..'), { recursive: true })
  const temp = `${path}.${process.pid}.tmp`
  await writeFile(temp, `${JSON.stringify(status, null, 2)}\n`)
  await rename(temp, path)
}

/**
 * Ask GitHub for this plugin's release tags.
 * @returns {Promise<Array<{ref: string}>>}
 */
async function fetchRefs(folder, fetchImpl) {
  const url = `https://api.github.com/repos/${REPO}/git/matching-refs/tags/${encodeURIComponent(folder)}-v`
  const response = await fetchImpl(url, {
    headers: { accept: 'application/vnd.github+json', 'user-agent': 'dsh-skills-metrics-update-check' },
    signal: AbortSignal.timeout(TIMEOUT_MS),
  })
  if (!response.ok) throw new Error(`GitHub answered HTTP ${response.status}`)
  return response.json()
}

/**
 * Refresh the status file of one plugin. Never throws.
 * @param {object} options
 * @param {string} options.folder - plugin folder name, also the tag prefix.
 * @param {string} options.packageName - npm package name of the bundle.
 * @param {string} options.installed - `version` of the installed package.json.
 * @param {typeof fetch} [options.fetch]
 * @param {NodeJS.ProcessEnv} [options.env]
 * @param {() => number} [options.now]
 * @returns {Promise<object | undefined>} the status written, or undefined when the check is off or failed to write.
 */
export async function checkForUpdate({ folder, packageName, installed, fetch: fetchImpl = globalThis.fetch, env = process.env, now = Date.now }) {
  try {
    if (/^(0|false|off|no)$/i.test(env[OPT_OUT_ENV]?.trim() ?? '')) return undefined
    const path = statusPath(folder, env)
    const previous = await readStatus(path)
    const previousAt = Date.parse(previous?.checkedAt ?? '')
    const ttl = previous?.error === undefined ? TTL_MS : RETRY_MS
    const fresh = Number.isFinite(previousAt) && now() >= previousAt && now() - previousAt < ttl

    let latest
    let checkedAt
    let error
    if (fresh) {
      // Reuse GitHub's last answer; recompute because the installed version may have changed since.
      latest = previous.tag && previous.latest ? { tag: previous.tag, version: previous.latest } : undefined
      checkedAt = previousAt
      error = previous.error
    } else {
      checkedAt = now()
      try {
        latest = latestRelease(await fetchRefs(folder, fetchImpl), folder)
      } catch (cause) {
        error = String(cause?.message ?? cause)
        // Keep the last release we knew of, so a flaky network does not hide a pending update.
        latest = previous?.tag && previous?.latest ? { tag: previous.tag, version: previous.latest } : undefined
      }
    }
    const status = buildStatus({ folder, packageName, installed, latest, checkedAt, error })
    await writeStatus(path, status)
    return status
  } catch {
    return undefined
  }
}
