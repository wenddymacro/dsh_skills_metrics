{smcl}
{* *! version 1.0.0  21nov2026}{...}
{viewerjumpto "Syntax" "mycmd##syntax"}{...}
{viewerjumpto "Description" "mycmd##description"}{...}
{viewerjumpto "Options" "mycmd##options"}{...}
{viewerjumpto "Examples" "mycmd##examples"}{...}
{viewerjumpto "Stored results" "mycmd##results"}{...}
{title:Title}

{phang}
{bf:mycmd} {hline 2} One-line description of the estimator


{marker syntax}{...}
{title:Syntax}

{p 8 17 2}
{cmd:mycmd} {depvar} {indepvars} {ifin} {weight} [{cmd:,} {it:options}]

{synoptset 20 tabbed}{...}
{synopthdr}
{synoptline}
{syntab:Model}
{synopt:{opt nocons:tant}}suppress the constant term{p_end}
{syntab:SE}
{synopt:{opth vce(vcetype)}}{it:vcetype} may be {opt robust} or {opt cl:uster} {it:clustvar}{p_end}
{syntab:Reporting}
{synopt:{opt l:evel(#)}}set confidence level; default is {cmd:level(95)}{p_end}
{synoptline}
{p 4 6 2}
{it:indepvars} may contain factor variables; see {help fvvarlist}.{p_end}
{p 4 6 2}
{cmd:pweight}s and {cmd:fweight}s are allowed; see {help weight}.{p_end}


{marker description}{...}
{title:Description}

{pstd}
{cmd:mycmd} fits ... (method in plain words, when to use it, reference).


{marker options}{...}
{title:Options}

{phang}
{opt noconstant} suppresses the constant term.

{phang}
{opt level(#)} specifies the confidence level, as a percentage, for confidence intervals.


{marker examples}{...}
{title:Examples}

{phang2}{cmd:. sysuse auto, clear}{p_end}
{phang2}{cmd:. mycmd price mpg weight}{p_end}
{phang2}{cmd:. mycmd price mpg weight, vce(robust)}{p_end}


{marker results}{...}
{title:Stored results}

{pstd}
{cmd:mycmd} stores the following in {cmd:e()}:

{synoptset 20 tabbed}{...}
{p2col 5 20 24 2: Scalars}{p_end}
{synopt:{cmd:e(N)}}number of observations{p_end}
{p2col 5 20 24 2: Macros}{p_end}
{synopt:{cmd:e(cmd)}}{cmd:mycmd}{p_end}
{synopt:{cmd:e(cmdline)}}command as typed{p_end}
{synopt:{cmd:e(vce)}}{it:vcetype} specified in {cmd:vce()}{p_end}
{p2col 5 20 24 2: Matrices}{p_end}
{synopt:{cmd:e(b)}}coefficient vector{p_end}
{synopt:{cmd:e(V)}}variance-covariance matrix of the estimators{p_end}
{p2col 5 20 24 2: Functions}{p_end}
{synopt:{cmd:e(sample)}}marks estimation sample{p_end}


{title:References}

{phang}
Author, A. 2026. Title. {it:Journal} 1: 1-10.


{title:Author}

{pstd}
(name and contact supplied by the package author)
