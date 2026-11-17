"""Godley & Lavoie（2007）第 4 章模型 PC：政府债券、中央银行和投资组合选择。

方程与上游 nbs/06_godleylavoie.ipynb 一致（上游已与 pysolve3 核对）。Hh = Hs 由其余方程隐含，
作为冗余方程每期核对。
运行：python3 ../scripts/sfc_run.py pc.py --warmup 500 --periods 40 --shock Rbar=0.035@5
"""

from SFCmodeler import Parameter, SFCmodel, Variable, d

PLOTS = [["Y", "C"], ["V", "Hh", "Bh"]]


def build():
    global Bcb, Bh, Bs, C, Hh, Hs, R, T, V, Y, YD, alpha1, alpha2, lambda0, lambda1, lambda2, theta, G, Rbar
    Variable.default_value = 0

    Bcb = Variable("Bcb", "中央银行持有的国债")
    Bh = Variable("Bh", "家庭持有的国债")
    Bs = Variable("Bs", "政府发行的国债")
    C = Variable("C", "消费")
    Hh = Variable("Hh", "家庭持有的现金")
    Hs = Variable("Hs", "中央银行供给的现金")
    R = Variable("R", "国债利率")
    T = Variable("T", "税收")
    V = Variable("V", "家庭财富")
    Y = Variable("Y", "收入 = GDP")
    YD = Variable("YD", "家庭可支配收入")

    alpha1 = Parameter("alpha1", "收入的边际消费倾向", 0.6)
    alpha2 = Parameter("alpha2", "财富的边际消费倾向", 0.4)
    lambda0 = Parameter("lambda0", "资产需求函数参数", 0.635)
    lambda1 = Parameter("lambda1", "资产需求函数参数", 5.0)
    lambda2 = Parameter("lambda2", "资产需求函数参数", 0.01)
    theta = Parameter("theta", "税率", 0.2)
    G = Parameter("G", "政府购买", 20.0)
    Rbar = Parameter("Rbar", "政策利率", 0.025)

    return SFCmodel(
        [
            Y << C + G,                                                   # 4.1
            YD << Y - T + R(-1) * Bh(-1),                                 # 4.2
            T << theta * (Y + R(-1) * Bh(-1)),                            # 4.3
            V << V(-1) + (YD - C),                                        # 4.4
            C << alpha1 * YD + alpha2 * V(-1),                            # 4.5
            Hh << V - Bh,                                                 # 4.6
            Bh << V * lambda0 + V * lambda1 * R - lambda2 * YD,           # 4.7
            d(Bs) << (G + R(-1) * Bs(-1)) - (T + R(-1) * Bcb(-1)),       # 4.8
            d(Hs) << Bcb - Bcb(-1),                                       # 4.9
            Bcb << Bs - Bh,                                               # 4.10
            R << Rbar,                                                    # 4.11
        ],
        redundant_equation=Hh << Hs,
    )


def checks(model):
    return {
        "家庭：YD − C − ΔV": YD - C - d(V),
        "资产负债表：V − Hh − Bh": V - Hh - Bh,
        "国债市场：Bs − Bh − Bcb": Bs - Bh - Bcb,
        "货币：Hs − Hh（冗余方程）": Hs - Hh,
    }
