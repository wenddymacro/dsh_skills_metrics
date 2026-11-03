---
name: which-did-should-i-use
description: >-
  Classify a panel by difference-in-differences (DID) design -- classical (CLA), staggered
  adoption (SAD), heterogeneous adoption (HAD) or stable-for-some design (SFSD) -- and name
  the estimator and DID-textbook chapter that fit it, by running the Stata command
  `whichdidshouldiuse` bundled with this skill. Use when the user asks which DID / event-study
  estimator to use (TWFE, csdid, did_multiplegt_dyn, did2s, did_had, ...), whether their
  treatment timing is staggered, or what DID design their data is.
---

# Which DID should I use?

This skill wraps `whichdidshouldiuse` (Trelles, de Chaisemartin & Quispe; MIT licence, upstream
<https://github.com/Credible-Answers/whichDIDshouldIuse>). From four variables -- outcome `Y`,
group `G`, **calendar** time `T`, treatment `D` -- it reports one design and a recommended
estimator, following de Chaisemartin & D'Haultfœuille, *Causal Inference with
Differences-in-Differences: Credible Answers to Hard Questions* (Princeton UP, 2026).

It **classifies; it does not estimate.** Never present its output as a treatment effect.

Everything lives in this skill's resource directory (the base directory reported with this skill):

| Path | Content |
|---|---|
| `scripts/run_whichdid.sh` | Runs the command in Stata batch mode and prints the report plus `return list` |
| `stata/whichdidshouldiuse.ado`, `.sthlp` | The upstream command and its help file |
| `data/*.dta` | The four textbook panels (see "Example panels") |

Requirements: Stata 16+ on this machine (found automatically; otherwise set `STATA_BIN`).
On first use the command installs `distinct` from SSC; HAD panels without stayers also fetch
`did_had`, `nprobust` and `gtools`. That needs network access the first time only.

## Workflow

1. **Find the data and the four roles.** If the user has not named the variables, inspect the file:

   ```sh
   bash <skill-dir>/scripts/run_whichdid.sh --describe /abs/path/data.dta
   ```

   Map `Y` (outcome), `G` (unit / group id), `T` (calendar period: year, quarter, ...) and `D`
   (treatment, 0 = untreated). Ask the user when a role is ambiguous instead of guessing.

2. **Check the preparation rules** before running, and fix them with `--prep` where needed:
   - the panel is **long** (one row per group-period); wide data is reshaped first;
   - `T` is calendar time (gaps are fine; the command normalises internally);
   - `D` has a genuine untreated value of 0 (a treatment coded `{4, 9}` is binary but has no
     untreated state; `r(is_binary)=1` with `r(is_binary01)=0` flags it);
   - pre-period treatment is filled in where it is known to be 0, not left missing;
   - string group ids work, but string `T`/`D` must be converted (`destring`, `encode`).

3. **Run the classification:**

   ```sh
   bash <skill-dir>/scripts/run_whichdid.sh /abs/path/data.dta Y G T D
   bash <skill-dir>/scripts/run_whichdid.sh /abs/path/data.dta Y G T D detail   # full diagnostics
   bash <skill-dir>/scripts/run_whichdid.sh /abs/path/data.dta Y G T D strict   # robustness check
   bash <skill-dir>/scripts/run_whichdid.sh --if 'year >= 1990' /abs/path/data.dta Y G T D
   bash <skill-dir>/scripts/run_whichdid.sh --prep 'reshape long y, i(g) j(year)' /abs/path/wide.dta y g year d
   ```

   `.dta`, `.csv` and `.xlsx` files are accepted. `--prep` runs Stata code after loading
   (separate commands with `;`). `if`/`in` restrictions change the balanced panel and the
   baseline, so they can change the design; prefer restrictions on group-level variables.

4. **Report** in the user's language:
   - the design, the recommended estimator(s), and the textbook chapter;
   - the sub-case for HAD (`r(had_case)`) or SFSD (`r(sfsd_case)`) and what it implies;
   - every sample adjustment that is non-zero, quoting the counts -- above all `r(n_demoted)`
     and any dropped-group line, which can change the answer;
   - when `r(n_demoted) > 0` or groups were dropped, rerun with `strict` and say whether the
     two modes agree (agreement is evidence the repairs are not driving the result).

   Quote the command's own report lines rather than paraphrasing numbers from memory.

## Designs (they nest: CLA ⊂ SAD ⊂ HAD-stayers ⊂ SFSD; the tightest one that holds is reported)

| Design | Meaning | Estimator | Chapter |
|---|---|---|---|
| CLA | Binary 0/1, absorbing, everyone switches on the same date, never-treated controls exist, everyone starts untreated | static / event-study TWFE | 3 |
| SAD | As CLA, but switch dates vary across groups | `csdid`, `did_multiplegt_dyn`, `did2s` | 6 |
| HAD | Everyone starts untreated and switches on the same date, but the dose varies | `did_had`, `did_multiplegt_stat` | 7 |
| SFSD | Groups share a baseline treatment and first switch at different dates; allows non-absorbing treatment and heterogeneous baseline doses | `did_multiplegt_dyn` | 8 |
| OTHER | None of the above | — | 8.5.2 |

HAD sub-cases (`r(had_case)`): `stayers` -- some groups keep `D = 0` at the switch, ATT and WATT
identified at the usual √G rate; `quasi-stayers` -- no stayers but `did_had`'s test does not
reject doses near 0, WATT identified, nonparametric with bias-corrected CIs; `none` -- only the
sign of the WATT is identified, under a heterogeneity assumption; `undetermined` -- `did_had`
could not run (`r(had_why)` says why); the design is still HAD.

SFSD sub-cases (`r(sfsd_case)`): `shared-baseline` (the usual condition) or `continuous-baseline`
(no two groups share a baseline -- continuous treatment at period one; use
`did_multiplegt_dyn`'s `continuous()` option, textbook §8.3.5.1).

Key `r()` flags behind the decision: `any_switchers`, `same_Fg` (common switch date),
`is_binary01`, `is_absorbing`, `zero_baseline`, `common_baseline`, `heterog_dose`, `sfsd_pair`.
Sample counts: `n_groups`, `n_switchers`, `n_never_treated`. The full list of returns is in
`stata/whichdidshouldiuse.sthlp`.

## Example panels (in `data/`)

| File | Command | Expected |
|---|---|---|
| `moser_voena_didtextbook.dta` | `patents subclass year twea` | CLA |
| `wolfers2006_didtextbook.dta` | `div_rate state year udl` | SAD |
| `gentzkowetal_didtextbook.dta` | `prestout cnty90 year numdailies` | SFSD, shared baseline |
| `pierce_schott_didtextbook.dta` | ships **wide**; see below | HAD, quasi-stayers |

Pierce–Schott needs the textbook's preparation first:

```sh
bash <skill-dir>/scripts/run_whichdid.sh \
  --prep 'gen lemp2001 = lemp2000 + delta2001; gen lemp2002 = lemp2000 + delta2002; gen lemp2004 = lemp2000 + delta2004; gen lemp2005 = lemp2000 + delta2005; reshape long lemp, i(indusid) j(year); replace ntrgap = 0 if year <= 2000' \
  <skill-dir>/data/pierce_schott_didtextbook.dta lemp indusid year ntrgap
```

Use these panels when the user wants a demonstration or to check that the setup works.

## Troubleshooting

- `r(had_why) : "did_had did not return a QS test (rc = 198)"` -- the user's `did_had` from SSC
  predates the options this command passes (`option _no_updates not allowed`). The design is
  still HAD; only the sub-case is unknown. Tell the user to update it in Stata with
  `ssc install did_had, replace` (this changes their Stata installation, so do not run it
  without their approval), then rerun.
- `run_whichdid: Stata not found` -- set `STATA_BIN` to the console binary, e.g.
  `/Applications/StataNow/StataMP.app/Contents/MacOS/stata-mp`.
- `run_whichdid: Stata stopped with r(###)` -- read the lines just above it in the output;
  usually a variable name is wrong or `--prep` code failed.

## When Stata is unavailable

Say so plainly and do not invent a classification. You may explain the design definitions
above so the user can reason about their own data, and point them to installing Stata 16+
(or setting `STATA_BIN`). Any classification you reason out by hand must be labelled as an
unverified reading of the definitions, not the command's output.
