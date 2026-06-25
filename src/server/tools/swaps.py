"""
互换类 MCP 工具
包含： vanilla 互换、浮动浮动互换、隔夜指数互换、零息互换等
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
        mcp = FastMCP("QuantLib Swaps")


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
    return freq_map.get(freq, ql.Semiannual)


def get_day_counter(day_count_convention: str) -> ql.DayCounter:
    """获取日期计数惯例"""
    if day_count_convention == "Actual365Fixed":
        return ql.Actual365Fixed()
    elif day_count_convention == "Actual360":
        return ql.Actual360()
    elif day_count_convention == "Thirty360":
        return ql.Thirty360(ql.Thirty360.USA)
    elif day_count_convention == "ActualActual":
        return ql.ActualActual(ql.ActualActual.ISDA)
    else:
        return ql.Thirty360(ql.Thirty360.USA)


@mcp.tool()
def price_vanilla_swap(
    settlement_date: str,
    maturity_date: str,
    fixed_rate: float,
    floating_spread: float = 0.0,
    nominal: float = 10_000_000.0,
    fixed_leg_frequency: int = 1,
    floating_leg_frequency: int = 2,
    yield_rate: float = 0.04,
    swap_type: str = "Payer",
    day_count_convention: str = "Thirty360",
    calendar_type: str = "TARGET"
) -> Dict[str, Any]:
    """
    定价普通固定对浮动利率互换
    
    :param settlement_date: 估值/生效日期 (YYYY-MM-DD)
    :param maturity_date: 互换到期日期 (YYYY-MM-DD)
    :param fixed_rate: 固定端票息率（小数）
    :param floating_spread: 浮动端利差（小数）
    :param nominal: 名义本金
    :param fixed_leg_frequency: 固定端付息频率 (1=年, 2=半年, 4=季)
    :param floating_leg_frequency: 浮动端付息频率
    :param yield_rate: 市场参考/贴现率（小数）
    :param swap_type: 互换类型 ('Payer', 'Receiver')
    :param day_count_convention: 日期计数惯例
    :param calendar_type: 日历类型 ('TARGET', 'USGovernmentBond')
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
        
        day_counter = get_day_counter(day_count_convention)

        # 生成付息计划
        fixed_schedule = ql.Schedule(
            settle_d, mat_d, ql.Period(get_frequency_enum(fixed_leg_frequency)), calendar,
            ql.ModifiedFollowing, ql.ModifiedFollowing, ql.DateGeneration.Forward, False
        )
        floating_schedule = ql.Schedule(
            settle_d, mat_d, ql.Period(get_frequency_enum(floating_leg_frequency)), calendar,
            ql.ModifiedFollowing, ql.ModifiedFollowing, ql.DateGeneration.Forward, False
        )

        # 指数和期限结构
        discount_curve = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(yield_rate)), day_counter)
        )
        index = ql.Euribor(ql.Period(get_frequency_enum(floating_leg_frequency)), discount_curve)

        # 创建互换
        if swap_type.lower() == "payer":
            swap_type_enum = ql.VanillaSwap.Payer
        else:
            swap_type_enum = ql.VanillaSwap.Receiver

        swap = ql.VanillaSwap(
            swap_type_enum,
            nominal,
            fixed_schedule,
            fixed_rate,
            day_counter,
            floating_schedule,
            index,
            floating_spread,
            day_counter
        )

        # 定价引擎
        engine = ql.DiscountingSwapEngine(discount_curve)
        swap.setPricingEngine(engine)

        # 现金流分析
        fixed_leg_cf = []
        for cf in swap.fixedLeg():
            if hasattr(cf, 'amount'):
                fixed_leg_cf.append({
                    "date": cf.date().to_datetime().strftime("%Y-%m-%d"),
                    "amount": cf.amount()
                })

        floating_leg_cf = []
        for cf in swap.floatingLeg():
            if hasattr(cf, 'amount'):
                floating_leg_cf.append({
                    "date": cf.date().to_datetime().strftime("%Y-%m-%d"),
                    "amount": cf.amount()
                })

        return {
            "npv": swap.NPV(),
            "fair_rate": swap.fairRate(),
            "fair_spread": swap.fairSpread(),
            "fixed_leg_npv": swap.fixedLegNPV(),
            "floating_leg_npv": swap.floatingLegNPV(),
            "fixed_leg_cashflows": fixed_leg_cf,
            "floating_leg_cashflows": floating_leg_cf
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_float_float_swap(
    settlement_date: str,
    maturity_date: str,
    spread: float = 0.0,
    nominal: float = 10_000_000.0,
    leg1_frequency: int = 4,
    leg2_frequency: int = 4,
    leg1_index_type: str = "Euribor3M",
    leg2_index_type: str = "Euribor6M",
    yield_rate: float = 0.04,
    swap_type: str = "Payer"
) -> Dict[str, Any]:
    """
    定价浮动对浮动利率互换
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param spread: 利差（小数）
    :param nominal: 名义本金
    :param leg1_frequency: 第一端频率 (1=年, 2=半年, 4=季)
    :param leg2_frequency: 第二端频率
    :param leg1_index_type: 第一端指数类型
    :param leg2_index_type: 第二端指数类型
    :param yield_rate: 贴现率（小数）
    :param swap_type: 互换类型
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.TARGET()
        day_counter = ql.Actual360()

        # 贴现曲线
        discount_curve = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(yield_rate)), day_counter)
        )

        # 创建指数
        index1 = ql.Euribor(ql.Period(get_frequency_enum(leg1_frequency)), discount_curve)
        index2 = ql.Euribor(ql.Period(get_frequency_enum(leg2_frequency)), discount_curve)

        # 付息计划
        schedule1 = ql.Schedule(
            settle_d, mat_d, ql.Period(get_frequency_enum(leg1_frequency)), calendar,
            ql.ModifiedFollowing, ql.ModifiedFollowing, ql.DateGeneration.Forward, False
        )
        schedule2 = ql.Schedule(
            settle_d, mat_d, ql.Period(get_frequency_enum(leg2_frequency)), calendar,
            ql.ModifiedFollowing, ql.ModifiedFollowing, ql.DateGeneration.Forward, False
        )

        # 创建浮动对浮动互换
        if swap_type.lower() == "payer":
            swap_type_enum = ql.FloatFloatSwap.Payer
        else:
            swap_type_enum = ql.FloatFloatSwap.Receiver

        swap = ql.FloatFloatSwap(
            swap_type_enum,
            nominal,
            schedule1,
            index1,
            day_counter,
            schedule2,
            index2,
            day_counter,
            spread
        )

        # 定价引擎
        engine = ql.DiscountingSwapEngine(discount_curve)
        swap.setPricingEngine(engine)

        return {
            "npv": swap.NPV(),
            "fair_spread": swap.fairSpread(),
            "leg1_npv": swap.legNPV(0),
            "leg2_npv": swap.legNPV(1)
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_overnight_indexed_swap(
    settlement_date: str,
    maturity_date: str,
    fixed_rate: float,
    nominal: float = 10_000_000.0,
    fixed_leg_frequency: int = 1,
    yield_rate: float = 0.04,
    overnight_index_type: str = "EONIA",
    swap_type: str = "Payer"
) -> Dict[str, Any]:
    """
    定价隔夜指数互换 (OIS)
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param fixed_rate: 固定端利率（小数）
    :param nominal: 名义本金
    :param fixed_leg_frequency: 固定端付息频率
    :param yield_rate: 市场参考利率（小数）
    :param overnight_index_type: 隔夜指数类型 ('EONIA', 'FEDFUNDS', 'SOFR')
    :param swap_type: 互换类型
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.TARGET()
        day_counter = ql.Actual360()

        # 贴现曲线
        discount_curve = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(yield_rate)), day_counter)
        )

        # 隔夜指数
        if overnight_index_type.upper() == "SOFR":
            overnight_index = ql.Sofr()
        elif overnight_index_type.upper() == "FEDFUNDS":
            overnight_index = ql.FedFunds()
        else:
            overnight_index = ql.Eonia()

        # 付息计划
        fixed_schedule = ql.Schedule(
            settle_d, mat_d, ql.Period(get_frequency_enum(fixed_leg_frequency)), calendar,
            ql.ModifiedFollowing, ql.ModifiedFollowing, ql.DateGeneration.Forward, False
        )

        # 创建 OIS
        if swap_type.lower() == "payer":
            swap_type_enum = ql.OvernightIndexedSwap.Payer
        else:
            swap_type_enum = ql.OvernightIndexedSwap.Receiver

        swap = ql.OvernightIndexedSwap(
            swap_type_enum,
            nominal,
            fixed_schedule,
            fixed_rate,
            day_counter,
            overnight_index
        )

        # 定价引擎
        engine = ql.DiscountingSwapEngine(discount_curve)
        swap.setPricingEngine(engine)

        return {
            "npv": swap.NPV(),
            "fair_rate": swap.fairRate(),
            "fixed_leg_npv": swap.fixedLegNPV(),
            "overnight_leg_npv": swap.overnightLegNPV()
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_zero_coupon_swap(
    settlement_date: str,
    maturity_date: str,
    fixed_rate: float,
    nominal: float = 10_000_000.0,
    floating_spread: float = 0.0,
    floating_leg_frequency: int = 4,
    yield_rate: float = 0.04,
    swap_type: str = "Payer"
) -> Dict[str, Any]:
    """
    定价零息互换
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param fixed_rate: 固定端利率（小数）
    :param nominal: 名义本金
    :param floating_spread: 浮动端利差（小数）
    :param floating_leg_frequency: 浮动端频率
    :param yield_rate: 贴现率（小数）
    :param swap_type: 互换类型
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.TARGET()
        day_counter = ql.Actual360()

        # 贴现曲线
        discount_curve = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(yield_rate)), day_counter)
        )

        # 指数
        index = ql.Euribor(ql.Period(get_frequency_enum(floating_leg_frequency)), discount_curve)

        # 付息计划（固定端只有到期日支付）
        fixed_schedule = ql.Schedule(
            settle_d, mat_d, ql.Period(ql.Once), calendar,
            ql.ModifiedFollowing, ql.ModifiedFollowing, ql.DateGeneration.Forward, False
        )
        floating_schedule = ql.Schedule(
            settle_d, mat_d, ql.Period(get_frequency_enum(floating_leg_frequency)), calendar,
            ql.ModifiedFollowing, ql.ModifiedFollowing, ql.DateGeneration.Forward, False
        )

        # 创建零息互换
        swap = ql.ZeroCouponSwap(
            ql.ZeroCouponSwap.Payer if swap_type.lower() == "payer" else ql.ZeroCouponSwap.Receiver,
            nominal,
            fixed_schedule,
            fixed_rate,
            day_counter,
            floating_schedule,
            index,
            floating_spread
        )

        # 定价引擎
        engine = ql.DiscountingSwapEngine(discount_curve)
        swap.setPricingEngine(engine)

        return {
            "npv": swap.NPV(),
            "fair_rate": swap.fairRate(),
            "fair_spread": swap.fairSpread()
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_basis_swap(
    settlement_date: str,
    maturity_date: str,
    spread: float = 0.0,
    nominal: float = 10_000_000.0,
    leg1_frequency: int = 3,
    leg2_frequency: int = 6,
    yield_rate: float = 0.04,
    swap_type: str = "Payer"
) -> Dict[str, Any]:
    """
    定价基差互换（浮动对浮动，不同期限）
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param spread: 利差（小数）
    :param nominal: 名义本金
    :param leg1_frequency: 第一端频率 (月数，如 3=3M, 6=6M)
    :param leg2_frequency: 第二端频率
    :param yield_rate: 贴现率（小数）
    :param swap_type: 互换类型
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.TARGET()
        day_counter = ql.Actual360()

        # 贴现曲线
        discount_curve = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(yield_rate)), day_counter)
        )

        # 创建不同期限的指数
        index1 = ql.Euribor(ql.Period(leg1_frequency, ql.Months), discount_curve)
        index2 = ql.Euribor(ql.Period(leg2_frequency, ql.Months), discount_curve)

        # 付息计划
        schedule1 = ql.Schedule(
            settle_d, mat_d, ql.Period(leg1_frequency, ql.Months), calendar,
            ql.ModifiedFollowing, ql.ModifiedFollowing, ql.DateGeneration.Forward, False
        )
        schedule2 = ql.Schedule(
            settle_d, mat_d, ql.Period(leg2_frequency, ql.Months), calendar,
            ql.ModifiedFollowing, ql.ModifiedFollowing, ql.DateGeneration.Forward, False
        )

        # 使用普通互换来模拟基差互换
        # 固定端使用第一端的指数，浮动端使用第二端的指数加利差
        swap = ql.VanillaSwap(
            ql.VanillaSwap.Payer if swap_type.lower() == "payer" else ql.VanillaSwap.Receiver,
            nominal,
            schedule1,
            0.0,  # 固定端利率为 0
            day_counter,
            schedule2,
            index2,
            spread,
            day_counter
        )

        # 定价引擎
        engine = ql.DiscountingSwapEngine(discount_curve)
        swap.setPricingEngine(engine)

        return {
            "npv": swap.NPV(),
            "fair_spread": swap.fairSpread(),
            "fixed_leg_npv": swap.fixedLegNPV(),
            "floating_leg_npv": swap.floatingLegNPV()
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def create_swap_schedule(
    settlement_date: str,
    maturity_date: str,
    frequency: int = 2,
    calendar_type: str = "TARGET",
    date_generation_rule: str = "Forward",
    end_of_month: bool = False
) -> Dict[str, Any]:
    """
    创建互换付息计划
    
    :param settlement_date: 起始日期 (YYYY-MM-DD)
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param frequency: 付息频率
    :param calendar_type: 日历类型
    :param date_generation_rule: 日期生成规则 ('Forward', 'Backward', 'Zero')
    :param end_of_month: 是否使用月末规则
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)

        # 日历
        if calendar_type == "USGovernmentBond":
            calendar = ql.UnitedStates(ql.UnitedStates.GovernmentBond)
        else:
            calendar = ql.TARGET()

        # 日期生成规则
        if date_generation_rule == "Backward":
            rule = ql.DateGeneration.Backward
        elif date_generation_rule == "Zero":
            rule = ql.DateGeneration.Zero
        else:
            rule = ql.DateGeneration.Forward

        # 创建计划
        schedule = ql.Schedule(
            settle_d,
            mat_d,
            ql.Period(get_frequency_enum(frequency)),
            calendar,
            ql.ModifiedFollowing,
            ql.ModifiedFollowing,
            rule,
            end_of_month
        )

        # 提取日期
        dates = []
        for i, date in enumerate(schedule):
            dates.append({
                "index": i,
                "date": date.to_datetime().strftime("%Y-%m-%d"),
                "is_regular": schedule.isRegular(i + 1)
            })

        return {
            "number_of_dates": len(dates),
            "tenor": schedule.tenor(),
            "dates": dates
        }
    except Exception as e:
        return {"error": str(e)}
