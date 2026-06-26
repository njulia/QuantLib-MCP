"""
日历和计划类 MCP 工具
包含：日历查询、节假日、付息计划生成等
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
        mcp = FastMCP("QuantLib Calendars")


def parse_date(date_str: str) -> ql.Date:
    """解析 ISO 日期字符串为 QuantLib.Date"""
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    return ql.Date(dt.day, dt.month, dt.year)


def get_calendar(calendar_type: str) -> ql.Calendar:
    """获取日历对象"""
    calendar_map = {
        "TARGET": ql.TARGET(),
        "NullCalendar": ql.NullCalendar(),
        "USGovernmentBond": ql.UnitedStates(ql.UnitedStates.GovernmentBond),
        "USSettlement": ql.UnitedStates(ql.UnitedStates.Settlement),
        "USNYSE": ql.UnitedStates(ql.UnitedStates.NYSE),
        "UKSettlement": ql.UnitedKingdom(ql.UnitedKingdom.Settlement),
        "UKExchange": ql.UnitedKingdom(ql.UnitedKingdom.Exchange),
        "JapanSettlement": ql.Japan(ql.Japan.Settlement),
        "JapanExchange": ql.Japan(ql.Japan.Exchange),
        "AustraliaSettlement": ql.Australia(ql.Australia.Settlement),
        "AustraliaExchange": ql.Australia(ql.Australia.Exchange),
        "BrazilSettlement": ql.Brazil(ql.Brazil.Settlement),
        "BrazilExchange": ql.Brazil(ql.Brazil.Exchange),
        "CanadaSettlement": ql.Canada(ql.Canada.Settlement),
        "CanadaTSX": ql.Canada(ql.Canada.TSX),
        "ChinaSSE": ql.China(ql.China.SSE),
        "ChinaIB": ql.China(ql.China.IB),
        "GermanySettlement": ql.Germany(ql.Germany.Settlement),
        "GermanyFrankfurt": ql.Germany(ql.Germany.FrankfurtStockExchange),
        "ItalySettlement": ql.Italy(ql.Italy.Settlement),
        "ItalyExchange": ql.Italy(ql.Italy.Exchange),
        "SwitzerlandSettlement": ql.Switzerland(ql.Switzerland.Settlement),
        "SwitzerlandExchange": ql.Switzerland(ql.Switzerland.Exchange),
        "HongKongSettlement": ql.HongKong(ql.HongKong.Settlement),
        "HongKongExchange": ql.HongKong(ql.HongKong.Exchange),
        "IndiaSettlement": ql.India(ql.India.Settlement),
        "IndiaNSE": ql.India(ql.India.NSE),
    }
    return calendar_map.get(calendar_type, ql.TARGET())


@mcp.tool()
def list_holidays(
    calendar_type: str,
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """
    列出指定日历在给定日期范围内的节假日
    
    :param calendar_type: 日历类型 ('TARGET', 'USGovernmentBond', 'USNYSE', 'UKSettlement', 'JapanExchange', 'ChinaSSE', 等)
    :param start_date: 起始日期 (YYYY-MM-DD)
    :param end_date: 结束日期 (YYYY-MM-DD)
    """
    try:
        cal = get_calendar(calendar_type)
        start_d = parse_date(start_date)
        end_d = parse_date(end_date)

        holidays = []
        current = start_d
        while current <= end_d:
            if not cal.isBusinessDay(current):
                holidays.append(current.to_datetime().strftime("%Y-%m-%d"))
            current = current + 1

        return {
            "calendar": calendar_type,
            "start_date": start_date,
            "end_date": end_date,
            "holiday_count": len(holidays),
            "holidays": holidays
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def check_business_day(
    calendar_type: str,
    date: str
) -> Dict[str, Any]:
    """
    检查指定日期是否为工作日
    
    :param calendar_type: 日历类型
    :param date: 要检查的日期 (YYYY-MM-DD)
    """
    try:
        cal = get_calendar(calendar_type)
        d = parse_date(date)
        is_business = cal.isBusinessDay(d)
        is_holiday = not is_business

        return {
            "calendar": calendar_type,
            "date": date,
            "is_business_day": is_business,
            "is_holiday": is_holiday,
            "day_of_week": d.to_datetime().strftime("%A")
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def advance_date(
    calendar_type: str,
    start_date: str,
    days: int = 1,
    business_days_only: bool = True
) -> Dict[str, Any]:
    """
    从给定日期推进指定天数
    
    :param calendar_type: 日历类型
    :param start_date: 起始日期 (YYYY-MM-DD)
    :param days: 推进天数
    :param business_days_only: 是否只推进工作日
    """
    try:
        cal = get_calendar(calendar_type)
        start_d = parse_date(start_date)

        if business_days_only:
            result = cal.advance(start_d, days)
        else:
            result = start_d + days

        return {
            "calendar": calendar_type,
            "start_date": start_date,
            "days": days,
            "business_days_only": business_days_only,
            "result_date": result.to_datetime().strftime("%Y-%m-%d"),
            "day_of_week": result.to_datetime().strftime("%A")
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def business_days_between(
    calendar_type: str,
    start_date: str,
    end_date: str
) -> Dict[str, Any]:
    """
    计算两个日期之间的工作日天数
    
    :param calendar_type: 日历类型
    :param start_date: 起始日期 (YYYY-MM-DD)
    :param end_date: 结束日期 (YYYY-MM-DD)
    """
    try:
        cal = get_calendar(calendar_type)
        start_d = parse_date(start_date)
        end_d = parse_date(end_date)

        business_days = 0
        current = start_d
        while current < end_d:
            if cal.isBusinessDay(current):
                business_days += 1
            current = current + 1

        calendar_days = (end_d - start_d)

        return {
            "calendar": calendar_type,
            "start_date": start_date,
            "end_date": end_date,
            "business_days": business_days,
            "calendar_days": calendar_days
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def create_schedule(
    start_date: str,
    end_date: str,
    frequency: int = 2,
    calendar_type: str = "TARGET",
    date_generation_rule: str = "Backward",
    business_day_convention: str = "ModifiedFollowing",
    end_of_month: bool = False,
    first_date: str = None,
    next_to_last_date: str = None
) -> Dict[str, Any]:
    """
    创建付息计划
    
    :param start_date: 起始日期 (YYYY-MM-DD)
    :param end_date: 结束日期 (YYYY-MM-DD)
    :param frequency: 每年付息次数 (1=年, 2=半年, 4=季, 12=月)
    :param calendar_type: 日历类型
    :param date_generation_rule: 日期生成规则 ('Forward', 'Backward', 'Zero')
    :param business_day_convention: 营业日调整规则 ('Following', 'ModifiedFollowing', 'Preceding', 'Unadjusted')
    :param end_of_month: 是否使用月末规则
    :param first_date: 第一个付息日期（可选）
    :param next_to_last_date: 倒数第二个付息日期（可选）
    """
    try:
        start_d = parse_date(start_date)
        end_d = parse_date(end_date)
        cal = get_calendar(calendar_type)

        # 频率
        freq_map = {1: ql.Annual, 2: ql.Semiannual, 4: ql.Quarterly, 6: ql.Bimonthly, 12: ql.Monthly}
        tenor = ql.Period(freq_map.get(frequency, ql.Semiannual))

        # 日期生成规则
        rule_map = {"Forward": ql.DateGeneration.Forward, "Backward": ql.DateGeneration.Backward, "Zero": ql.DateGeneration.Zero}
        rule = rule_map.get(date_generation_rule, ql.DateGeneration.Backward)

        # 营业日调整
        bdc_map = {
            "Following": ql.Following,
            "ModifiedFollowing": ql.ModifiedFollowing,
            "Preceding": ql.Preceding,
            "Unadjusted": ql.Unadjusted
        }
        bdc = bdc_map.get(business_day_convention, ql.ModifiedFollowing)

        # 可选的 first_date 和 next_to_last_date
        first_d = parse_date(first_date) if first_date else ql.Date()
        ntl_d = parse_date(next_to_last_date) if next_to_last_date else ql.Date()

        schedule = ql.Schedule(
            start_d,
            end_d,
            tenor,
            cal,
            bdc,
            bdc,
            rule,
            end_of_month,
            first_d,
            ntl_d
        )

        # 提取日期
        dates = []
        for i, d in enumerate(schedule):
            dates.append({
                "index": i,
                "date": d.to_datetime().strftime("%Y-%m-%d"),
                "day_of_week": d.to_datetime().strftime("%A"),
                "is_regular": schedule.isRegular(i + 1)
            })

        return {
            "calendar": calendar_type,
            "frequency": frequency,
            "date_generation_rule": date_generation_rule,
            "tenor": schedule.tenor(),
            "number_of_dates": len(dates),
            "dates": dates
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def adjust_date(
    calendar_type: str,
    date: str,
    business_day_convention: str = "ModifiedFollowing"
) -> Dict[str, Any]:
    """
    根据营业日调整规则调整日期
    
    :param calendar_type: 日历类型
    :param date: 要调整的日期 (YYYY-MM-DD)
    :param business_day_convention: 调整规则
    """
    try:
        cal = get_calendar(calendar_type)
        d = parse_date(date)

        bdc_map = {
            "Following": ql.Following,
            "ModifiedFollowing": ql.ModifiedFollowing,
            "Preceding": ql.Preceding,
            "Unadjusted": ql.Unadjusted,
            "ModifiedPreceding": ql.ModifiedPreceding
        }
        bdc = bdc_map.get(business_day_convention, ql.ModifiedFollowing)

        adjusted = cal.adjust(d, bdc)

        return {
            "calendar": calendar_type,
            "original_date": date,
            "business_day_convention": business_day_convention,
            "adjusted_date": adjusted.to_datetime().strftime("%Y-%m-%d"),
            "day_of_week": adjusted.to_datetime().strftime("%A")
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def list_available_calendars() -> Dict[str, Any]:
    """
    列出所有可用的日历类型
    """
    calendars = {
        "TARGET": "欧洲央行目标日历",
        "NullCalendar": "无日历（所有日期均为工作日）",
        "USGovernmentBond": "美国政府债券日历",
        "USSettlement": "美国结算日历",
        "USNYSE": "纽约证券交易所日历",
        "UKSettlement": "英国结算日历",
        "UKExchange": "英国交易所日历",
        "JapanSettlement": "日本结算日历",
        "JapanExchange": "日本交易所日历",
        "AustraliaSettlement": "澳大利亚结算日历",
        "AustraliaExchange": "澳大利亚交易所日历",
        "BrazilSettlement": "巴西结算日历",
        "BrazilExchange": "巴西交易所日历",
        "CanadaSettlement": "加拿大结算日历",
        "CanadaTSX": "多伦多证券交易所日历",
        "ChinaSSE": "上海证券交易所日历",
        "ChinaIB": "中国银行间市场日历",
        "GermanySettlement": "德国结算日历",
        "GermanyFrankfurt": "法兰克福交易所日历",
        "ItalySettlement": "意大利结算日历",
        "ItalyExchange": "意大利交易所日历",
        "SwitzerlandSettlement": "瑞士结算日历",
        "SwitzerlandExchange": "瑞士交易所日历",
        "HongKongSettlement": "香港结算日历",
        "HongKongExchange": "香港交易所日历",
        "IndiaSettlement": "印度结算日历",
        "IndiaNSE": "印度国家证券交易所日历"
    }
    return {
        "available_calendars": calendars,
        "count": len(calendars)
    }


@mcp.tool()
def calculate_year_fraction(
    start_date: str,
    end_date: str,
    day_count_convention: str = "Actual360"
) -> Dict[str, Any]:
    """
    计算两个日期之间的年分数
    
    :param start_date: 起始日期 (YYYY-MM-DD)
    :param end_date: 结束日期 (YYYY-MM-DD)
    :param day_count_convention: 日期计数惯例 ('Actual360', 'Actual365Fixed', 'Thirty360', 'ActualActual')
    """
    try:
        start_d = parse_date(start_date)
        end_d = parse_date(end_date)

        dc_map = {
            "Actual360": ql.Actual360(),
            "Actual365Fixed": ql.Actual365Fixed(),
            "Thirty360": ql.Thirty360(ql.Thirty360.USA),
            "ActualActual": ql.ActualActual(ql.ActualActual.ISDA),
            "Actual36525": ql.Actual36525(),
            "OneDayCounter": ql.OneDayCounter(),
            "SimpleDayCounter": ql.SimpleDayCounter()
        }
        dc = dc_map.get(day_count_convention, ql.Actual360())

        year_fraction = dc.yearFraction(start_d, end_d)
        day_count = dc.dayCount(start_d, end_d)

        return {
            "start_date": start_date,
            "end_date": end_date,
            "day_count_convention": day_count_convention,
            "day_count": day_count,
            "year_fraction": round(year_fraction, 8),
            "days_between": (end_d - start_d)
        }
    except Exception as e:
        return {"error": str(e)}
