/**
 * journalfinder -> DSH: put this package's `skills/` in every session's catalog.
 *
 * The directory is computed from this module's own URL, so the bundle works from a
 * linked checkout, a git install, or a packed tarball without a path to edit.
 *
 * It mounts DSH's shipped `@deepseek-ai/dsh-skill-filesystem` provider through
 * `ctx.loader.import()` instead of a bare import: a bundle's own `node_modules` is
 * empty, so `import '@deepseek-ai/...'` would fail to link, while the loader resolves
 * the provider exactly as a patch row's `name` is resolved.
 *
 * After mounting, it starts a background check for a newer release of this plugin
 * (see update-check.js); the check never delays loading and never throws.
 */

import { existsSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

import { checkForUpdate } from './update-check.js'

/** Cordis plugin name, shown in diagnostics. */
export const name = 'journalfinder-skill'

/** `loader` imports the shipped provider; `skills` is the registry it registers on. */
export const inject = ['loader', 'skills']

/** Folder of this plugin in the repository, also the prefix of its release tags. */
export const FOLDER = 'journalfinder'

/** DSH's local filesystem skill provider, shipped with the harness. */
export const PROVIDER = '@deepseek-ai/dsh-skill-filesystem'

/** Provider name in the `ctx.skills` registry; unique so it cannot collide with the preset's. */
export const PROVIDER_NAME = 'journalfinder'

/**
 * The `skills/` directory beside the module at `from`.
 * @param {string} [from] - a `file:` module URL; defaults to this module.
 * @returns {string} the absolute path to `skills/`.
 * @throws {Error} when it is missing, so a broken install fails loudly instead of listing nothing.
 */
export function skillsDir(from = import.meta.url) {
  const dir = join(dirname(fileURLToPath(from)), 'skills')
  if (!existsSync(dir)) {
    throw new Error(`journalfinder: expected a skills/ directory at ${dir}; the package was installed without it.`)
  }
  return dir
}

/**
 * Mount the shipped local skill provider on this package's `skills/` only.
 * @param {import('@deepseek-ai/cordis').Context} ctx - plugin context with `loader` and `skills` injected.
 */
export async function apply(ctx) {
  const dir = skillsDir()

  let module
  try {
    module = await ctx.loader.import(PROVIDER)
  } catch (error) {
    throw new Error(`journalfinder: could not load ${PROVIDER} from the DSH loader: ${error}`)
  }
  const plugin = typeof module?.apply === 'function' ? module : module?.default
  if (typeof plugin?.apply !== 'function') {
    throw new Error(`journalfinder: ${PROVIDER} did not resolve to a plugin (got ${typeof module}).`)
  }

  // includeDefaultRoots: false scans only this directory, so the preset's own provider
  // keeps the project/user/bundled roots. The child fiber is owned by this plugin's
  // scope and disposed with it; returning it would be read as an (invalid) effect.
  ctx.plugin(plugin, {
    providerName: PROVIDER_NAME,
    includeDefaultRoots: false,
    customSkillDirs: [dir],
  })

  // Not awaited: loading must not wait for GitHub.
  void startUpdateCheck()
}

/**
 * Refresh this plugin's update status file from its own package.json.
 * @param {object} [options] - passed through to checkForUpdate (tests inject fetch, env, now).
 * @returns {Promise<object | undefined>} the status written, if any.
 */
export function startUpdateCheck(options = {}) {
  const packageDir = dirname(fileURLToPath(import.meta.url))
  let manifest
  try {
    manifest = JSON.parse(readFileSync(join(packageDir, 'package.json'), 'utf8'))
  } catch {
    return Promise.resolve(undefined)
  }
  return checkForUpdate({ folder: FOLDER, packageName: manifest.name, installed: manifest.version, packageDir, ...options })
}
