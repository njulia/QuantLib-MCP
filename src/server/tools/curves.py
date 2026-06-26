"""
收益率曲线类 MCP 工具
包含：收益率曲线构建、贴现曲线、远期曲线、插值曲线等
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
        mcp = FastMCP("QuantLib Curves")


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
    elif day_count_convention == "ActualActual":
        return ql.ActualActual(ql.ActualActual.ISDA)
    else:
        return ql.Actual360()


@mcp.tool()
def build_piecewise_flat_forward_curve(
    settlement_date: str,
    deposit_rates: List[Dict[str, Any]],
    fra_rates: List[Dict[str, Any]] = None,
    swap_rates: List[Dict[str, Any]] = None,
    futures_rates: List[Dict[str, Any]] = None,
    day_count_convention: str = "Actual360",
    calendar_type: str = "TARGET"
) -> Dict[str, Any]:
    """
    构建分段常数远期收益率曲线
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param deposit_rates: 存款利率列表 [{"tenor": "1M", "rate": 0.04}, ...]
    :param fra_rates: FRA 利率列表 [{"tenor": "3x6", "rate": 0.042}, ...]
    :param swap_rates: 互换利率列表 [{"tenor": "5Y", "rate": 0.035}, ...]
    :param futures_rates: 期货利率列表
    :param day_count_convention: 日期计数惯例
    :param calendar_type: 日历类型
    """
    try:
        settle_d = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.TARGET() if calendar_type == "TARGET" else ql.UnitedStates(ql.UnitedStates.GovernmentBond)
        day_counter = get_day_counter(day_count_convention)

        instruments = []

        # 添加存款工具
        for dep in (deposit_rates or []):
            tenor_str = dep['tenor']
            rate = dep['rate']
            val = int(tenor_str[:-1])
            unit = tenor_str[-1].upper()
            tenor = ql.Period(val, ql.Months if unit == 'M' else ql.Years if unit == 'Y' else ql.Days)
            
            helper = ql.DepositRateHelper(
                ql.QuoteHandle(ql.SimpleQuote(rate)),
                tenor,
                2,
                calendar,
                ql.ModifiedFollowing,
                False,
                day_counter
            )
            instruments.append(helper)

        # 添加 FRA 工具
        for fra in (fra_rates or []):
            tenor_str = fra['tenor']
            rate = fra['rate']
            # 解析 "3x6" 格式
            parts = tenor_str.split('x')
            start_months = int(parts[0])
            end_months = int(parts[1])
            
            helper = ql.FraRateHelper(
                ql.QuoteHandle(ql.SimpleQuote(rate)),
                start_months,
                end_months - start_months,
                2,
                calendar,
                ql.ModifiedFollowing,
                False,
                day_counter
            )
            instruments.append(helper)

        # 添加互换工具
        for sw in (swap_rates or []):
            tenor_str = sw['tenor']
            rate = sw['rate']
            val = int(tenor_str[:-1])
            unit = tenor_str[-1].upper()
            tenor = ql.Period(val, ql.Years if unit == 'Y' else ql.Months)
            
            index = ql.Euribor(ql.Period(6, ql.Months))
            helper = ql.SwapRateHelper(
                ql.QuoteHandle(ql.SimpleQuote(rate)),
                tenor,
                calendar,
                ql.Annual,
                ql.ModifiedFollowing,
                ql.Thirty360(ql.Thirty360.BondBasis),
                index
            )
            instruments.append(helper)

        # 构建曲线
        yield_curve = ql.PiecewiseFlatForward(settle_d, instruments, ql.Actual365Fixed())

        # 提取曲线节点
        curve_nodes = []
        for years in range(1, 31):
            target_date = settle_d + ql.Period(years, ql.Years)
            if target_date > settle_d:
                zero_rate = yield_curve.zeroRate(target_date, ql.Actual365Fixed(), ql.Continuous).value()
                df = yield_curve.discount(target_date)
                fwd_rate = yield_curve.forwardRate(target_date, target_date + ql.Period(1, ql.Years), ql.Actual365Fixed(), ql.Continuous).value()
                curve_nodes.append({
                    "date": target_date.to_datetime().strftime("%Y-%m-%d"),
                    "years": years,
                    "zero_rate": round(zero_rate, 6),
                    "discount_factor": round(df, 6),
                    "forward_rate": round(fwd_rate, 6)
                })

        return {
            "status": "Success",
            "number_of_instruments": len(instruments),
            "curve_nodes": curve_nodes
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def build_zero_coupon_curve(
    settlement_date: str,
    zero_rates: List[Dict[str, Any]],
    day_count_convention: str = "Actual365Fixed",
    compounding: str = "Continuous"
) -> Dict[str, Any]:
    """
    构建零息收益率曲线
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param zero_rates: 零息利率列表 [{"tenor": "1Y", "rate": 0.03}, ...]
    :param day_count_convention: 日期计数惯例
    :param compounding: 复利方式 ('Continuous', 'Compounded', 'Simple')
    """
    try:
        settle_d = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = settle_d

        day_counter = get_day_counter(day_count_convention)

        # 复利方式
        if compounding == "Continuous":
            comp = ql.Continuous
            freq = 0
        elif compounding == "Compounded":
            comp = ql.Compounded
            freq = 2
        else:
            comp = ql.Simple
            freq = 0

        dates = []
        rates = []
        for zr in zero_rates:
            tenor_str = zr['tenor']
            rate = zr['rate']
            val = int(tenor_str[:-1])
            unit = tenor_str[-1].upper()
            if unit == 'Y':
                tenor = ql.Period(val, ql.Years)
            else:
                tenor = ql.Period(val, ql.Months)
            
            dates.append(settle_d + tenor)
            rates.append(rate)

        # 插值零息曲线
        zero_curve = ql.ZeroCurve(dates, rates, day_counter, ql.NullCalendar(), ql.Linear())

        # 提取曲线值
        curve_values = []
        for i in range(1, 31):
            target_date = settle_d + ql.Period(i, ql.Years)
            if target_date > settle_d:
                zero_rate = zero_curve.zeroRate(target_date, day_counter, comp, freq).value()
                df = zero_curve.discount(target_date)
                curve_values.append({
                    "date": target_date.to_datetime().strftime("%Y-%m-%d"),
                    "years": i,
                    "zero_rate": round(zero_rate, 6),
                    "discount_factor": round(df, 6)
                })

        return {
            "status": "Success",
            "curve_values": curve_values
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def build_discount_curve(
    settlement_date: str,
    discount_factors: List[Dict[str, Any]],
    day_count_convention: str = "Actual365Fixed"
) -> Dict[str, Any]:
    """
    构建贴现曲线
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param discount_factors: 贴现因子列表 [{"date": "2027-06-25", "df": 0.95}, ...]
    :param day_count_convention: 日期计数惯例
    """
    try:
        settle_d = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = settle_d

        day_counter = get_day_counter(day_count_convention)

        dates = [settle_d]
        dfs = [1.0]
        for df in discount_factors:
            dates.append(parse_date(df['date']))
            dfs.append(df['df'])

        # 贴现曲线
        discount_curve = ql.DiscountCurve(dates, dfs, day_counter, ql.NullCalendar(), ql.Linear())

        # 提取零息利率
        curve_values = []
        for d, df_val in zip(dates, dfs):
            if d > settle_d:
                zero_rate = discount_curve.zeroRate(d, day_counter, ql.Continuous, 0).value()
                curve_values.append({
                    "date": d.to_datetime().strftime("%Y-%m-%d"),
                    "discount_factor": round(df_val, 6),
                    "zero_rate": round(zero_rate, 6)
                })

        return {
            "status": "Success",
            "number_of_points": len(dates),
            "curve_values": curve_values
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def build_forward_curve(
    settlement_date: str,
    forward_rates: List[Dict[str, Any]],
    day_count_convention: str = "Actual365Fixed"
) -> Dict[str, Any]:
    """
    构建远期曲线
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param forward_rates: 远期利率列表 [{"date": "2027-06-25", "rate": 0.035}, ...]
    :param day_count_convention: 日期计数惯例
    """
    try:
        settle_d = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = settle_d

        day_counter = get_day_counter(day_count_convention)

        dates = []
        rates = []
        for fr in forward_rates:
            dates.append(parse_date(fr['date']))
            rates.append(fr['rate'])

        # 远期曲线
        forward_curve = ql.ForwardCurve(dates, rates, day_counter, ql.NullCalendar(), ql.Linear())

        # 提取曲线值
        curve_values = []
        for d, r in zip(dates, rates):
            fwd_rate = forward_curve.forwardRate(d, d, day_counter, ql.Continuous).value()
            curve_values.append({
                "date": d.to_datetime().strftime("%Y-%m-%d"),
                "forward_rate": round(fwd_rate, 6)
            })

        return {
            "status": "Success",
            "number_of_points": len(dates),
            "curve_values": curve_values
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def get_curve_rates(
    settlement_date: str,
    yield_rate: float,
    day_count_convention: str = "Actual365Fixed",
    start_years: int = 1,
    end_years: int = 30
) -> Dict[str, Any]:
    """
    获取平坦收益率曲线在不同期限的利率
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param yield_rate: 平坦收益率（小数）
    :param day_count_convention: 日期计数惯例
    :param start_years: 起始年份
    :param end_years: 结束年份
    """
    try:
        settle_d = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = settle_d

        day_counter = get_day_counter(day_count_convention)

        # 平坦曲线
        flat_curve = ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(yield_rate)), day_counter)

        # 提取各期限利率
        rates = []
        for years in range(start_years, end_years + 1):
            target_date = settle_d + ql.Period(years, ql.Years)
            zero_rate = flat_curve.zeroRate(target_date, day_counter, ql.Continuous).value()
            df = flat_curve.discount(target_date)
            fwd_rate = flat_curve.forwardRate(target_date, target_date + ql.Period(1, ql.Years), day_counter, ql.Continuous).value()
            rates.append({
                "years": years,
                "zero_rate": round(zero_rate, 6),
                "discount_factor": round(df, 6),
                "forward_rate": round(fwd_rate, 6)
            })

        return {
            "yield_rate": yield_rate,
            "rates": rates
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def calculate_discount_factor(
    settlement_date: str,
    target_date: str,
    yield_rate: float,
    day_count_convention: str = "Actual365Fixed",
    compounding: str = "Continuous"
) -> Dict[str, Any]:
    """
    计算贴现因子
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param target_date: 目标日期 (YYYY-MM-DD)
    :param yield_rate: 收益率（小数）
    :param day_count_convention: 日期计数惯例
    :param compounding: 复利方式
    """
    try:
        settle_d = parse_date(settlement_date)
        target_d = parse_date(target_date)
        ql.Settings.instance().evaluationDate = settle_d

        day_counter = get_day_counter(day_count_convention)

        # 复利方式
        if compounding == "Continuous":
            comp = ql.Continuous
            freq = 0
        elif compounding == "Compounded":
            comp = ql.Compounded
            freq = 2
        else:
            comp = ql.Simple
            freq = 0

        # 平坦曲线
        flat_curve = ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(yield_rate)), day_counter)

        df = flat_curve.discount(target_d)
        year_frac = day_counter.yearFraction(settle_d, target_d)
        zero_rate = flat_curve.zeroRate(target_d, day_counter, comp, freq).value()

        return {
            "discount_factor": round(df, 8),
            "year_fraction": round(year_frac, 6),
            "zero_rate": round(zero_rate, 6),
            "settlement_date": settle_d.to_datetime().strftime("%Y-%m-%d"),
            "target_date": target_d.to_datetime().strftime("%Y-%m-%d")
        }
    except Exception as e:
        return {"error": str(e)}
