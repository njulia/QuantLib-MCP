"""
资产互换类 MCP 工具
包含：资产互换分析、总收益互换等
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
        mcp = FastMCP("QuantLib Asset Swap")


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
        4: ql.Quarterly
    }
    return freq_map.get(freq, ql.Semiannual)


@mcp.tool()
def price_asset_swap(
    settlement_date: str,
    maturity_date: str,
    coupon_rate: float,
    bond_price: float,
    yield_rate: float,
    floating_spread: float = 0.0,
    frequency: int = 2,
    face_value: float = 100.0,
    day_count_convention: str = "Thirty360"
) -> Dict[str, Any]:
    """
    定价资产互换（将固定利率债券转换为浮动利率）
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param coupon_rate: 债券票息率（小数）
    :param bond_price: 债券市场价格
    :param yield_rate: 市场收益率（小数）
    :param floating_spread: 浮动端利差（小数）
    :param frequency: 付息频率
    :param face_value: 债券面值
    :param day_count_convention: 日期计数惯例
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.UnitedStates(ql.UnitedStates.GovernmentBond)
        day_counter = ql.Thirty360(ql.Thirty360.USA) if day_count_convention == "Thirty360" else ql.Actual365Fixed()

        # 创建固定利率债券
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

        bond = ql.FixedRateBond(
            0,
            face_value,
            schedule,
            [coupon_rate],
            day_counter
        )

        # 贴现曲线
        discount_curve = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(yield_rate)), day_counter)
        )

        # 浮动利率指数
        ibor_index = ql.Euribor(ql.Period(get_frequency_enum(frequency)), discount_curve)

        # 创建资产互换
        asset_swap = ql.AssetSwap(
            True,  # 接收浮动
            bond,
            bond_price,
            ibor_index,
            floating_spread,
            schedule
        )

        # 定价引擎
        engine = ql.AssetSwapEngine(discount_curve)
        asset_swap.setPricingEngine(engine)

        # 计算债券收益率
        bond_yield = bond.bondYield(bond_price, day_counter, ql.Compounded, frequency)

        # 资产互换利差
        par_spread = asset_swap.parSpread()
        par_swap_rate = asset_swap.parSwapRate()

        return {
            "bond_clean_price": bond.cleanPrice(),
            "bond_dirty_price": bond.dirtyPrice(),
            "bond_yield": round(bond_yield, 6),
            "asset_swap_par_spread": round(par_spread, 6),
            "asset_swap_par_spread_bps": round(par_spread * 10000, 2),
            "par_swap_rate": round(par_swap_rate, 6),
            "floating_spread": floating_spread,
            "fixed_leg_npv": asset_swap.fixedLegNPV(),
            "floating_leg_npv": asset_swap.floatingLegNPV()
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_equity_total_return_swap(
    settlement_date: str,
    maturity_date: str,
    initial_spot: float,
    final_spot: float,
    funding_rate: float,
    dividend_yield: float = 0.0,
    notional: float = 10_000_000.0,
    frequency: int = 4
) -> Dict[str, Any]:
    """
    定价股票总收益互换
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param initial_spot: 初始股票价格
    :param final_spot: 到期股票价格
    :param funding_rate: 融资利率（小数）
    :param dividend_yield: 股息率（小数）
    :param notional: 名义本金
    :param frequency: 付费频率
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        ql.Settings.instance().evaluationDate = settle_d

        day_counter = ql.Actual360()
        year_fraction = day_counter.yearFraction(settle_d, mat_d)

        # 股票总收益
        equity_return = (final_spot - initial_spot) / initial_spot
        total_equity_payment = notional * (equity_return + dividend_yield * year_fraction)

        # 融资支付
        funding_payment = notional * funding_rate * year_fraction

        # 互换 NPV
        npv = total_equity_payment - funding_payment

        return {
            "equity_return": round(equity_return, 6),
            "dividend_payment": round(notional * dividend_yield * year_fraction, 2),
            "total_equity_payment": round(total_equity_payment, 2),
            "funding_payment": round(funding_payment, 2),
            "npv": round(npv, 2),
            "year_fraction": round(year_fraction, 6),
            "annualized_return_pct": round(equity_return / year_fraction * 100, 4)
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def calculate_bond_z_spread(
    settlement_date: str,
    maturity_date: str,
    coupon_rate: float,
    bond_price: float,
    benchmark_rates: List[Dict[str, Any]],
    frequency: int = 2,
    face_value: float = 100.0
) -> Dict[str, Any]:
    """
    计算债券 Z-Spread（零波动率利差）
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param maturity_date: 到期日期 (YYYY-MM-DD)
    :param coupon_rate: 票息率（小数）
    :param bond_price: 债券价格
    :param benchmark_rates: 基准利率曲线 [{"date": "2027-06-25", "rate": 0.03}, ...]
    :param frequency: 付息频率
    :param face_value: 债券面值
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.UnitedStates(ql.UnitedStates.GovernmentBond)
        day_counter = ql.Thirty360(ql.Thirty360.USA)

        # 创建债券
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

        bond = ql.FixedRateBond(
            0,
            face_value,
            schedule,
            [coupon_rate],
            day_counter
        )

        # 创建基准曲线
        dates = [settle_d]
        rates = [1.0]  # 贴现因子
        for br in benchmark_rates:
            dates.append(parse_date(br['date']))
            rates.append(br['rate'])

        benchmark_curve = ql.ZeroCurve(
            [parse_date(br['date']) for br in benchmark_rates],
            [br['rate'] for br in benchmark_rates],
            day_counter,
            ql.NullCalendar(),
            ql.Linear()
        )

        # 计算 Z-Spread
        # 使用二分法找到使债券价格等于市场价格的利差
        low_spread = -0.05
        high_spread = 0.10
        
        for _ in range(100):
            mid_spread = (low_spread + high_spread) / 2
            
            # 计算带利差的贴现曲线
            total_pv = 0.0
            cashflows = bond.cashflows()
            for cf in cashflows:
                cf_date = cf.date()
                if cf_date > settle_d:
                    zero_rate = benchmark_curve.zeroRate(cf_date, day_counter, ql.Continuous, 0).value()
                    df = (1.0 / (1.0 + zero_rate + mid_spread)) ** ((cf_date - settle_d) / 365.25)
                    total_pv += cf.amount() * df

            if total_pv > bond_price:
                low_spread = mid_spread
            else:
                high_spread = mid_spread

        z_spread = (low_spread + high_spread) / 2

        return {
            "z_spread": round(z_spread, 6),
            "z_spread_bps": round(z_spread * 10000, 2),
            "bond_price": bond_price,
            "coupon_rate": coupon_rate
        }
    except Exception as e:
        return {"error": str(e)}
