"""
期权类 MCP 工具
包含：欧式期权、美式期权、百慕大期权、障碍期权、亚式期权等
"""
import datetime
from typing import Dict, Any, List, Optional
import QuantLib as ql
from mcp.server.fastmcp import FastMCP

try:
    # 尝试从 server.py 获取 mcp 实例
    from ..server import mcp
except ImportError:
    # 如果失败，尝试从 server_llm.py 获取
    try:
        from src.server.server_llm import mcp
    except ImportError:
        mcp = FastMCP("QuantLib Options")


def parse_date(date_str: str) -> ql.Date:
    """解析 ISO 日期字符串为 QuantLib.Date"""
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    return ql.Date(dt.day, dt.month, dt.year)


def get_day_counter(day_count_convention: str) -> ql.DayCounter:
    """获取日期计数惯例"""
    if day_count_convention == "Actual365Fixed":
        return ql.Actual365Fixed()
    elif day_count_convention == "Actual360":
        return ql.Actual360()
    elif day_count_convention == "Thirty360":
        return ql.Thirty360(ql.Thirty360.USA)
    else:
        return ql.Actual365Fixed()


@mcp.tool()
def price_european_option(
    spot: float,
    strike: float,
    volatility: float,
    risk_free_rate: float,
    dividend_yield: float,
    maturity_date: str,
    settlement_date: str,
    option_type: str = "call",
    day_count_convention: str = "Actual365Fixed"
) -> Dict[str, Any]:
    """
    使用 Black-Scholes-Merton 模型定价欧式期权并计算 Greeks
    
    :param spot: 标的资产当前价格
    :param strike: 期权行权价
    :param volatility: 资产波动率（小数，如 0.20 表示 20%）
    :param risk_free_rate: 无风险利率（小数）
    :param dividend_yield: 资产股息率（小数）
    :param maturity_date: 期权到期日期 (YYYY-MM-DD)
    :param settlement_date: 计算结算日期 (YYYY-MM-DD)
    :param option_type: 期权类型 ('call', 'put')
    :param day_count_convention: 日期计数惯例
    """
    try:
        # 设置估值日
        eval_date = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = eval_date

        # 期权设置
        mat_date = parse_date(maturity_date)
        if option_type.lower() == "call":
            payoff_type = ql.Option.Call
        elif option_type.lower() == "put":
            payoff_type = ql.Option.Put
        else:
            return {"error": "Invalid option_type. Must be 'call' or 'put'."}

        payoff = ql.PlainVanillaPayoff(payoff_type, strike)
        exercise = ql.EuropeanExercise(mat_date)
        option = ql.VanillaOption(payoff, exercise)

        # 市场数据过程
        spot_handle = ql.QuoteHandle(ql.SimpleQuote(spot))
        
        day_count = get_day_counter(day_count_convention)
        calendar = ql.NullCalendar()

        r_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(risk_free_rate)), day_count)
        )
        d_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(dividend_yield)), day_count)
        )
        vol_ts = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(eval_date, calendar, ql.QuoteHandle(ql.SimpleQuote(volatility)), day_count)
        )

        bsm_process = ql.BlackScholesMertonProcess(spot_handle, d_ts, r_ts, vol_ts)
        
        # 定价引擎
        engine = ql.AnalyticEuropeanEngine(bsm_process)
        option.setPricingEngine(engine)

        return {
            "npv": option.NPV(),
            "delta": option.delta(),
            "gamma": option.gamma(),
            "vega": option.vega(),
            "theta": option.theta(),
            "rho": option.rho(),
            "implied_volatility": option.impliedVolatility(
                option.NPV(), bsm_process, 1e-6, 1000, 0.05, 5.0
            ) if option.NPV() > 0 else 0.0
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_american_option(
    spot: float,
    strike: float,
    volatility: float,
    risk_free_rate: float,
    dividend_yield: float,
    maturity_date: str,
    settlement_date: str,
    option_type: str = "call",
    engine_type: str = "CRR",
    time_steps: int = 100
) -> Dict[str, Any]:
    """
    定价美式期权（使用二叉树或有限差分方法）
    
    :param spot: 标的资产当前价格
    :param strike: 期权行权价
    :param volatility: 资产波动率（小数）
    :param risk_free_rate: 无风险利率（小数）
    :param dividend_yield: 资产股息率（小数）
    :param maturity_date: 期权到期日期 (YYYY-MM-DD)
    :param settlement_date: 计算结算日期 (YYYY-MM-DD)
    :param option_type: 期权类型 ('call', 'put')
    :param engine_type: 定价引擎类型 ('CRR', 'JR', 'EQP', 'Trigeorgis')
    :param time_steps: 时间步数
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
        exercise = ql.AmericanExercise(eval_date, mat_date)
        option = ql.VanillaOption(payoff, exercise)

        # 市场数据
        spot_handle = ql.QuoteHandle(ql.SimpleQuote(spot))
        day_count = ql.Actual365Fixed()
        calendar = ql.NullCalendar()

        r_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(risk_free_rate)), day_count)
        )
        d_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(dividend_yield)), day_count)
        )
        vol_ts = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(eval_date, calendar, ql.QuoteHandle(ql.SimpleQuote(volatility)), day_count)
        )

        bsm_process = ql.BlackScholesMertonProcess(spot_handle, d_ts, r_ts, vol_ts)
        
        # 二叉树定价引擎
        if engine_type == "JR":
            engine = ql.JarrowsRuddAmericanEngine(bsm_process, time_steps)
        elif engine_type == "EQP":
            engine = ql.EquityPercentageAmericanEngine(bsm_process, time_steps)
        elif engine_type == "Trigeorgis":
            engine = ql.TrigeorgisAmericanEngine(bsm_process, time_steps)
        else:  # CRR
            engine = ql.CRRAmericanEngine(bsm_process, time_steps)
        
        option.setPricingEngine(engine)

        return {
            "npv": option.NPV(),
            "delta": option.delta(),
            "gamma": option.gamma(),
            "vega": option.vega(),
            "theta": option.theta(),
            "rho": option.rho()
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_bermudan_option(
    spot: float,
    strike: float,
    volatility: float,
    risk_free_rate: float,
    dividend_yield: float,
    maturity_date: str,
    settlement_date: str,
    exercise_dates: List[str],
    option_type: str = "call",
    time_steps: int = 100
) -> Dict[str, Any]:
    """
    定价百慕大期权（可在多个预先确定的日期行权）
    
    :param spot: 标的资产当前价格
    :param strike: 期权行权价
    :param volatility: 资产波动率（小数）
    :param risk_free_rate: 无风险利率（小数）
    :param dividend_yield: 资产股息率（小数）
    :param maturity_date: 期权到期日期 (YYYY-MM-DD)
    :param settlement_date: 计算结算日期 (YYYY-MM-DD)
    :param exercise_dates: 可行权日期列表 (YYYY-MM-DD)
    :param option_type: 期权类型
    :param time_steps: 时间步数
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
        
        # 百慕大行权日期
        bermudan_dates = [parse_date(d) for d in exercise_dates]
        exercise = ql.BermudanExercise(bermudan_dates)
        option = ql.VanillaOption(payoff, exercise)

        # 市场数据
        spot_handle = ql.QuoteHandle(ql.SimpleQuote(spot))
        day_count = ql.Actual365Fixed()
        calendar = ql.NullCalendar()

        r_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(risk_free_rate)), day_count)
        )
        d_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(dividend_yield)), day_count)
        )
        vol_ts = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(eval_date, calendar, ql.QuoteHandle(ql.SimpleQuote(volatility)), day_count)
        )

        bsm_process = ql.BlackScholesMertonProcess(spot_handle, d_ts, r_ts, vol_ts)
        
        # 定价引擎
        engine = ql.CRRBermudanEngine(bsm_process, time_steps)
        option.setPricingEngine(engine)

        return {
            "npv": option.NPV(),
            "delta": option.delta(),
            "gamma": option.gamma(),
            "exercise_dates": exercise_dates
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_barrier_option(
    spot: float,
    strike: float,
    volatility: float,
    risk_free_rate: float,
    dividend_yield: float,
    maturity_date: str,
    settlement_date: str,
    barrier_type: str = "DownAndOut",
    barrier_level: float = 90.0,
    rebate: float = 0.0,
    option_type: str = "call"
) -> Dict[str, Any]:
    """
    定价障碍期权
    
    :param spot: 标的资产当前价格
    :param strike: 期权行权价
    :param volatility: 资产波动率（小数）
    :param risk_free_rate: 无风险利率（小数）
    :param dividend_yield: 资产股息率（小数）
    :param maturity_date: 期权到期日期 (YYYY-MM-DD)
    :param settlement_date: 计算结算日期 (YYYY-MM-DD)
    :param barrier_type: 障碍类型 ('UpAndOut', 'UpAndIn', 'DownAndOut', 'DownAndIn')
    :param barrier_level: 障碍价格水平
    :param rebate: 障碍触发后的补偿
    :param option_type: 期权类型
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

        # 障碍类型
        barrier_type_map = {
            "UpAndOut": ql.Barrier.UpOut,
            "UpAndIn": ql.Barrier.UpIn,
            "DownAndOut": ql.Barrier.DownOut,
            "DownAndIn": ql.Barrier.DownIn
        }
        barrier_enum = barrier_type_map.get(barrier_type, ql.Barrier.DownOut)

        # 创建障碍期权
        option = ql.BarrierOption(
            barrier_enum,
            barrier_level,
            rebate,
            payoff,
            exercise
        )

        # 市场数据
        spot_handle = ql.QuoteHandle(ql.SimpleQuote(spot))
        day_count = ql.Actual365Fixed()
        calendar = ql.NullCalendar()

        r_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(risk_free_rate)), day_count)
        )
        d_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(dividend_yield)), day_count)
        )
        vol_ts = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(eval_date, calendar, ql.QuoteHandle(ql.SimpleQuote(volatility)), day_count)
        )

        bsm_process = ql.BlackScholesMertonProcess(spot_handle, d_ts, r_ts, vol_ts)
        
        # 定价引擎
        engine = ql.AnalyticBarrierEngine(bsm_process)
        option.setPricingEngine(engine)

        return {
            "npv": option.NPV(),
            "delta": option.delta(),
            "gamma": option.gamma(),
            "vega": option.vega(),
            "theta": option.theta(),
            "rho": option.rho()
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_asian_option(
    spot: float,
    strike: float,
    volatility: float,
    risk_free_rate: float,
    dividend_yield: float,
    maturity_date: str,
    settlement_date: str,
    averaging_type: str = "Arithmetic",
    option_type: str = "call",
    number_of_fixings: int = 12
) -> Dict[str, Any]:
    """
    定价亚式期权（收益依赖于标的资产的平均价格）
    
    :param spot: 标的资产当前价格
    :param strike: 期权行权价
    :param volatility: 资产波动率（小数）
    :param risk_free_rate: 无风险利率（小数）
    :param dividend_yield: 资产股息率（小数）
    :param maturity_date: 期权到期日期 (YYYY-MM-DD)
    :param settlement_date: 计算结算日期 (YYYY-MM-DD)
    :param averaging_type: 平均类型 ('Arithmetic', 'Geometric')
    :param option_type: 期权类型
    :param number_of_fixings: 定价点数量
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

        # 平均类型
        if averaging_type == "Geometric":
            average_type = ql.Average.Geometric
        else:
            average_type = ql.Average.Arithmetic

        # 创建亚式期权
        option = ql.ContinuousAveragingAsianOption(average_type, payoff, mat_date)

        # 市场数据
        spot_handle = ql.QuoteHandle(ql.SimpleQuote(spot))
        day_count = ql.Actual365Fixed()
        calendar = ql.NullCalendar()

        r_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(risk_free_rate)), day_count)
        )
        d_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(dividend_yield)), day_count)
        )
        vol_ts = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(eval_date, calendar, ql.QuoteHandle(ql.SimpleQuote(volatility)), day_count)
        )

        bsm_process = ql.BlackScholesMertonProcess(spot_handle, d_ts, r_ts, vol_ts)
        
        # 定价引擎（Turnbull-Wakeman 方法）
        engine = ql.TurnbullWakemanAsianEngine(bsm_process)
        option.setPricingEngine(engine)

        return {
            "npv": option.NPV(),
            "delta": option.delta(),
            "gamma": option.gamma(),
            "vega": option.vega(),
            "theta": option.theta(),
            "rho": option.rho()
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_binary_option(
    spot: float,
    strike: float,
    volatility: float,
    risk_free_rate: float,
    dividend_yield: float,
    maturity_date: str,
    settlement_date: str,
    cash_payoff: float = 1.0,
    option_type: str = "call"
) -> Dict[str, Any]:
    """
    定价二元期权（固定收益期权）
    
    :param spot: 标的资产当前价格
    :param strike: 期权行权价
    :param volatility: 资产波动率（小数）
    :param risk_free_rate: 无风险利率（小数）
    :param dividend_yield: 资产股息率（小数）
    :param maturity_date: 期权到期日期 (YYYY-MM-DD)
    :param settlement_date: 计算结算日期 (YYYY-MM-DD)
    :param cash_payoff: 固定现金收益
    :param option_type: 期权类型
    """
    try:
        eval_date = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = eval_date

        mat_date = parse_date(maturity_date)
        if option_type.lower() == "call":
            payoff_type = ql.Option.Call
        else:
            payoff_type = ql.Option.Put

        payoff = ql.CashOrNothingPayoff(payoff_type, strike, cash_payoff)
        exercise = ql.EuropeanExercise(mat_date)
        option = ql.VanillaOption(payoff, exercise)

        # 市场数据
        spot_handle = ql.QuoteHandle(ql.SimpleQuote(spot))
        day_count = ql.Actual365Fixed()
        calendar = ql.NullCalendar()

        r_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(risk_free_rate)), day_count)
        )
        d_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(dividend_yield)), day_count)
        )
        vol_ts = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(eval_date, calendar, ql.QuoteHandle(ql.SimpleQuote(volatility)), day_count)
        )

        bsm_process = ql.BlackScholesMertonProcess(spot_handle, d_ts, r_ts, vol_ts)
        
        # 定价引擎
        engine = ql.AnalyticEuropeanEngine(bsm_process)
        option.setPricingEngine(engine)

        return {
            "npv": option.NPV(),
            "delta": option.delta(),
            "gamma": option.gamma(),
            "vega": option.vega(),
            "theta": option.theta(),
            "rho": option.rho()
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_double_barrier_option(
    spot: float,
    strike: float,
    volatility: float,
    risk_free_rate: float,
    dividend_yield: float,
    maturity_date: str,
    settlement_date: str,
    barrier_type: str = "KnockOut",
    lower_barrier: float = 90.0,
    upper_barrier: float = 110.0,
    rebate: float = 0.0,
    option_type: str = "call"
) -> Dict[str, Any]:
    """
    定价双障碍期权
    
    :param spot: 标的资产当前价格
    :param strike: 期权行权价
    :param volatility: 资产波动率（小数）
    :param risk_free_rate: 无风险利率（小数）
    :param dividend_yield: 资产股息率（小数）
    :param maturity_date: 期权到期日期 (YYYY-MM-DD)
    :param settlement_date: 计算结算日期 (YYYY-MM-DD)
    :param barrier_type: 障碍类型 ('KnockOut', 'KnockIn')
    :param lower_barrier: 下障碍价格
    :param upper_barrier: 上障碍价格
    :param rebate: 障碍触发后的补偿
    :param option_type: 期权类型
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

        # 双障碍类型
        if barrier_type == "KnockIn":
            barrier_enum = ql.DoubleBarrier.KnockIn
        else:
            barrier_enum = ql.DoubleBarrier.KnockOut

        # 创建双障碍期权
        option = ql.DoubleBarrierOption(
            barrier_enum,
            lower_barrier,
            upper_barrier,
            rebate,
            payoff,
            exercise
        )

        # 市场数据
        spot_handle = ql.QuoteHandle(ql.SimpleQuote(spot))
        day_count = ql.Actual365Fixed()
        calendar = ql.NullCalendar()

        r_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(risk_free_rate)), day_count)
        )
        d_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(dividend_yield)), day_count)
        )
        vol_ts = ql.BlackVolTermStructureHandle(
            ql.BlackConstantVol(eval_date, calendar, ql.QuoteHandle(ql.SimpleQuote(volatility)), day_count)
        )

        bsm_process = ql.BlackScholesMertonProcess(spot_handle, d_ts, r_ts, vol_ts)
        
        # 定价引擎
        engine = ql.AnalyticDoubleBarrierEngine(bsm_process)
        option.setPricingEngine(engine)

        return {
            "npv": option.NPV(),
            "delta": option.delta(),
            "gamma": option.gamma(),
            "vega": option.vega(),
            "theta": option.theta(),
            "rho": option.rho()
        }
    except Exception as e:
        return {"error": str(e)}
