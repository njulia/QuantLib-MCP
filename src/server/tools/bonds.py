"""
债券类 MCP 工具
包含：固定利率债券、浮动利率债券、零息债券、可赎回债券等
"""
import datetime
from typing import Dict, Any, List, Optional
import QuantLib as ql
from mcp.server.fastmcp import FastMCP

# 使用外部传入的 mcp 实例，如果不存在则创建新的
try:
    # 尝试从 server.py 获取 mcp 实例
    from ..server import mcp
except ImportError:
    # 如果失败，尝试从 server_llm.py 获取
    try:
        from src.server.server_llm import mcp
    except ImportError:
        mcp = FastMCP("QuantLib Bonds")


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
        return ql.ActualActual(ql.ActualActual.Bond)
    else:
        return ql.Thirty360(ql.Thirty360.USA)


@mcp.tool()
def price_fixed_rate_bond(
    settlement_date: str,
    maturity_date: str,
    coupon_rate: float,
    yield_rate: float,
    frequency: int = 2,
    face_value: float = 100.0,
    day_count_convention: str = "Thirty360",
    calendar_type: str = "USGovernmentBond"
) -> Dict[str, Any]:
    """
    定价固定利率债券并计算久期、凸性等分析指标
    
    :param settlement_date: 债券购买/结算日期 (YYYY-MM-DD)
    :param maturity_date: 债券到期日期 (YYYY-MM-DD)
    :param coupon_rate: 年票息率（小数，如 0.05 表示 5%）
    :param yield_rate: 到期市场收益率（小数）
    :param frequency: 每年付息次数 (1=年, 2=半年, 4=季)
    :param face_value: 债券面值
    :param day_count_convention: 日期计数惯例 ('Thirty360', 'Actual365Fixed', 'Actual360', 'ActualActual')
    :param calendar_type: 日历类型 ('USGovernmentBond', 'TARGET', 'Null')
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        ql.Settings.instance().evaluationDate = settle_d

        # 日历设置
        if calendar_type == "USGovernmentBond":
            calendar = ql.UnitedStates(ql.UnitedStates.GovernmentBond)
        elif calendar_type == "TARGET":
            calendar = ql.TARGET()
        else:
            calendar = ql.NullCalendar()
        
        day_counter = get_day_counter(day_count_convention)

        # 付息计划
        tenor = ql.Period(get_frequency_enum(frequency))
        schedule = ql.Schedule(
            settle_d,
            mat_d,
            tenor,
            calendar,
            ql.Unadjusted,
            ql.Unadjusted,
            ql.DateGeneration.Backward,
            False
        )

        # 创建固定利率债券
        coupons = [coupon_rate]
        bond = ql.FixedRateBond(
            0,  # 结算天数
            face_value,
            schedule,
            coupons,
            day_counter
        )

        # 平坦收益率曲线定价
        interest_rate = ql.InterestRate(yield_rate, day_counter, ql.Compounded, frequency)
        
        clean_price = bond.cleanPrice(yield_rate, day_counter, ql.Compounded, frequency)
        dirty_price = bond.dirtyPrice(yield_rate, day_counter, ql.Compounded, frequency)
        
        # 风险指标
        duration = ql.BondFunctions.duration(bond, interest_rate, ql.Duration.Modified)
        macaulay_duration = ql.BondFunctions.duration(bond, interest_rate, ql.Duration.Macaulay)
        convexity = ql.BondFunctions.convexity(bond, interest_rate)
        bpv = ql.BondFunctions.basisPointValue(bond, interest_rate)

        # 现金流
        cashflows = bond.cashflows()
        cf_list = []
        for cf in cashflows:
            cf_list.append({
                "date": cf.date().to_datetime().strftime("%Y-%m-%d"),
                "amount": cf.amount()
            })

        return {
            "clean_price": clean_price,
            "dirty_price": dirty_price,
            "accrued_amount": bond.accruedAmount(),
            "modified_duration": duration,
            "macaulay_duration": macaulay_duration,
            "convexity": convexity,
            "bpv": bpv,
            "yield": bond.bondYield(clean_price, day_counter, ql.Compounded, frequency),
            "cashflows": cf_list
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_floating_rate_bond(
    settlement_date: str,
    maturity_date: str,
    floating_spread: float,
    yield_rate: float,
    frequency: int = 2,
    face_value: float = 100.0,
    day_count_convention: str = "Actual360",
    gearing: float = 1.0
) -> Dict[str, Any]:
    """
    定价浮动利率债券
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param floating_spread: 浮动利差（小数）
    :param yield_rate: 贴现率（小数）
    :param frequency: 每年重置次数 (1=年, 2=半年, 4=季)
    :param face_value: 债券面值
    :param day_count_convention: 日期计数惯例
    :param gearing: 杠杆系数（通常为 1.0）
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

        # 浮动利率指数
        ibor_index = ql.Euribor(ql.Period(get_frequency_enum(frequency)), discount_curve)

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

        # 创建浮动利率债券
        bond = ql.FloatingRateBond(
            0,  # 结算天数
            face_value,
            schedule,
            ibor_index,
            day_counter,
            [gearing],
            [floating_spread]
        )

        # 定价引擎
        engine = ql.DiscountingBondEngine(discount_curve)
        bond.setPricingEngine(engine)

        # 预测现金流
        cashflows = bond.cashflows()
        cf_list = []
        for cf in cashflows:
            cf_list.append({
                "date": cf.date().to_datetime().strftime("%Y-%m-%d"),
                "amount": cf.amount()
            })

        return {
            "npv": bond.NPV(),
            "clean_price": bond.cleanPrice(),
            "dirty_price": bond.dirtyPrice(),
            "accrued_amount": bond.accruedAmount(),
            "cashflows": cf_list
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_zero_coupon_bond(
    settlement_date: str,
    maturity_date: str,
    yield_rate: float,
    face_value: float = 100.0,
    day_count_convention: str = "Actual365Fixed",
    compounding: str = "Compounded",
    frequency: int = 2
) -> Dict[str, Any]:
    """
    定价零息债券
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param yield_rate: 到期收益率（小数）
    :param face_value: 债券面值
    :param day_count_convention: 日期计数惯例
    :param compounding: 复利方式 ('Compounded', 'Continuous', 'Simple')
    :param frequency: 复利频率（仅 Compounded 有效）
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        ql.Settings.instance().evaluationDate = settle_d

        day_counter = get_day_counter(day_count_convention)

        # 复利方式
        if compounding == "Continuous":
            comp = ql.Continuous
            freq = 0
        elif compounding == "Simple":
            comp = ql.Simple
            freq = 0
        else:
            comp = ql.Compounded
            freq = frequency

        # 创建零息债券
        bond = ql.ZeroCouponBond(
            0,  # 结算天数
            ql.UnitedStates(ql.UnitedStates.GovernmentBond),
            face_value,
            mat_d,
            ql.Following,
            yield_rate,
            settle_d
        )

        # 计算价格
        clean_price = bond.cleanPrice(yield_rate, day_counter, comp, freq)
        dirty_price = bond.dirtyPrice(yield_rate, day_counter, comp, freq)

        # 久期和凸性
        interest_rate = ql.InterestRate(yield_rate, day_counter, comp, freq)
        duration = ql.BondFunctions.duration(bond, interest_rate, ql.Duration.Modified)
        convexity = ql.BondFunctions.convexity(bond, interest_rate)

        return {
            "clean_price": clean_price,
            "dirty_price": dirty_price,
            "accrued_amount": bond.accruedAmount(),
            "modified_duration": duration,
            "convexity": convexity,
            "yield": yield_rate,
            "maturity_years": (mat_d - settle_d) / 365.25
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_callable_bond(
    settlement_date: str,
    maturity_date: str,
    coupon_rate: float,
    call_price: float,
    call_date: str,
    yield_rate: float,
    hull_white_a: float = 0.03,
    hull_white_sigma: float = 0.012,
    face_value: float = 100.0,
    frequency: int = 2
) -> Dict[str, Any]:
    """
    使用 Hull-White 单因子短期利率模型定价可赎回债券
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param coupon_rate: 票息率（小数）
    :param call_price: 赎回价格（通常为 100.0 或 101.0）
    :param call_date: 可赎回日期 (YYYY-MM-DD)
    :param yield_rate: 平坦曲线参考利率（小数）
    :param hull_white_a: Hull-White 模型均值回归速度参数
    :param hull_white_sigma: Hull-White 模型波动率参数
    :param face_value: 债券面值
    :param frequency: 付息频率
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        call_d = parse_date(call_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.UnitedStates(ql.UnitedStates.GovernmentBond)
        day_counter = ql.Thirty360(ql.Thirty360.USA)

        # 生成付息计划
        schedule = ql.Schedule(
            settle_d, mat_d, ql.Period(get_frequency_enum(frequency)), calendar,
            ql.Unadjusted, ql.Unadjusted, ql.DateGeneration.Backward, False
        )

        # 可赎回安排
        callability_price = ql.BondPrice(call_price, ql.BondPrice.Clean)
        callability = ql.Callability(callability_price, ql.Callability.Call, call_d)
        callability_schedule = ql.CallabilitySchedule([callability])

        # 创建可赎回债券
        bond = ql.CallableFixedRateBond(
            0, face_value, schedule, [coupon_rate], day_counter,
            ql.Following, face_value, mat_d, callability_schedule
        )

        # 平坦收益率曲线
        term_structure = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(yield_rate)), day_counter)
        )
        
        # Hull-White 模型
        model = ql.HullWhite(term_structure, hull_white_a, hull_white_sigma)
        
        # 定价引擎
        grid_steps = 40
        engine = ql.TreeCallableFixedRateBondEngine(model, grid_steps)
        bond.setPricingEngine(engine)

        return {
            "npv": bond.NPV(),
            "clean_price": bond.cleanPrice(),
            "dirty_price": bond.dirtyPrice(),
            "accrued_amount": bond.accruedAmount(),
            "oas_spread": bond.OAS(yield_rate, model, 1e-6, 40)
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_cms_rate_bond(
    settlement_date: str,
    maturity_date: str,
    coupon_gearing: float,
    coupon_spread: float,
    yield_rate: float,
    frequency: int = 2,
    face_value: float = 100.0,
    cms_index_tenor: str = "10Y",
    payment_lag: int = 2
) -> Dict[str, Any]:
    """
    定价 CMS（固定息票互换）利率债券
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param coupon_gearing: CMS 利差系数
    :param coupon_spread: CMS 利差（小数）
    :param yield_rate: 贴现率（小数）
    :param frequency: 付息频率
    :param face_value: 债券面值
    :param cms_index_tenor: CMS 指数期限（如 '10Y', '5Y'）
    :param payment_lag: 支付滞后天数
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

        # CMS 指数
        swap_index = ql.EuriborSwapIsdaFixA(
            ql.Period(ql.Semiannual),
            ql.Period(int(cms_index_tenor[:-1]), ql.Years if cms_index_tenor.endswith('Y') else ql.Months),
            discount_curve
        )

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

        # 创建 CMS 利率债券
        bond = ql.CmsRateBond(
            0,
            face_value,
            schedule,
            swap_index,
            day_counter,
            ql.Following,
            payment_lag,
            [coupon_gearing],
            [coupon_spread],
            [0.0],  #  caps
            [0.0],  #  floors
            [False] #  atm caps/floors
        )

        # 定价引擎
        engine = ql.DiscountingBondEngine(discount_curve)
        bond.setPricingEngine(engine)

        return {
            "npv": bond.NPV(),
            "clean_price": bond.cleanPrice(),
            "dirty_price": bond.dirtyPrice(),
            "accrued_amount": bond.accruedAmount()
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_inflation_linked_bond(
    settlement_date: str,
    maturity_date: str,
    coupon_rate: float,
    inflation_rate: float,
    frequency: int = 2,
    face_value: float = 100.0,
    base_cpi: float = 100.0,
    observation_lag_months: int = 3
) -> Dict[str, Any]:
    """
    定价通胀挂钩债券
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param coupon_rate: 票息率（小数）
    :param inflation_rate: 预期通胀率（小数）
    :param frequency: 付息频率
    :param face_value: 债券面值
    :param base_cpi: 基准 CPI 值
    :param observation_lag_months: 通胀数据观察滞后月数
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.UnitedStates(ql.UnitedStates.GovernmentBond)
        day_counter = ql.Thirty360(ql.Thirty360.USA)

        # 通胀曲线
        inflation_curve = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(inflation_rate)), day_counter)
        )

        # 贴现曲线
        discount_curve = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(0.02)), day_counter)
        )

        # CPI 指数
        cpi_index = ql.USCPI(
            ql.Period(observation_lag_months, ql.Months),
            False,  #  not interpolated
            inflation_curve
        )

        # 付息计划
        schedule = ql.Schedule(
            settle_d,
            mat_d,
            ql.Period(get_frequency_enum(frequency)),
            calendar,
            ql.Unadjusted,
            ql.Unadjusted,
            ql.DateGeneration.Backward,
            False
        )

        # 创建 CPI 债券
        bond = ql.CPIBond(
            0,
            face_value,
            False,  #  not growth
            schedule,
            ql.Following,
            [coupon_rate],
            cpi_index,
            ql.Average,
            base_cpi
        )

        # 定价引擎
        engine = ql.DiscountingBondEngine(discount_curve)
        bond.setPricingEngine(engine)

        return {
            "npv": bond.NPV(),
            "clean_price": bond.cleanPrice(),
            "dirty_price": bond.dirtyPrice(),
            "accrued_amount": bond.accruedAmount()
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def bond_cashflow_analysis(
    settlement_date: str,
    maturity_date: str,
    coupon_rate: float,
    yield_rate: float,
    frequency: int = 2,
    face_value: float = 100.0,
    day_count_convention: str = "Thirty360"
) -> Dict[str, Any]:
    """
    债券现金流分析
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param coupon_rate: 票息率（小数）
    :param yield_rate: 收益率（小数）
    :param frequency: 付息频率
    :param face_value: 债券面值
    :param day_count_convention: 日期计数惯例
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.UnitedStates(ql.UnitedStates.GovernmentBond)
        day_counter = get_day_counter(day_count_convention)

        # 付息计划
        schedule = ql.Schedule(
            settle_d,
            mat_d,
            ql.Period(get_frequency_enum(frequency)),
            calendar,
            ql.Unadjusted,
            ql.Unadjusted,
            ql.DateGeneration.Backward,
            False
        )

        # 创建债券
        bond = ql.FixedRateBond(
            0,
            face_value,
            schedule,
            [coupon_rate],
            day_counter
        )

        # 现金流分析
        cashflows = bond.cashflows()
        cf_analysis = []
        total_pv = 0.0
        
        interest_rate = ql.InterestRate(yield_rate, day_counter, ql.Compounded, frequency)
        
        for i, cf in enumerate(cashflows):
            cf_date = cf.date().to_datetime()
            years = (cf_date - settle_d).days / 365.25
            pv = cf.amount() / (1 + yield_rate / frequency) ** (frequency * years)
            total_pv += pv
            
            cf_analysis.append({
                "period": i + 1,
                "date": cf_date.strftime("%Y-%m-%d"),
                "amount": cf.amount(),
                "years": round(years, 4),
                "pv": round(pv, 6),
                "weight": round(pv / total_pv, 6) if total_pv > 0 else 0
            })

        # 重新计算权重
        if total_pv > 0:
            for cf in cf_analysis:
                cf["weight"] = round(cf["pv"] / total_pv, 6)

        return {
            "total_pv": round(total_pv, 6),
            "number_of_cashflows": len(cf_analysis),
            "cashflows": cf_analysis
        }
    except Exception as e:
        return {"error": str(e)}
