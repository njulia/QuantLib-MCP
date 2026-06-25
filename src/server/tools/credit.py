"""
信用类 MCP 工具
包含：信用违约互换 (CDS)、CDS 期权等
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
        mcp = FastMCP("QuantLib Credit")


def parse_date(date_str: str) -> ql.Date:
    """解析 ISO 日期字符串为 QuantLib.Date"""
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    return ql.Date(dt.day, dt.month, dt.year)


def get_frequency_enum(freq: int) -> ql.Frequency:
    """将整数频率转换为 QuantLib 频率枚举"""
    freq_map = {
        0: ql.Once,
        1: ql.Annual,
        2: ql.Semiannual,
        4: ql.Quarterly,
        6: ql.Bimonthly,
        12: ql.Monthly
    }
    return freq_map.get(freq, ql.Quarterly)


@mcp.tool()
def price_credit_default_swap(
    settlement_date: str,
    maturity_date: str,
    spread: float,
    recovery_rate: float,
    hazard_rate: float,
    notional: float = 10_000_000.0,
    frequency: int = 4,
    day_count_convention: str = "Actual360",
    calendar_type: str = "TARGET"
) -> Dict[str, Any]:
    """
    定价信用违约互换 (CDS)
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param spread: CDS 利差/保费（小数，如 0.01 表示 100bps）
    :param recovery_rate: 回收率（小数，如 0.40 表示 40%）
    :param hazard_rate: 违约强度/风险率（小数）
    :param notional: 名义本金
    :param frequency: 付费频率
    :param day_count_convention: 日期计数惯例
    :param calendar_type: 日历类型
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        ql.Settings.instance().evaluationDate = settle_d

        # 日历
        if calendar_type == "USGovernmentBond":
            calendar = ql.UnitedStates(ql.UnitedStates.GovernmentBond)
        else:
            calendar = ql.TARGET()
        
        # 日期计数
        if day_count_convention == "Actual365Fixed":
            day_counter = ql.Actual365Fixed()
        elif day_count_convention == "Thirty360":
            day_counter = ql.Thirty360(ql.Thirty360.USA)
        else:
            day_counter = ql.Actual360()

        # 违约曲线
        hazard_rates = ql.DefaultProbabilityTermStructureHandle(
            ql.FlatHazardRate(
                0,
                calendar,
                ql.QuoteHandle(ql.SimpleQuote(hazard_rate)),
                ql.Actual360()
            )
        )

        # 付费计划
        schedule = ql.Schedule(
            settle_d,
            mat_d,
            ql.Period(get_frequency_enum(frequency)),
            calendar,
            ql.Following,
            ql.Following,
            ql.DateGeneration.Forward,
            False
        )

        # 创建 CDS
        cds = ql.CreditDefaultSwap(
            ql.Protection.Buyer,
            notional,
            settle_d,
            mat_d,
            ql.Following,
            spread,
            schedule,
            ql.Following,
            True,
            day_counter,
            recovery_rate,
            ql.Actual360(),
            ql.Date(1, 1, 2025),  # 最后交付日期
            ql.CreditDefaultSwap.Physical,
            ql.CreditDefaultSwap.Actual
        )

        # 贴现曲线
        discount_curve = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(0.03)), day_counter)
        )

        # 定价引擎
        engine = ql.IsdaCdsEngine(hazard_rates, recovery_rate, discount_curve)
        cds.setPricingEngine(engine)

        return {
            "npv": cds.NPV(),
            "fair_spread": cds.fairSpread(),
            "default_leg_npv": cds.defaultLegNPV(),
            "premium_leg_npv": cds.premiumLegNPV(),
            "risky_pv01": cds.riskyPV01(),
            "hazard_rate": hazard_rate,
            "survival_probability": hazard_rates.survivalProbability(mat_d)
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_cds_with_term_structure(
    settlement_date: str,
    maturity_date: str,
    cds_spread: float,
    recovery_rate: float,
    hazard_rate_dates: List[str],
    hazard_rates: List[float],
    notional: float = 10_000_000.0,
    frequency: int = 4,
    yield_rate: float = 0.03
) -> Dict[str, Any]:
    """
    使用风险率期限结构定价 CDS
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param cds_spread: CDS 利差（小数）
    :param recovery_rate: 回收率（小数）
    :param hazard_rate_dates: 风险率日期列表
    :param hazard_rates: 风险率列表
    :param notional: 名义本金
    :param frequency: 付费频率
    :param yield_rate: 无风险利率（小数）
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.TARGET()
        day_counter = ql.Actual360()

        # 风险率日期
        dates = [parse_date(d) for d in hazard_rate_dates]
        
        # 插值风险率曲线
        hazard_curve = ql.InterpolatedHazardRateCurve(
            dates,
            hazard_rates,
            ql.Actual360(),
            calendar,
            ql.Linear()
        )
        hazard_rates_handle = ql.DefaultProbabilityTermStructureHandle(hazard_curve)

        # 付费计划
        schedule = ql.Schedule(
            settle_d,
            mat_d,
            ql.Period(get_frequency_enum(frequency)),
            calendar,
            ql.Following,
            ql.Following,
            ql.DateGeneration.Forward,
            False
        )

        # 贴现曲线
        discount_curve = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(yield_rate)), day_counter)
        )

        # 创建 CDS
        cds = ql.CreditDefaultSwap(
            ql.Protection.Buyer,
            notional,
            settle_d,
            mat_d,
            ql.Following,
            cds_spread,
            schedule,
            ql.Following,
            True,
            day_counter,
            recovery_rate,
            ql.Actual360(),
            ql.Date(1, 1, 2025),
            ql.CreditDefaultSwap.Physical,
            ql.CreditDefaultSwap.Actual
        )

        # 定价引擎
        engine = ql.IsdaCdsEngine(hazard_rates_handle, recovery_rate, discount_curve)
        cds.setPricingEngine(engine)

        # 生存概率
        survival_probs = []
        for d, h in zip(hazard_rate_dates, hazard_rates):
            date = parse_date(d)
            survival_probs.append({
                "date": d,
                "survival_probability": hazard_rates_handle.survivalProbability(date)
            })

        return {
            "npv": cds.NPV(),
            "fair_spread": cds.fairSpread(),
            "default_leg_npv": cds.defaultLegNPV(),
            "premium_leg_npv": cds.premiumLegNPV(),
            "survival_probabilities": survival_probs
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_cds_option(
    settlement_date: str,
    option_maturity: str,
    cds_maturity: str,
    strike_spread: float,
    recovery_rate: float,
    hazard_rate: float,
    volatility: float,
    notional: float = 10_000_000.0,
    frequency: int = 4,
    yield_rate: float = 0.03
) -> Dict[str, Any]:
    """
    定价 CDS 期权
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param option_maturity: 期权到期日期 (YYYY-MM-DD)
    :param cds_maturity: 基础 CDS 到期日期 (YYYY-MM-DD)
    :param strike_spread: 行权利差（小数）
    :param recovery_rate: 回收率（小数）
    :param hazard_rate: 违约强度（小数）
    :param volatility: 波动率（小数）
    :param notional: 名义本金
    :param frequency: 付费频率
    :param yield_rate: 无风险利率（小数）
    """
    try:
        settle_d = parse_date(settlement_date)
        option_d = parse_date(option_maturity)
        cds_d = parse_date(cds_maturity)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.TARGET()
        day_counter = ql.Actual360()

        # 违约曲线
        hazard_rates = ql.DefaultProbabilityTermStructureHandle(
            ql.FlatHazardRate(
                0,
                calendar,
                ql.QuoteHandle(ql.SimpleQuote(hazard_rate)),
                ql.Actual360()
            )
        )

        # 贴现曲线
        discount_curve = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(yield_rate)), day_counter)
        )

        # CDS 付费计划
        cds_schedule = ql.Schedule(
            option_d,
            cds_d,
            ql.Period(get_frequency_enum(frequency)),
            calendar,
            ql.Following,
            ql.Following,
            ql.DateGeneration.Forward,
            False
        )

        # 基础 CDS
        cds = ql.CreditDefaultSwap(
            ql.Protection.Buyer,
            notional,
            option_d,
            cds_d,
            ql.Following,
            strike_spread,
            cds_schedule,
            ql.Following,
            True,
            day_counter,
            recovery_rate,
            ql.Actual360(),
            ql.Date(1, 1, 2025),
            ql.CreditDefaultSwap.Physical,
            ql.CreditDefaultSwap.Actual
        )

        # CDS 期权
        cds_option = ql.CdsOption(cds, strike_spread, option_d)

        # 波动率
        vol_handle = ql.QuoteHandle(ql.SimpleQuote(volatility))

        # 定价引擎
        engine = ql.BlackCdsOptionEngine(hazard_rates, recovery_rate, discount_curve, vol_handle)
        cds_option.setPricingEngine(engine)

        return {
            "npv": cds_option.NPV(),
            "value": cds_option.NPV()
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def calculate_cds_fair_spread(
    settlement_date: str,
    maturity_date: str,
    recovery_rate: float,
    hazard_rate: float,
    notional: float = 10_000_000.0,
    frequency: int = 4,
    yield_rate: float = 0.03
) -> Dict[str, Any]:
    """
    计算 CDS 公平利差
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param recovery_rate: 回收率（小数）
    :param hazard_rate: 违约强度（小数）
    :param notional: 名义本金
    :param frequency: 付费频率
    :param yield_rate: 无风险利率（小数）
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.TARGET()
        day_counter = ql.Actual360()

        # 违约曲线
        hazard_rates = ql.DefaultProbabilityTermStructureHandle(
            ql.FlatHazardRate(
                0,
                calendar,
                ql.QuoteHandle(ql.SimpleQuote(hazard_rate)),
                ql.Actual360()
            )
        )

        # 贴现曲线
        discount_curve = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(yield_rate)), day_counter)
        )

        # 使用临时利差创建 CDS 以计算公平利差
        temp_spread = 0.01
        schedule = ql.Schedule(
            settle_d,
            mat_d,
            ql.Period(get_frequency_enum(frequency)),
            calendar,
            ql.Following,
            ql.Following,
            ql.DateGeneration.Forward,
            False
        )

        cds = ql.CreditDefaultSwap(
            ql.Protection.Buyer,
            notional,
            settle_d,
            mat_d,
            ql.Following,
            temp_spread,
            schedule,
            ql.Following,
            True,
            day_counter,
            recovery_rate,
            ql.Actual360(),
            ql.Date(1, 1, 2025),
            ql.CreditDefaultSwap.Physical,
            ql.CreditDefaultSwap.Actual
        )

        # 定价引擎
        engine = ql.IsdaCdsEngine(hazard_rates, recovery_rate, discount_curve)
        cds.setPricingEngine(engine)

        # 公平利差
        fair_spread = cds.fairSpread()
        
        # 计算 PV01
        cds_with_zero_spread = ql.CreditDefaultSwap(
            ql.Protection.Buyer,
            notional,
            settle_d,
            mat_d,
            ql.Following,
            0.0,
            schedule,
            ql.Following,
            True,
            day_counter,
            recovery_rate,
            ql.Actual360(),
            ql.Date(1, 1, 2025),
            ql.CreditDefaultSwap.Physical,
            ql.CreditDefaultSwap.Actual
        )
        cds_with_zero_spread.setPricingEngine(engine)
        pv01 = cds_with_zero_spread.riskyPV01()

        return {
            "fair_spread": fair_spread,
            "fair_spread_bps": fair_spread * 10000,
            "risky_pv01": pv01,
            "hazard_rate": hazard_rate,
            "survival_probability": hazard_rates.survivalProbability(mat_d)
        }
    except Exception as e:
        return {"error": str(e)}
