"""
波动率类 MCP 工具
包含：利率上限期权 (Cap)、利率下限期权 (Floor)、互换期权 (Swaption)
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
        mcp = FastMCP("QuantLib Volatility")


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
    else:
        return ql.Actual360()


@mcp.tool()
def price_cap(
    settlement_date: str,
    maturity_date: str,
    strike_rates: List[float],
    yield_rate: float,
    volatility: float,
    nominal: float = 10_000_000.0,
    frequency: int = 4,
    day_count_convention: str = "Actual360",
    engine_type: str = "Black"
) -> Dict[str, Any]:
    """
    定价利率上限期权 (Cap)
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param strike_rates: 行权利率列表（小数）
    :param yield_rate: 市场参考利率（小数）
    :param volatility: 波动率（小数）
    :param nominal: 名义本金
    :param frequency: 付息频率
    :param day_count_convention: 日期计数惯例
    :param engine_type: 定价引擎类型 ('Black', 'Bachelier')
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.TARGET()
        day_counter = get_day_counter(day_count_convention)

        # 贴现曲线
        discount_curve = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(yield_rate)), day_counter)
        )

        # Ibor 指数
        index = ql.Euribor(ql.Period(get_frequency_enum(frequency)), discount_curve)

        # 付息计划
        schedule = ql.Schedule(
            settle_d,
            mat_d,
            ql.Period(get_frequency_enum(frequency)),
            calendar,
            ql.ModifiedFollowing,
            ql.ModifiedFollowing,
            ql.DateGeneration.Forward,
            False
        )

        # 创建 Cap
        cap = ql.Cap(schedule, strike_rates, index)

        # 波动率
        vol_handle = ql.QuoteHandle(ql.SimpleQuote(volatility))

        # 定价引擎
        if engine_type == "Bachelier":
            engine = ql.BachelierCapFloorEngine(index, vol_handle)
        else:
            engine = ql.BlackCapFloorEngine(index, vol_handle)
        
        cap.setPricingEngine(engine)

        # 现金流分析
        cashflows = []
        for i, cf in enumerate(cap.leg):
            if hasattr(cf, 'amount'):
                cashflows.append({
                    "period": i + 1,
                    "date": cf.date().to_datetime().strftime("%Y-%m-%d"),
                    "amount": cf.amount()
                })

        return {
            "npv": cap.NPV(),
            "value": cap.NPV(),
            "cashflows": cashflows
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_floor(
    settlement_date: str,
    maturity_date: str,
    strike_rates: List[float],
    yield_rate: float,
    volatility: float,
    nominal: float = 10_000_000.0,
    frequency: int = 4,
    day_count_convention: str = "Actual360",
    engine_type: str = "Black"
) -> Dict[str, Any]:
    """
    定价利率下限期权 (Floor)
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param strike_rates: 行权利率列表（小数）
    :param yield_rate: 市场参考利率（小数）
    :param volatility: 波动率（小数）
    :param nominal: 名义本金
    :param frequency: 付息频率
    :param day_count_convention: 日期计数惯例
    :param engine_type: 定价引擎类型 ('Black', 'Bachelier')
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.TARGET()
        day_counter = get_day_counter(day_count_convention)

        # 贴现曲线
        discount_curve = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(yield_rate)), day_counter)
        )

        # Ibor 指数
        index = ql.Euribor(ql.Period(get_frequency_enum(frequency)), discount_curve)

        # 付息计划
        schedule = ql.Schedule(
            settle_d,
            mat_d,
            ql.Period(get_frequency_enum(frequency)),
            calendar,
            ql.ModifiedFollowing,
            ql.ModifiedFollowing,
            ql.DateGeneration.Forward,
            False
        )

        # 创建 Floor
        floor = ql.Floor(schedule, strike_rates, index)

        # 波动率
        vol_handle = ql.QuoteHandle(ql.SimpleQuote(volatility))

        # 定价引擎
        if engine_type == "Bachelier":
            engine = ql.BachelierCapFloorEngine(index, vol_handle)
        else:
            engine = ql.BlackCapFloorEngine(index, vol_handle)
        
        floor.setPricingEngine(engine)

        # 现金流分析
        cashflows = []
        for i, cf in enumerate(floor.leg):
            if hasattr(cf, 'amount'):
                cashflows.append({
                    "period": i + 1,
                    "date": cf.date().to_datetime().strftime("%Y-%m-%d"),
                    "amount": cf.amount()
                })

        return {
            "npv": floor.NPV(),
            "value": floor.NPV(),
            "cashflows": cashflows
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_cap_floor_strip(
    settlement_date: str,
    maturity_date: str,
    cap_strikes: List[float],
    floor_strikes: List[float],
    yield_rate: float,
    cap_volatilities: List[float],
    floor_volatilities: List[float],
    frequency: int = 4,
    day_count_convention: str = "Actual360"
) -> Dict[str, Any]:
    """
    对 Cap 和 Floor 进行条带定价
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param cap_strikes: Cap 行权利率列表
    :param floor_strikes: Floor 行权利率列表
    :param yield_rate: 市场参考利率（小数）
    :param cap_volatilities: Cap 波动率列表
    :param floor_volatilities: Floor 波动率列表
    :param frequency: 付息频率
    :param day_count_convention: 日期计数惯例
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.TARGET()
        day_counter = get_day_counter(day_count_convention)

        # 贴现曲线
        discount_curve = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(yield_rate)), day_counter)
        )

        # Ibor 指数
        index = ql.Euribor(ql.Period(get_frequency_enum(frequency)), discount_curve)

        # 付息计划
        schedule = ql.Schedule(
            settle_d,
            mat_d,
            ql.Period(get_frequency_enum(frequency)),
            calendar,
            ql.ModifiedFollowing,
            ql.ModifiedFollowing,
            ql.DateGeneration.Forward,
            False
        )

        # Cap 定价
        cap_results = []
        for i, (strike, vol) in enumerate(zip(cap_strikes, cap_volatilities)):
            cap = ql.Cap(schedule, [strike], index)
            vol_handle = ql.QuoteHandle(ql.SimpleQuote(vol))
            engine = ql.BlackCapFloorEngine(index, vol_handle)
            cap.setPricingEngine(engine)
            cap_results.append({
                "strike": strike,
                "volatility": vol,
                "npv": cap.NPV()
            })

        # Floor 定价
        floor_results = []
        for i, (strike, vol) in enumerate(zip(floor_strikes, floor_volatilities)):
            floor = ql.Floor(schedule, [strike], index)
            vol_handle = ql.QuoteHandle(ql.SimpleQuote(vol))
            engine = ql.BlackCapFloorEngine(index, vol_handle)
            floor.setPricingEngine(engine)
            floor_results.append({
                "strike": strike,
                "volatility": vol,
                "npv": floor.NPV()
            })

        return {
            "cap_results": cap_results,
            "floor_results": floor_results
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_swaption(
    settlement_date: str,
    swaption_maturity: str,
    swap_tenor_years: int,
    strike_rate: float,
    volatility: float,
    nominal: float = 10_000_000.0,
    fixed_leg_frequency: int = 1,
    floating_leg_frequency: int = 2,
    yield_rate: float = 0.04,
    swaption_type: str = "Call",
    exercise_type: str = "European",
    day_count_convention: str = "Thirty360"
) -> Dict[str, Any]:
    """
    定价互换期权 (Swaption)
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param swaption_maturity: 互换期权到期日期 (YYYY-MM-DD)
    :param swap_tenor_years: 基础互换期限（年）
    :param strike_rate: 行权利率（小数）
    :param volatility: 波动率（小数）
    :param nominal: 名义本金
    :param fixed_leg_frequency: 固定端付息频率
    :param floating_leg_frequency: 浮动端付息频率
    :param yield_rate: 市场参考利率（小数）
    :param swaption_type: 期权类型 ('Call', 'Put')
    :param exercise_type: 行权类型 ('European', 'Bermudan')
    :param day_count_convention: 日期计数惯例
    """
    try:
        settle_d = parse_date(settlement_date)
        maturity_d = parse_date(swaption_maturity)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.TARGET()
        day_counter = get_day_counter(day_count_convention)

        # 贴现曲线
        discount_curve = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(yield_rate)), day_counter)
        )

        # 互换指数
        index = ql.Euribor(ql.Period(get_frequency_enum(floating_leg_frequency)), discount_curve)

        # 互换到期日
        swap_maturity = maturity_d + ql.Period(swap_tenor_years, ql.Years)

        # 付息计划
        fixed_schedule = ql.Schedule(
            maturity_d,
            swap_maturity,
            ql.Period(get_frequency_enum(fixed_leg_frequency)),
            calendar,
            ql.ModifiedFollowing,
            ql.ModifiedFollowing,
            ql.DateGeneration.Forward,
            False
        )
        floating_schedule = ql.Schedule(
            maturity_d,
            swap_maturity,
            ql.Period(get_frequency_enum(floating_leg_frequency)),
            calendar,
            ql.ModifiedFollowing,
            ql.ModifiedFollowing,
            ql.DateGeneration.Forward,
            False
        )

        # 基础互换
        underlying_swap = ql.VanillaSwap(
            ql.VanillaSwap.Payer,
            nominal,
            fixed_schedule,
            strike_rate,
            day_counter,
            floating_schedule,
            index,
            0.0,
            day_counter
        )

        # 互换期权
        if exercise_type == "European":
            exercise = ql.EuropeanExercise(maturity_d)
            swaption = ql.Swaption(underlying_swap, exercise)
            
            # 波动率
            vol_handle = ql.QuoteHandle(ql.SimpleQuote(volatility))
            swaption_vol = ql.ConstantSwaptionVolatility(
                settle_d,
                calendar,
                ql.ModifiedFollowing,
                vol_handle
            )
            
            # 定价引擎
            engine = ql.BlackSwaptionEngine(swaption_vol, discount_curve)
            swaption.setPricingEngine(engine)
        else:
            return {"error": "Bermudan swaption not implemented in this version"}

        return {
            "npv": swaption.NPV(),
            "value": swaption.NPV(),
            "implied_volatility": swaption.impliedVolatility(
                swaption.NPV(),
                ql.ConstantSwaptionVolatility(
                    settle_d,
                    calendar,
                    ql.ModifiedFollowing,
                    ql.QuoteHandle(ql.SimpleQuote(volatility))
                ),
                discount_curve,
                1e-6,
                1000,
                0.01,
                1.0
            ) if swaption.NPV() > 0 else 0.0
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_swaption_volatility_surface(
    settlement_date: str,
    option_tenors: List[str],
    swap_tenors: List[str],
    volatilities: List[List[float]],
    yield_rate: float,
    strike_rate: float = 0.04,
    nominal: float = 10_000_000.0,
    frequency: int = 2
) -> Dict[str, Any]:
    """
    使用波动率曲面定价互换期权
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param option_tenors: 期权期限列表（如 ['1Y', '2Y', '5Y']）
    :param swap_tenors: 互换期限列表（如 ['5Y', '10Y']）
    :param volatilities: 波动率矩阵
    :param yield_rate: 市场参考利率（小数）
    :param strike_rate: 行权利率（小数）
    :param nominal: 名义本金
    :param frequency: 付息频率
    """
    try:
        settle_d = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.TARGET()
        day_counter = ql.Thirty360(ql.Thirty360.USA)

        # 贴现曲线
        discount_curve = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(yield_rate)), day_counter)
        )

        # 构建期权期限日期
        option_dates = []
        for tenor in option_tenors:
            val = int(tenor[:-1])
            unit = tenor[-1]
            if unit == 'Y':
                option_dates.append(settle_d + ql.Period(val, ql.Years))
            else:
                option_dates.append(settle_d + ql.Period(val, ql.Months))

        # 构建互换期限
        swap_periods = []
        for tenor in swap_tenors:
            val = int(tenor[:-1])
            unit = tenor[-1]
            if unit == 'Y':
                swap_periods.append(ql.Period(val, ql.Years))
            else:
                swap_periods.append(ql.Period(val, ql.Months))

        # 波动率曲面
        swaption_vol_surface = ql.SwaptionVolatilityMatrix(
            calendar,
            ql.ModifiedFollowing,
            option_dates,
            swap_periods,
            volatilities,
            ql.Actual365Fixed()
        )

        # 创建基础互换并定价
        index = ql.Euribor(ql.Period(get_frequency_enum(frequency)), discount_curve)
        
        # 示例：定价 ATM 互换期权（使用第一个期权期限和互换期限）
        maturity_d = option_dates[0]
        swap_maturity = maturity_d + swap_periods[0]

        fixed_schedule = ql.Schedule(
            maturity_d,
            swap_maturity,
            ql.Period(get_frequency_enum(frequency)),
            calendar,
            ql.ModifiedFollowing,
            ql.ModifiedFollowing,
            ql.DateGeneration.Forward,
            False
        )
        floating_schedule = ql.Schedule(
            maturity_d,
            swap_maturity,
            ql.Period(get_frequency_enum(frequency)),
            calendar,
            ql.ModifiedFollowing,
            ql.ModifiedFollowing,
            ql.DateGeneration.Forward,
            False
        )

        underlying_swap = ql.VanillaSwap(
            ql.VanillaSwap.Payer,
            nominal,
            fixed_schedule,
            strike_rate,
            day_counter,
            floating_schedule,
            index,
            0.0,
            day_counter
        )

        exercise = ql.EuropeanExercise(maturity_d)
        swaption = ql.Swaption(underlying_swap, exercise)

        engine = ql.BlackSwaptionEngine(swaption_vol_surface, discount_curve)
        swaption.setPricingEngine(engine)

        return {
            "npv": swaption.NPV(),
            "volatility_surface_dimensions": {
                "option_tenors": len(option_tenors),
                "swap_tenors": len(swap_tenors)
            }
        }
    except Exception as e:
        return {"error": str(e)}
