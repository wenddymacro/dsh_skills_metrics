#!/usr/bin/env node
/**
 * Generate `cordis.patch.yml` from the role manuals in
 * `skills/statsclaw-stata/references/roles/*.md`.
 *
 * The role manuals are the single source of truth: the same file is the persona of
 * a role preset (team mode) and the manual a fresh subagent or the serial fallback
 * reads (other modes). Run `node scripts/build-patch.mjs` after editing a manual;
 * `node scripts/build-patch.mjs --check` exits 1 when the committed patch is stale.
 *
 * No dependencies: the YAML is emitted by hand from a small, fixed shape.
 */

import { readFileSync, writeFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(dirname(fileURLToPath(import.meta.url)), '..')
const rolesDir = join(root, 'skills', 'statsclaw-stata', 'references', 'roles')
const patchPath = join(root, 'cordis.patch.yml')
const pkg = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8'))

/** Role presets in pipeline order: preset id suffix, display label, extra tools. */
export const ROLES = [
  { role: 'planner', label: '规划', summary: '读懂论文和需求，写出互相隔离的 spec.md、test-spec.md、sim-spec.md，含 Stata 语法和返回值约定', web: true },
  { role: 'builder', label: '编码', summary: '只依据 spec.md 写 ado / Mata 和自己的认证脚本' },
  { role: 'tester', label: '测试', summary: '只依据 test-spec.md 写认证脚本、对照基准命令独立验证，容差不可放宽' },
  { role: 'simulator', label: '仿真', summary: '只依据 sim-spec.md 用 simulate / postfile 写 DGP 和蒙特卡洛仿真' },
  { role: 'scriber', label: '文档', summary: 'sthlp 帮助文件、README、架构图和过程记录' },
  { role: 'reviewer', label: '审查', summary: '交叉核对各流水线，给出能否交付的结论', readOnly: true },
]

export const LEADER_ID = 'statsclaw-stata-leader'
export const ROLE_IDS = ROLES.map(r => `statsclaw-stata-${r.role}`)
export const DISPATCH_TOOL = 'statsclaw_stata_dispatch'

const LEADER_PERSONA = `你是 StatsClaw Stata 团队的组长（leader），在用户的电脑上协助开发 Stata 命令包（ado / Mata / sthlp）和 Stata 复现项目。

开始任何开发任务之前，先用 skill 工具加载 \`statsclaw-stata\` skill，并严格按其中的组长协议工作；skill 加载结果给出的资源目录就是协议里说的 <SKILL>。如果 skill 列表里没有 statsclaw-stata，告诉用户 StatsClaw Stata 插件可能没有安装或启用完整，然后停止。

你有一个专用派发工具 \`${DISPATCH_TOOL}\`，只能派发这六个角色：${ROLE_IDS.join('、')}。每次派发都要显式设置 agent_preset，并给子级一个 name（如 builder-1）。子级看不到本对话，派发提示必须写全路径和任务。

硬性规则：
- 你只负责规划、派发、核对和汇报，不亲自写 ado、跑认证脚本、推导公式、写帮助文件或下审查结论；这些都派给对应角色。认证脚本失败时哪怕只差一个字符，也重派 builder，不自己改。
- 不自动 ssc install 任何包；缺依赖时告诉用户，经同意再装。
- 规格隔离不可违反：builder 只拿 spec.md，tester 只拿 test-spec.md，simulator 只拿 sim-spec.md；scriber 和 reviewer 拿全部。
- 只有角色发出 HOLD 时才问用户；BLOCK 和 STOP 自动重派处理，同一角色同一信号最多重派 3 次。
- 提交只在用户要求时做；推送和开 PR 只在用户明确要求时做。

用户只是闲聊或问与开发无关的问题时，直接回答即可。`

/**
 * The persona of one role preset: a short header, then the role manual verbatim.
 * @param {{ role: string, label: string }} spec - the role entry.
 * @returns {string} the persona prefix text.
 */
export function rolePersona(spec) {
  const manual = readFileSync(join(rolesDir, `${spec.role}.md`), 'utf8').trim()
  const header = `你是 StatsClaw Stata 团队的${spec.label}角色（${spec.role}），由组长通过派发工具调用。你看不到组长和用户的对话；派发提示会给出目标项目、运行目录、Stata 版本、run_stata.sh 和参考文件的绝对路径，以及本次任务和写入范围。你不能直接问用户：需要用户回答时按手册发出 HOLD，组长会转达。下面是你的完整工作手册，严格遵守。`
  return `${header}\n\n${manual}`
}

// --- YAML emission -------------------------------------------------------

/** Quote a scalar with single quotes (YAML-safe for every value used here). */
const q = (s) => `'${String(s).replaceAll("'", "''")}'`

/** A block literal (`|-`) indented to `indent` spaces. */
function block(text, indent) {
  const pad = ' '.repeat(indent)
  return '|-\n' + text.split('\n').map(line => (line.length > 0 ? pad + line : '')).join('\n')
}

/** Rows shared by every preset; `fs` lets the reviewer drop edit. */
function baseRows(pad, { readOnly = false } = {}) {
  const r = (s) => s.split('\n').map(l => (l.length ? pad + l : '')).join('\n')
  return r(`- id: agent-instructions
  name: '@deepseek-ai/dsh-agent-instructions'
  config:
    maxBytes: 65536
- id: time-context
  name: '@deepseek-ai/dsh-time-context'
- id: tool-bash
  name: '@deepseek-ai/dsh-tool-bash'
  disabled: !!js process.platform === 'win32'
- id: tool-pwsh
  name: '@deepseek-ai/dsh-tool-pwsh'
  disabled: !!js process.platform !== 'win32'
- id: tool-fs
  name: '@deepseek-ai/dsh-tool-fs'
  config:
    applyPatch: false${readOnly ? '\n    edit: false' : ''}
- id: tool-fs-search
  name: '@deepseek-ai/dsh-tool-fs-search'
  config:
    sampleOverCapGlobResults: false
- id: tool-jobs
  name: '@deepseek-ai/dsh-tool-jobs'
- id: tool-todo
  name: '@deepseek-ai/dsh-tool-todo'
  config:
    allowParallelInProgress: true
- id: compaction
  name: cordis:group
  group: true
  isolate:
    compaction: true
    toolResultPruner: true
  config:
    - id: compaction-basic
      name: '@deepseek-ai/dsh-compaction-basic'
    - id: command-compact
      name: '@deepseek-ai/dsh-command-compact'
    - id: tool-result-pruner
      name: '@deepseek-ai/dsh-compaction-tool-result-pruner'
      config:
        thresholdChars: 8192
        headChars: 4096
        tailChars: 1024`)
}

const WEB_ROW = `- id: tool-web
  name: '@deepseek-ai/dsh-tool-web'
  config:
    fetch: true
    searchTimeoutMs: 60000`

function indentRows(text, pad) {
  return text.split('\n').map(l => (l.length ? pad + l : '')).join('\n')
}

function presetRow({ id, name, description, order, persona, extra }) {
  const P = '          ' // 10 spaces: plugin rows inside config.plugins
  return [
    `    - id: preset-${id}`,
    `      name: '@deepseek-ai/dsh-agent-preset'`,
    `      config:`,
    `        id: ${id}`,
    `        name: ${q(name)}`,
    `        description: ${q(description)}`,
    `        order: ${order}`,
    `        plugins:`,
    `${P}- id: persona`,
    `${P}  name: '@deepseek-ai/dsh-persona'`,
    `${P}  config:`,
    `${P}    prefix: ${block(persona, P.length + 6)}`,
    baseRows(P, extra),
    ...(extra.rows ? [indentRows(extra.rows, P)] : []),
  ].join('\n')
}

/** @returns {string} the full generated patch. */
export function buildPatch() {
  const leaderRows = `- id: tool-skill
  name: '@deepseek-ai/dsh-tool-skill'
- id: tool-ask-user
  name: '@deepseek-ai/dsh-tool-ask-user'
${WEB_ROW}
- id: tool-subagent-control
  name: '@deepseek-ai/dsh-tool-subagent-control'
  config:
    interrupt: false
- id: tool-statsclaw-dispatch
  name: '@deepseek-ai/dsh-tool-subagent'
  config:
    provider: spawn
    toolName: ${DISPATCH_TOOL}
    agentPreset: ${ROLE_IDS[0]}
    allowedAgentPresets:
${ROLE_IDS.map(id => `      - ${id}`).join('\n')}`

  const presets = [
    presetRow({
      id: LEADER_ID,
      name: 'StatsClaw Stata · 组长',
      description: 'Stata 命令包开发团队：组长派发规划、编码、测试、仿真、文档、审查六个角色，规格互相隔离，认证脚本对照基准命令验证。开发 Stata 包时选这个。',
      order: 70,
      persona: LEADER_PERSONA,
      extra: { rows: leaderRows },
    }),
    ...ROLES.map((spec, i) => presetRow({
      id: `statsclaw-stata-${spec.role}`,
      name: `StatsClaw Stata · ${spec.label}`,
      description: `StatsClaw Stata ${spec.label}角色：${spec.summary}。由组长派发，一般不要直接选择。`,
      order: 71 + i,
      persona: rolePersona(spec),
      extra: { readOnly: !!spec.readOnly, rows: spec.web ? WEB_ROW : undefined },
    })),
  ]

  return `# GENERATED by scripts/build-patch.mjs from skills/statsclaw-stata/references/roles/*.md.
# Do not edit by hand: edit the role manuals, then run \`node scripts/build-patch.mjs\`.
#
# 1. statsclaw-skill mounts this package's skills/ (the \`statsclaw-stata\` entry skill) for
#    every session; index.js locates skills/ from its own module URL, so no path here.
# 2. preset-statsclaw-stata-leader is the session preset to choose: a leader persona plus a
#    dedicated \`${DISPATCH_TOOL}\` tool that may only spawn the six role presets.
# 3. preset-statsclaw-stata-<role> are the role presets; each persona is the role manual.
- insert:
    - id: statsclaw-stata-skill
      name: ${q(pkg.name)}
${presets.join('\n')}
`
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const next = buildPatch()
  if (process.argv.includes('--check')) {
    const current = readFileSync(patchPath, 'utf8')
    if (current !== next) {
      console.error('cordis.patch.yml is stale: run `node scripts/build-patch.mjs`.')
      process.exit(1)
    }
    console.log('cordis.patch.yml is up to date.')
  } else {
    writeFileSync(patchPath, next)
    console.log(`wrote ${patchPath}`)
  }
}
