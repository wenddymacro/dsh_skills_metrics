# 帮助文件与打包

scriber 写帮助文件、builder 改打包清单、tester 做包装检查时依据本文件。

## 1. SMCL 帮助文件骨架

模板在 `templates/helpfile.sthlp`。必备章节和顺序：

1. `{smcl}` 第一行；`{* *! version 1.0.0  21nov2026}{...}` 版本注释（与 ado 的 `*!` 行一致）
2. 标题：`{title:Title}` 加 `{phang}{bf:mycmd} {hline 2} 一句话说明{p_end}`
3. `{title:Syntax}`：`{p 8 17 2}{cmd:mycmd} {depvar} {indepvars} {ifin} {weight} [{cmd:,} {it:options}]{p_end}`，再用 `{synoptset}` / `{synopthdr}` / `{synopt:}` 列出全部选项，并说明支持哪些权重、是否支持 `by` 和因子变量
4. `{title:Description}`：方法是什么、什么时候用；引用论文
5. `{title:Options}`：每个选项一段 `{phang}{opt level(#)} ...{p_end}`
6. `{title:Examples}`：可以直接运行的例子，优先用 `sysuse` / `webuse` 自带数据；可点击运行用 `{stata "sysuse auto, clear"}`
7. `{title:Stored results}`：列出全部 `e()` / `r()`，与 ado 实际返回的一一对应（`{synopt:{cmd:e(N)}}number of observations{p_end}`）
8. `{title:Methods and formulas}`（估计命令建议写）
9. `{title:References}`
10. `{title:Author}`：作者信息由用户提供，不要编造邮箱

SMCL 注意事项：

- 字面花括号写成 `{c -(}` 和 `{c )-}`，否则会被当作 SMCL 指令。
- `{p_end}` 结束段落；`{pstd}`、`{phang}`、`{pmore}` 控制缩进。
- 选项缩写在帮助里用 `{opt l:evel(#)}` 标出，与 `syntax` 里大写字母一致。
- 每个公开命令都要有帮助文件；改了选项或返回值，帮助文件必须同步更新。
- 检查：`translate mycmd.sthlp /tmp/mycmd.txt, translator(smcl2txt) replace` 能成功转换。

## 2. 打包清单

**`<pkgname>.pkg`**（模板 `templates/package.pkg`）：

```
v 3
d mycmd: one-line description
d Author Name
d Distribution-Date: 20261121
d License: MIT
f mycmd.ado
f mycmd.sthlp
f mycmd_p.ado
f lmycmd.mlib
```

- `v 3` 必须在第一行；`d` 行是说明；每个要安装的文件一行 `f`（可以带子目录，如 `f m/mycmd.ado`）。
- `Distribution-Date` 用 `YYYYMMDD`，每次发布更新（`adoupdate` 靠它判断是否有新版）。
- 所有公开 ado、帮助文件、mlib、配套数据（`f mydata.dta`）都要列入；认证脚本和开发文件不要列入。

**`stata.toc`**：

```
v 3
d Packages by Author Name
p mycmd one-line description
```

`p` 后面是 pkg 文件名（不带 `.pkg`）。

## 3. 发布前检查清单

1. `stata_pkg_check.py` 没有 ERROR。
2. 在临时 PLUS 目录里 `net install <pkgname>, from("<项目目录>") replace` 成功；`which <cmd>` 显示新版本号。
3. 帮助文件能转换为文本，例子实际运行一遍不报错。
4. ado 的 `*!` 版本、sthlp 的版本注释、pkg 的 `Distribution-Date` 三者一致更新。
5. README 写明安装方式：`net install <pkgname>, from("https://raw.githubusercontent.com/<用户>/<仓库>/main/")` 或 SSC。

**提交 SSC**：需要用户自己把压缩包和说明发给 SSC 维护者（Kit Baum）。插件只准备文件、核对清单，不代为发送邮件。

## 4. 复现项目的文档

- `README.md`：数据来源和获取方式、软件版本、依赖的 SSC 包、运行顺序、各脚本产出、预计耗时。
- `master.do`：设好路径（相对路径）、`version`、种子、依赖检查，按顺序 `do` 各脚本。
- 符合 AEA 数据编辑办公室（Data Editor）复现包要求时，在 README 里列出数据可用性说明和计算环境。
