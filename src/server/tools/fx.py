"""
外汇和 Quanto 类 MCP 工具
包含：外汇期权、Quanto 期权、交叉货币工具等
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
        mcp = FastMCP("QuantLib FX")


def parse_date(date_str: str) -> ql.Date:
    """解析 ISO 日期字符串为 QuantLib.Date"""
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    return ql.Date(dt.day, dt.month, dt.year)


@mcp.tool()
def price_fx_vanilla_option(
    spot_fx_rate: float,
    strike: float,
    volatility: float,
    domestic_rate: float,
    foreign_rate: float,
    maturity_date: str,
    settlement_date: str,
    option_type: str = "call",
    notional: float = 1_000_000.0
) -> Dict[str, Any]:
    """
    定价外汇香草期权（使用 Garman-Kohlhagen 模型）
    
    :param spot_fx_rate: 即期汇率（每单位外币的本币数量）
    :param strike: 行权汇率
    :param volatility: 汇率波动率（小数）
    :param domestic_rate: 本币无风险利率（小数）
    :param foreign_rate: 外币无风险利率（小数）
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param option_type: 期权类型 ('call' = 买入外币, 'put' = 卖出外币)
    :param notional: 名义本金（外币）
    """
    try:
        eval_date = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = eval_date

        mat_date = parse_date(maturity_date)
        if option_type.lower() == "call":
            payoff_type = ql.Option.Call
        else:
            payoff_type = ql.Option.Put

        payoff = ql.PlainVanillaPayoff(payoff_type, strike)
        exercise = ql.EuropeanExercise(mat_date)
        option = ql.VanillaOption(payoff, exercise)

        day_count = ql.Actual365Fixed()
        calendar = ql.NullCalendar()

        spot_handle = ql.QuoteHandle(ql.SimpleQuote(spot_fx_rate))
        
        # 本币利率
        r_domestic = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(domestic_rate)), day_count)
        )
        # 外币利率（视为股息率）
        r_foreign = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(foreign_rate)), day_count)
        )
        vol_ts = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(eval_date, calendar, ql.QuoteHandle(ql.SimpleQuote(volatility)), day_count)
        )

        # Garman-Kohlhagen 过程
        gk_process = ql.GarmanKohlagenProcess(
            spot_handle, r_foreign, r_domestic, vol_ts
        )

        # 定价引擎
        engine = ql.AnalyticEuropeanEngine(gk_process)
        option.setPricingEngine(engine)

        return {
            "npv_per_unit": option.NPV(),
            "npv_total": option.NPV() * notional,
            "delta_per_unit": option.delta(),
            "gamma": option.gamma(),
            "vega": option.vega(),
            "theta": option.theta(),
            "rho_domestic": option.rho(),
            "notional": notional,
            "spot_fx_rate": spot_fx_rate,
            "strike": strike,
            "moneyness": round(spot_fx_rate / strike, 6)
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_quanto_option(
    spot: float,
    strike: float,
    equity_volatility: float,
    fx_volatility: float,
    correlation_equity_fx: float,
    domestic_rate: float,
    foreign_rate: float,
    maturity_date: str,
    settlement_date: str,
    option_type: str = "call",
    quanto_factor: float = 1.0,
    notional: float = 1_000_000.0
) -> Dict[str, Any]:
    """
    定价 Quanto 期权（跨境收益锁定汇率）
    
    :param spot: 标的资产价格（外币计价）
    :param strike: 行权价
    :param equity_volatility: 标的资产波动率
    :param fx_volatility: 汇率波动率
    :param correlation_equity_fx: 标的资产与汇率的相关系数
    :param domestic_rate: 本币无风险利率（小数）
    :param foreign_rate: 外币无风险利率（小数）
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param option_type: 期权类型
    :param quanto_factor: Quanto 调整因子
    :param notional: 名义本金
    """
    try:
        eval_date = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = eval_date

        mat_date = parse_date(maturity_date)
        if option_type.lower() == "call":
            payoff_type = ql.Option.Call
        else:
            payoff_type = ql.Option.Put

        payoff = ql.PlainVanillaPayoff(payoff_type, strike)
        exercise = ql.EuropeanExercise(mat_date)
        option = ql.VanillaOption(payoff, exercise)

        day_count = ql.Actual365Fixed()
        calendar = ql.NullCalendar()

        # Quanto 调整后的股息率
        quanto_dividend = foreign_rate - domestic_rate - correlation_equity_fx * equity_volatility * fx_volatility

        spot_handle = ql.QuoteHandle(ql.SimpleQuote(spot * quanto_factor))
        
        r_domestic = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(domestic_rate)), day_count)
        )
        quanto_yield = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(quanto_dividend)), day_count)
        )
        vol_ts = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(eval_date, calendar, ql.QuoteHandle(ql.SimpleQuote(equity_volatility)), day_count)
        )

        bsm_process = ql.BlackScholesMertonProcess(spot_handle, quanto_yield, r_domestic, vol_ts)
        engine = ql.AnalyticEuropeanEngine(bsm_process)
        option.setPricingEngine(engine)

        return {
            "npv_per_unit": option.NPV(),
            "npv_total": option.NPV() * notional,
            "delta": option.delta(),
            "gamma": option.gamma(),
            "vega": option.vega(),
            "quanto_adjustment": round(quanto_dividend, 6),
            "correlation_impact": round(correlation_equity_fx * equity_volatility * fx_volatility, 6)
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def calculate_fx_forward_rate(
    spot_fx_rate: float,
    domestic_rate: float,
    foreign_rate: float,
    settlement_date: str,
    maturity_date: str,
    day_count_convention: str = "Actual360"
) -> Dict[str, Any]:
    """
    计算外汇远期汇率
    
    :param spot_fx_rate: 即期汇率
    :param domestic_rate: 本币利率（小数）
    :param foreign_rate: 外币利率（小数）
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param day_count_convention: 日期计数惯例
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        ql.Settings.instance().evaluationDate = settle_d

        day_counter = ql.Actual360() if day_count_convention == "Actual360" else ql.Actual365Fixed()
        year_frac = day_counter.yearFraction(settle_d, mat_d)

        # 远期汇率公式：F = S * exp((r_d - r_f) * T)
        forward_rate = spot_fx_rate * ((1 + domestic_rate * year_frac) / (1 + foreign_rate * year_frac))
        
        # 远期点数
        forward_points = forward_rate - spot_fx_rate

        return {
            "spot_fx_rate": spot_fx_rate,
            "forward_rate": round(forward_rate, 6),
            "forward_points": round(forward_points, 6),
            "year_fraction": round(year_frac, 6),
            "domestic_rate": domestic_rate,
            "foreign_rate": foreign_rate,
            "settlement_date": settle_d.to_datetime().strftime("%Y-%m-%d"),
            "maturity_date": mat_d.to_datetime().strftime("%Y-%m-%d")
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def create_fx_swap_curve(
    settlement_date: str,
    spot_fx_rate: float,
    domestic_rates: List[Dict[str, Any]],
    foreign_rates: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    构建外汇互换曲线
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param spot_fx_rate: 即期汇率
    :param domestic_rates: 本币利率列表 [{"tenor": "1M", "rate": 0.05}, ...]
    :param foreign_rates: 外币利率列表
    """
    try:
        settle_d = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = settle_d

        curve_points = []
        for dr, fr in zip(domestic_rates, foreign_rates):
            tenor = dr['tenor']
            d_rate = dr['rate']
            f_rate = fr['rate']

            val = int(tenor[:-1])
            unit = tenor[-1].upper()
            if unit == 'M':
                mat_d = settle_d + ql.Period(val, ql.Months)
            else:
                mat_d = settle_d + ql.Period(val, ql.Years)

            day_counter = ql.Actual360()
            year_frac = day_counter.yearFraction(settle_d, mat_d)

            forward_rate = spot_fx_rate * ((1 + d_rate * year_frac) / (1 + f_rate * year_frac))
            forward_points = forward_rate - spot_fx_rate

            curve_points.append({
                "tenor": tenor,
                "maturity_date": mat_d.to_datetime().strftime("%Y-%m-%d"),
                "domestic_rate": d_rate,
                "foreign_rate": f_rate,
                "forward_rate": round(forward_rate, 6),
                "forward_points": round(forward_points, 6),
                "year_fraction": round(year_frac, 6)
            })

        return {
            "spot_fx_rate": spot_fx_rate,
            "curve_points": curve_points
        }
    except Exception as e:
        return {"error": str(e)}
