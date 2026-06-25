"""
货币市场类 MCP 工具
包含：远期利率协议 (FRA)、存款、期货等
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
        mcp = FastMCP("QuantLib Money Market")


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
        return ql.Actual360()


@mcp.tool()
def price_fra(
    settlement_date: str,
    fra_maturity_months: int,
    fra_rate: float,
    notional: float = 10_000_000.0,
    market_rate: float = 0.04,
    day_count_convention: str = "Actual360",
    calendar_type: str = "TARGET"
) -> Dict[str, Any]:
    """
    定价远期利率协议 (FRA)
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param fra_maturity_months: FRA 到期月数（如 3, 6, 9, 12）
    :param fra_rate: 合约远期利率（小数）
    :param notional: 名义本金
    :param market_rate: 市场远期利率（小数）
    :param day_count_convention: 日期计数惯例
    :param calendar_type: 日历类型
    """
    try:
        settle_d = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = settle_d

        # 日历
        if calendar_type == "USGovernmentBond":
            calendar = ql.UnitedStates(ql.UnitedStates.GovernmentBond)
        else:
            calendar = ql.TARGET()
        
        day_counter = get_day_counter(day_count_convention)

        # 到期日
        maturity = settle_d + ql.Period(fra_maturity_months, ql.Months)

        # 创建 FRA
        fra = ql.Fra(
            0.0,  # 开始时间（立即）
            fra_maturity_months,
            fra_rate,
            notional,
            ql.Position.Long,
            day_counter,
            calendar
        )

        # 贴现曲线
        discount_curve = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(market_rate)), day_counter)
        )

        # 定价引擎
        engine = ql.DiscountingFraEngine(discount_curve)
        fra.setPricingEngine(engine)

        return {
            "npv": fra.NPV(),
            "fair_rate": fra.fraRate(),
            "maturity_date": maturity.to_datetime().strftime("%Y-%m-%d"),
            "implied_forward_rate": market_rate
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_deposit(
    settlement_date: str,
    maturity_months: int,
    deposit_rate: float,
    notional: float = 10_000_000.0,
    day_count_convention: str = "Actual360",
    fixing_days: int = 2
) -> Dict[str, Any]:
    """
    定价存款工具
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param maturity_months: 存款期限（月）
    :param deposit_rate: 存款利率（小数）
    :param notional: 本金
    :param day_count_convention: 日期计数惯例
    :param fixing_days: 定盘天数
    """
    try:
        settle_d = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.TARGET()
        day_counter = get_day_counter(day_count_convention)

        # 到期日
        maturity = settle_d + ql.Period(maturity_months, ql.Months)

        # 存款利率
        interest_rate = ql.InterestRate(
            deposit_rate,
            day_counter,
            ql.Simple,
            ql.Once
        )

        # 计算利息
        year_fraction = day_counter.yearFraction(settle_d, maturity)
        interest = notional * deposit_rate * year_fraction
        total_amount = notional + interest

        return {
            "notional": notional,
            "maturity_date": maturity.to_datetime().strftime("%Y-%m-%d"),
            "interest": interest,
            "total_amount": total_amount,
            "year_fraction": year_fraction,
            "deposit_rate": deposit_rate
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_futures(
    settlement_date: str,
    futures_maturity_months: int,
    futures_price: float,
    notional: float = 10_000_000.0,
    day_count_convention: str = "Actual360"
) -> Dict[str, Any]:
    """
    定价利率期货
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param futures_maturity_months: 期货到期月数
    :param futures_price: 期货价格
    :param notional: 名义本金
    :param day_count_convention: 日期计数惯例
    """
    try:
        settle_d = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.TARGET()
        day_counter = get_day_counter(day_count_convention)

        # 到期日
        maturity = settle_d + ql.Period(futures_maturity_months, ql.Months)

        # 隐含利率（期货价格通常报价为 100 - 利率）
        implied_rate = (100.0 - futures_price) / 100.0

        # 年分数
        year_fraction = day_counter.yearFraction(settle_d, maturity)

        # 贴现因子
        discount_factor = 1.0 / (1.0 + implied_rate * year_fraction)

        return {
            "futures_price": futures_price,
            "implied_rate": implied_rate,
            "maturity_date": maturity.to_datetime().strftime("%Y-%m-%d"),
            "year_fraction": year_fraction,
            "discount_factor": discount_factor,
            "npv": notional * discount_factor
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def build_deposit_futures_curve(
    settlement_date: str,
    deposit_rates: List[Dict[str, Any]],
    futures_rates: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    使用存款和期货数据构建短期收益率曲线
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param deposit_rates: 存款利率列表，格式：[{"tenor": "1M", "rate": 0.04}, ...]
    :param futures_rates: 期货利率列表，格式：[{"tenor": "3M", "rate": 0.042}, ...]
    """
    try:
        settle_d = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.TARGET()
        day_counter = ql.Actual360()

        instruments = []

        # 添加存款工具
        for dep in deposit_rates:
            tenor_str = dep['tenor']
            rate = dep['rate']
            
            # 解析期限
            val = int(tenor_str[:-1])
            unit = tenor_str[-1]
            if unit == 'M':
                tenor = ql.Period(val, ql.Months)
            else:
                tenor = ql.Period(val, ql.Days)

            helper = ql.DepositRateHelper(
                ql.QuoteHandle(ql.SimpleQuote(rate)),
                tenor,
                2,  # 定盘天数
                calendar,
                ql.ModifiedFollowing,
                False,
                day_counter
            )
            instruments.append(helper)

        # 添加工具
        for fut in futures_rates:
            rate = fut['rate']
            
            # 创建期货利率工具
            helper = ql.FuturesRateHelper(
                ql.QuoteHandle(ql.SimpleQuote(rate)),
                ql.Date(1, 1, 2025),  #  IMM 日期
                3,  # 月数
                calendar,
                ql.ModifiedFollowing,
                False,
                day_counter
            )
            instruments.append(helper)

        # 构建曲线
        if len(instruments) > 0:
            yield_curve = ql.PiecewiseFlatForward(
                settle_d,
                instruments,
                ql.Actual365Fixed()
            )

            # 提取曲线节点
            curve_nodes = []
            for i in range(1, 13):
                target_date = settle_d + ql.Period(i, ql.Months)
                if target_date > settle_d:
                    zero_rate = yield_curve.zeroRate(
                        target_date,
                        ql.Actual365Fixed(),
                        ql.Continuous
                    ).value()
                    curve_nodes.append({
                        "date": target_date.to_datetime().strftime("%Y-%m-%d"),
                        "zero_rate": zero_rate,
                        "months": i
                    })

            return {
                "status": "Success",
                "number_of_instruments": len(instruments),
                "curve_nodes": curve_nodes
            }
        else:
            return {"error": "No instruments provided"}
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def calculate_forward_rate(
    settlement_date: str,
    start_months: int,
    end_months: int,
    yield_rate: float,
    day_count_convention: str = "Actual360",
    compounding: str = "Simple"
) -> Dict[str, Any]:
    """
    计算远期利率
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param start_months: 远期开始月数
    :param end_months: 远期结束月数
    :param yield_rate: 即期利率（小数）
    :param day_count_convention: 日期计数惯例
    :param compounding: 复利方式 ('Simple', 'Compounded', 'Continuous')
    """
    try:
        settle_d = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = settle_d

        day_counter = get_day_counter(day_count_convention)

        # 日期
        start_date = settle_d + ql.Period(start_months, ql.Months)
        end_date = settle_d + ql.Period(end_months, ql.Months)

        # 复利方式
        if compounding == "Continuous":
            comp = ql.Continuous
            freq = 0
        elif compounding == "Compounded":
            comp = ql.Compounded
            freq = 4
        else:
            comp = ql.Simple
            freq = 0

        # 贴现曲线
        discount_curve = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(yield_rate)), day_counter)
        )

        # 计算远期利率
        forward_rate = discount_curve.forwardRate(
            start_date,
            end_date,
            day_counter,
            comp,
            freq
        ).value()

        # 计算贴现因子
        df_start = discount_curve.discount(start_date)
        df_end = discount_curve.discount(end_date)

        return {
            "forward_rate": forward_rate,
            "forward_rate_bps": forward_rate * 10000,
            "start_date": start_date.to_datetime().strftime("%Y-%m-%d"),
            "end_date": end_date.to_datetime().strftime("%Y-%m-%d"),
            "discount_factor_start": df_start,
            "discount_factor_end": df_end,
            "year_fraction": day_counter.yearFraction(start_date, end_date)
        }
    except Exception as e:
        return {"error": str(e)}
