"""Godley & Lavoie（2007）第 5 章模型 LP：长期债券、资本利得和预期。

方程、参数和初始存量与上游 nbs/06_godleylavoie.ipynb 一致（上游已与 pysolve3 核对）。
初始值取自书中的稳态，所以不需要预热。
运行：python3 ../scripts/sfc_run.py lp.py --periods 60 --shock Pblbar=15@10 --plot Y --plot V
"""

from SFCmodeler import Parameter, SFCmodel, Variable, d

PLOTS = [["Y"], ["V"], ["Bh", "BLh"]]


def build():
    global Bcb, Bh, Bs, BLh, BLs, CG, C, Hh, Hs, Pbl, Rb, T, V, Y, YDr
    Variable.default_value = 0
    Parameter.default_value = 0

    Bcb = Variable("Bcb", "中央银行持有的短期国债")
    Bd = Variable("Bd", "短期国债需求")
    Bh = Variable("Bh", "家庭持有的短期国债")
    Bs = Variable("Bs", "政府发行的短期国债")
    BLd = Variable("BLd", "长期国债需求（份数）")
    BLh = Variable("BLh", "家庭持有的长期国债（份数）")
    BLs = Variable("BLs", "长期国债供给（份数）")
    CG = Variable("CG", "长期国债的资本利得")
    CGe = Variable("CGe", "预期资本利得")
    C = Variable("C", "消费")
    ERrbl = Variable("ERrbl", "长期国债的预期收益率")
    Hd = Variable("Hd", "现金需求")
    Hh = Variable("Hh", "家庭持有的现金")
    Hs = Variable("Hs", "中央银行供给的现金")
    Pbl = Variable("Pbl", "长期国债价格")
    Pble = Variable("Pble", "预期长期国债价格")
    Rb = Variable("Rb", "短期国债利率")
    Rbl = Variable("Rbl", "长期国债利率")
    T = Variable("T", "税收")
    V = Variable("V", "家庭财富")
    Ve = Variable("Ve", "预期家庭财富")
    Y = Variable("Y", "收入 = GDP")
    YDr = Variable("YDr", "常规可支配收入")
    YDre = Variable("YDre", "预期常规可支配收入")

    alpha1 = Parameter("alpha1", "收入的边际消费倾向", 0.8)
    alpha2 = Parameter("alpha2", "财富的边际消费倾向", 0.2)
    chi = Parameter("chi", "对预期债券价格的确信权重", 0.1)
    lambda20 = Parameter("lambda20", "短期国债需求参数", 0.44196)
    lambda22 = Parameter("lambda22", "短期国债需求参数", 1.1)
    lambda23 = Parameter("lambda23", "短期国债需求参数", 1.0)
    lambda24 = Parameter("lambda24", "短期国债需求参数", 0.03)
    lambda30 = Parameter("lambda30", "长期国债需求参数", 0.3997)
    lambda32 = Parameter("lambda32", "长期国债需求参数", 1.0)
    lambda33 = Parameter("lambda33", "长期国债需求参数", 1.1)
    lambda34 = Parameter("lambda34", "长期国债需求参数", 0.03)
    theta = Parameter("theta", "税率", 0.1938)
    G = Parameter("G", "政府购买", 20.0)
    Rbar = Parameter("Rbar", "短期利率（政策设定）", 0.03)
    Pblbar = Parameter("Pblbar", "长期国债价格（政策设定）", 20.0)

    model = SFCmodel(
        [
            Y << C + G,                                                                     # 5.1
            YDr << Y - T + Rb(-1) * Bh(-1) + BLh(-1),                                       # 5.2
            T << theta * (Y + Rb(-1) * Bh(-1) + BLh(-1)),                                   # 5.3
            d(V) << (YDr - C) + CG,                                                         # 5.4
            CG << (Pbl - Pbl(-1)) * BLh(-1),
            C << alpha1 * YDre + alpha2 * V(-1),
            Ve << V(-1) + (YDre - C) + CG,
            Hh << V - Bh - Pbl * BLh,
            Hd << Ve - Bd - Pbl * BLd,
            Bd << Ve * lambda20 + Ve * lambda22 * Rb - Ve * lambda23 * ERrbl - lambda24 * YDre,
            BLd << (Ve * lambda30 - Ve * lambda32 * Rb + Ve * lambda33 * ERrbl - lambda34 * YDre) / Pbl,
            Bh << Bd,
            BLh << BLd,
            d(Bs) << (G + Rb(-1) * Bs(-1) + BLs(-1)) - (T + Rb(-1) * Bcb(-1)) - (BLs - BLs(-1)) * Pbl,
            d(Hs) << Bcb - Bcb(-1),
            Bcb << Bs - Bh,
            BLs << BLh,
            ERrbl << Rbl + chi * (Pble - Pbl) / Pbl,
            Rbl << 1.0 / Pbl,
            Pble << Pbl,
            CGe << chi * (Pble - Pbl) * BLh,
            YDre << YDr(-1),
            Rb << Rbar,
            Pbl << Pblbar,
        ],
        redundant_equation=Hs << Hh,
    )

    # 书中的初始存量（稳态）。书里 Hs = 20.125 是四舍五入的结果，与 V − Bh − Pbl·BLh = 20.124
    # 差 0.001，会让冗余方程 Hs = Hh 每期都差 0.001；这里改用与资产负债表一致的 20.124。
    model[:] = {
        V: 95.803, Bh: 37.839, Bs: 57.964, Bcb: 57.964 - 37.839,
        BLh: 1.892, BLs: 1.892, Hs: 95.803 - 37.839 - 20 * 1.892, YDr: 95.803, Rb: 0.03, Pbl: 20,
    }
    return model


def checks(model):
    return {
        "家庭：YDr − C + CG − ΔV": YDr - C + CG - d(V),
        "资产负债表：V − Hh − Bh − Pbl·BLh": V - Hh - Bh - Pbl * BLh,
        "短期国债市场：Bs − Bh − Bcb": Bs - Bh - Bcb,
        "货币：Hs − Hh（冗余方程）": Hs - Hh,
    }
