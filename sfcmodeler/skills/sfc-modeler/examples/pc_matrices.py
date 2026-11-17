"""模型 PC 的“矩阵写法”：先写资产负债表和交易流量矩阵，再让 SFCmodeler 生成方程和核对式。

与 pc.py 的区别：
- 政府、中央银行两个部门的预算约束（4.8、4.9）和国债市场出清（4.10）不手写，
  而是用 TFmatrix / Asset 的零表达式加 solve_for 生成；
- checks() 直接返回交易流量矩阵每一行、每一列的和，任何一处漏记或记错都会在核对表里暴露。

运行：python3 ../scripts/sfc_run.py pc_matrices.py --warmup 500 --periods 40 --shock Rbar=0.035@5
结果应与 pc.py 完全相同。
"""

from SFCmodeler import (
    Asset, BSmatrix, Parameter, SFCmodel, Sector, TFmatrix, Transaction, Variable, solve_for,
)

PLOTS = [["Y", "C"], ["V", "Hh", "Bh"]]

TF = None  # build() 之后保存交易流量矩阵，供 checks() 使用
BS = None


def build():
    global TF, BS, Bcb, Bh, Bs, C, Hh, Hs, R, T, V, Y, YD
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

    # 1. 部门（矩阵的列）
    Households = Sector(NW=V, name="家庭")
    Production = Sector(name="生产")
    Government = Sector(name="政府")
    CB = Sector(name="中央银行")
    sectors = [Households, Production, Government, CB]

    # 2. 资产（资产负债表的行）。issuer 是负债方；payout 给出每单位持有量的利息
    Money = Asset(issuer=CB, supplies={Households: Hs}, demands={Households: Hh}, name="现金")
    Bills = Asset(
        issuer=Government,
        demands={Households: Bh, CB: Bcb},
        total_supply=Bs,
        payout=lambda q: R(-1) * q(-1),
        name="国债",
    )

    # 3. 非金融交易（交易流量矩阵的上半部分）；利息和存量变化两类行由 TFmatrix 自动生成
    transactions = [
        Transaction({Households: -C, Production: C}),
        Transaction({Government: -G, Production: G}),
        Transaction({Production: -Y, Households: Y}),
        Transaction({Households: -T, Government: T}),
        Transaction({CB: -R(-1) * Bcb(-1), Government: R(-1) * Bcb(-1)}),  # 央行利润上缴
    ]
    TF = TFmatrix(sectors=sectors, transactions=transactions, assets=[Money, Bills])
    BS = BSmatrix(sectors=sectors, assets=[Money, Bills])

    return SFCmodel(
        [
            Y << C + G,
            YD << Y - T + R(-1) * Bh(-1),
            T << theta * (Y + R(-1) * Bh(-1)),
            V << V(-1) + (YD - C),
            C << alpha1 * YD + alpha2 * V(-1),
            Hh << V - Bh,
            Bh << V * lambda0 + V * lambda1 * R - lambda2 * YD,
            solve_for(TF.sector_zero_expression(Government), Bs),  # 政府预算约束 → Bs
            solve_for(TF.sector_zero_expression(CB), Hs),          # 央行预算约束 → Hs
            solve_for(Bills.market_zero_expression(), Bcb),        # 国债市场出清 → Bcb
            R << Rbar,
        ],
        redundant_equation=Hh << Hs,
    )


def checks(model):
    out = {}
    for sector in TF.sectors:
        out[f"列和：{sector}"] = TF.sector_zero_expression(sector)
    for i, row in enumerate(TF.transactions, 1):
        out[f"行和：交易 {i}"] = row.zero_expression()
    out["资产负债表：家庭净值"] = BS.sector_zero_expression(TF.sectors[0])
    return out
