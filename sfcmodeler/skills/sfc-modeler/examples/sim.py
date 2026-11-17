"""Godley & Lavoie（2007）第 3 章模型 SIM：只有政府货币的最简单 SFC 模型。

方程与上游 SFCmodeler 的 nbs/06_godleylavoie.ipynb 一致（上游已与 pysolve3 的结果逐期核对）。
运行：python3 ../scripts/sfc_run.py sim.py --warmup 300 --periods 40 --shock Gd=25@5
解析稳态：Y* = Gd / theta = 100（Gd=20，theta=0.2）。
"""

from SFCmodeler import Parameter, SFCmodel, Variable, d

PLOTS = [["Y", "Cd"], ["Hh"]]


def build():
    global Cd, Cs, Gs, Hh, Hs, Nd, Ns, Td, Ts, Y, YD, Gd, W, alpha1, alpha2, theta
    Variable.default_value = 0

    Cd = Variable("Cd", "家庭消费需求")
    Cs = Variable("Cs", "消费品供给")
    Gs = Variable("Gs", "政府购买（供给）")
    Hh = Variable("Hh", "家庭持有的现金")
    Hs = Variable("Hs", "政府供给的现金")
    Nd = Variable("Nd", "劳动需求")
    Ns = Variable("Ns", "劳动供给")
    Td = Variable("Td", "税收（需求）")
    Ts = Variable("Ts", "税收（供给）")
    Y = Variable("Y", "收入 = GDP")
    YD = Variable("YD", "家庭可支配收入")

    Gd = Parameter("Gd", "政府购买（需求）", 20.0)
    W = Parameter("W", "工资率", 1.0)
    alpha1 = Parameter("alpha1", "收入的边际消费倾向", 0.6)
    alpha2 = Parameter("alpha2", "财富的边际消费倾向", 0.4)
    theta = Parameter("theta", "税率", 0.2)

    return SFCmodel(
        [
            Cs << Cd,
            Gs << Gd,
            Ts << Td,
            Ns << Nd,
            YD << W * Ns - Ts,
            Td << theta * W * Ns,
            Cd << alpha1 * YD + alpha2 * Hh(-1),
            d(Hs) << Gd - Td,
            d(Hh) << YD - Cd,
            Y << Cs + Gs,
            Nd << Y / W,
        ]
    )


def checks(model):
    # 交易流量矩阵的各列（部门预算约束）和货币市场；每项都应恒为 0
    return {
        "家庭：W·Ns − Ts − Cd − ΔHh": W * Ns - Ts - Cd - d(Hh),
        "生产：Cs + Gs − W·Nd": Cs + Gs - W * Nd,
        "政府：Td − Gd + ΔHs": Td - Gd + d(Hs),
        "货币：Hs − Hh（冗余方程）": Hs - Hh,
    }
