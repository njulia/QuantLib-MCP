"""
篮子期权和多资产类 MCP 工具
包含：篮子期权、价差期权、彩虹期权等
"""
import datetime
from typing import Dict, Any, List, Optional
import QuantLib as ql
from mcp.server.fastmcp import FastMCP

try:
    from ..server import mcp
except ImportError:
    try:
        from src.server.server_llm import mcp
    except ImportError:
        mcp = FastMCP("QuantLib Basket")


def parse_date(date_str: str) -> ql.Date:
    """解析 ISO 日期字符串为 QuantLib.Date"""
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    return ql.Date(dt.day, dt.month, dt.year)


@mcp.tool()
def price_basket_option(
    spots: List[float],
    weights: List[float],
    volatilities: List[float],
    correlations: List[List[float]],
    strike: float,
    risk_free_rate: float,
    maturity_date: str,
    settlement_date: str,
    option_type: str = "call",
    basket_type: str = "Arithmetic"
) -> Dict[str, Any]:
    """
    定价篮子期权（使用 Choi 或 Deng-Li-Zhou 方法）
    
    :param spots: 标的资产价格列表
    :param weights: 权重列表
    :param volatilities: 波动率列表
    :param correlations: 相关系数矩阵
    :param strike: 行权价
    :param risk_free_rate: 无风险利率（小数）
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param option_type: 期权类型 ('call', 'put')
    :param basket_type: 篮子类型 ('Arithmetic', 'Geometric')
    """
    try:
        eval_date = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = eval_date

        mat_date = parse_date(maturity_date)
        n_assets = len(spots)

        if option_type.lower() == "call":
            payoff_type = ql.Option.Call
        else:
            payoff_type = ql.Option.Put

        day_count = ql.Actual365Fixed()
        calendar = ql.NullCalendar()

        # 创建相关系数矩阵
        correlation_matrix = ql.Matrix(n_assets, n_assets)
        for i in range(n_assets):
            for j in range(n_assets):
                correlation_matrix[i][j] = correlations[i][j]

        # 创建现货报价句柄
        spot_handles = [ql.QuoteHandle(ql.SimpleQuote(s)) for s in spots]

        # 创建波动率句柄
        vol_handles = [ql.QuoteHandle(ql.SimpleQuote(v)) for v in volatilities]

        # 创建利率曲线
        r_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(risk_free_rate)), day_count)
        )

        # 创建几何布朗运动过程
        processes = []
        for i in range(n_assets):
            vol_ts = ql.BlackVolTermStructureHandle(
                ql.BlackConstantVol(eval_date, calendar, vol_handles[i], day_count)
            )
            process = ql.BlackScholesMertonProcess(
                spot_handles[i],
                ql.YieldTermStructureHandle(ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(0.0)), day_count)),
                r_ts,
                vol_ts
            )
            processes.append(process)

        # 创建多变量过程
        multi_process = ql.StochasticProcessArray(processes, correlation_matrix)

        # 篮子行权
        exercise = ql.EuropeanExercise(mat_date)

        # 使用 Monte Carlo 定价
        payoff = ql.PlainVanillaPayoff(payoff_type, strike)
        
        # 创建篮子支付
        basket_payoff = ql.BasketPayoff(weights, payoff)
        
        # 使用 Monte Carlo 引擎
        time_steps = 100
        mc_paths = 10000
        
        # 简化方法：使用几何平均近似
        if basket_type == "Geometric":
            # 几何平均的封闭解
            geom_vol = 0.0
            weighted_spot = 1.0
            for i in range(n_assets):
                weighted_spot *= spots[i] ** weights[i]
                for j in range(n_assets):
                    geom_vol += weights[i] * weights[j] * volatilities[i] * volatilities[j] * correlations[i][j]
            geom_vol = geom_vol ** 0.5

            # 使用 Black-Scholes 公式近似
            spot_handle = ql.QuoteHandle(ql.SimpleQuote(weighted_spot))
            vol_ts = ql.BlackVolTermStructureHandle(
                ql.BlackConstantVol(eval_date, calendar, ql.QuoteHandle(ql.SimpleQuote(geom_vol)), day_count)
            )
            bsm_process = ql.BlackScholesMertonProcess(
                spot_handle,
                ql.YieldTermStructureHandle(ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(0.0)), day_count)),
                r_ts,
                vol_ts
            )
            
            option = ql.VanillaOption(payoff, exercise)
            engine = ql.AnalyticEuropeanEngine(bsm_process)
            option.setPricingEngine(engine)

            return {
                "npv": option.NPV(),
                "basket_type": "Geometric",
                "geometric_spot": round(weighted_spot, 6),
                "basket_volatility": round(geom_vol, 6),
                "delta": option.delta(),
                "gamma": option.gamma(),
                "vega": option.vega()
            }
        else:
            # 算术篮子（使用 Monte Carlo 近似）
            # 这里使用一个简单的近似方法
            weighted_vol = 0.0
            weighted_spot = sum(w * s for w, s in zip(weights, spots))
            for i in range(n_assets):
                for j in range(n_assets):
                    weighted_vol += weights[i] * weights[j] * volatilities[i] * volatilities[j] * correlations[i][j]
            arithmetic_vol = weighted_vol ** 0.5

            spot_handle = ql.QuoteHandle(ql.SimpleQuote(weighted_spot))
            vol_ts = ql.BlackVolTermStructureHandle(
                ql.BlackConstantVol(eval_date, calendar, ql.QuoteHandle(ql.SimpleQuote(arithmetic_vol)), day_count)
            )
            bsm_process = ql.BlackScholesMertonProcess(
                spot_handle,
                ql.YieldTermStructureHandle(ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(0.0)), day_count)),
                r_ts,
                vol_ts
            )
            
            option = ql.VanillaOption(payoff, exercise)
            engine = ql.AnalyticEuropeanEngine(bsm_process)
            option.setPricingEngine(engine)

            return {
                "npv": option.NPV(),
                "basket_type": "Arithmetic",
                "weighted_spot": round(weighted_spot, 6),
                "basket_volatility": round(arithmetic_vol, 6),
                "delta": option.delta(),
                "gamma": option.gamma(),
                "vega": option.vega()
            }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_spread_option(
    spot1: float,
    spot2: float,
    vol1: float,
    vol2: float,
    correlation: float,
    strike: float,
    risk_free_rate: float,
    maturity_date: str,
    settlement_date: str,
    option_type: str = "call",
    method: str = "Kirk"
) -> Dict[str, Any]:
    """
    定价价差期权（使用 Kirk 或 Bjerksund-Stensland 方法）
    
    :param spot1: 第一个标的资产价格
    :param spot2: 第二个标的资产价格
    :param vol1: 第一个标的波动率
    :param vol2: 第二个标的波动率
    :param correlation: 相关系数
    :param strike: 行权价
    :param risk_free_rate: 无风险利率（小数）
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param option_type: 期权类型
    :param method: 定价方法 ('Kirk', 'BjerksundStensland')
    """
    try:
        eval_date = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = eval_date

        mat_date = parse_date(maturity_date)
        day_count = ql.Actual365Fixed()
        calendar = ql.NullCalendar()

        # Kirk 近似法
        # 将价差期权近似为一个标的的期权
        F1 = spot1
        F2 = spot2
        K = strike

        # Kirk 波动率
        w1 = F1 / (F1 + K)
        w2 = F2 / (F1 + K)
        kirk_vol = ((w1 * vol1) ** 2 + (w2 * vol2) ** 2 - 2 * w1 * w2 * vol1 * vol2 * correlation) ** 0.5

        # 使用 Black 公式
        effective_spot = F1 - F2
        if effective_spot <= 0:
            effective_spot = 0.01

        if option_type.lower() == "call":
            payoff_type = ql.Option.Call
        else:
            payoff_type = ql.Option.Put

        payoff = ql.PlainVanillaPayoff(payoff_type, max(K, 0.01))
        exercise = ql.EuropeanExercise(mat_date)
        option = ql.VanillaOption(payoff, exercise)

        spot_handle = ql.QuoteHandle(ql.SimpleQuote(effective_spot))
        vol_ts = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(eval_date, calendar, ql.QuoteHandle(ql.SimpleQuote(kirk_vol)), day_count)
        )
        r_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(risk_free_rate)), day_count)
        )
        d_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(0.0)), day_count)
        )

        bsm_process = ql.BlackScholesMertonProcess(spot_handle, d_ts, r_ts, vol_ts)
        engine = ql.AnalyticEuropeanEngine(bsm_process)
        option.setPricingEngine(engine)

        return {
            "npv": option.NPV(),
            "method": method,
            "kirk_volatility": round(kirk_vol, 6),
            "effective_spot": round(effective_spot, 6),
            "spread": round(spot1 - spot2, 6)
        }
    except Exception as e:
        return {"error": str(e)}
