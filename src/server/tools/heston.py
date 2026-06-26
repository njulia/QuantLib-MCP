"""
Heston 模型类 MCP 工具
包含：Heston 模型定价、半解析方法、有限差分方法等
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
        mcp = FastMCP("QuantLib Heston")


def parse_date(date_str: str) -> ql.Date:
    """解析 ISO 日期字符串为 QuantLib.Date"""
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    return ql.Date(dt.day, dt.month, dt.year)


@mcp.tool()
def price_heston_european_option(
    spot: float,
    strike: float,
    risk_free_rate: float,
    dividend_yield: float,
    maturity_date: str,
    settlement_date: str,
    v0: float = 0.04,
    kappa: float = 2.0,
    theta: float = 0.04,
    sigma: float = 0.3,
    rho: float = -0.7,
    option_type: str = "call"
) -> Dict[str, Any]:
    """
    使用 Heston 随机波动率模型定价欧式期权
    
    :param spot: 标的资产当前价格
    :param strike: 期权行权价
    :param risk_free_rate: 无风险利率（小数）
    :param dividend_yield: 资产股息率（小数）
    :param maturity_date: 期权到期日期 (YYYY-MM-DD)
    :param settlement_date: 计算结算日期 (YYYY-MM-DD)
    :param v0: 初始方差（小数平方，如 0.04 表示 20% 波动率）
    :param kappa: 均值回归速度
    :param theta: 长期方差
    :param sigma: 方差波动率
    :param rho: 资产与方差的相关系数
    :param option_type: 期权类型 ('call', 'put')
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

        # Heston 模型参数
        heston_process = ql.HestonProcess(
            r_ts,
            d_ts,
            spot_handle,
            v0,
            kappa,
            theta,
            sigma,
            rho
        )
        heston_model = ql.HestonModel(heston_process)

        # Heston 定价引擎
        engine = ql.AnalyticHestonEngine(heston_model)
        option.setPricingEngine(engine)

        # 计算隐含波动率
        implied_vol = option.impliedVolatility(
            option.NPV(),
            ql.GeneralizedBlackScholesProcess(
                spot_handle,
                d_ts,
                r_ts,
                ql.BlackVolTermStructureHandle(
                    ql.BlackConstantVol(eval_date, calendar, ql.QuoteHandle(ql.SimpleQuote(0.2)), day_count)
                )
            ),
            1e-6,
            1000,
            0.05,
            5.0
        )

        return {
            "npv": option.NPV(),
            "delta": option.delta(),
            "gamma": option.gamma(),
            "vega": option.vega(),
            "theta": option.theta(),
            "rho": option.rho(),
            "heston_parameters": {
                "v0": v0,
                "kappa": kappa,
                "theta": theta,
                "sigma": sigma,
                "rho": rho
            },
            "implied_volatility": implied_vol if implied_vol > 0 else 0.0,
            "long_term_volatility": (theta ** 0.5)
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def price_heston_barrier_option(
    spot: float,
    strike: float,
    barrier_level: float,
    risk_free_rate: float,
    dividend_yield: float,
    maturity_date: str,
    settlement_date: str,
    v0: float = 0.04,
    kappa: float = 2.0,
    theta: float = 0.04,
    sigma: float = 0.3,
    rho: float = -0.7,
    barrier_type: str = "DownAndOut",
    rebate: float = 0.0,
    option_type: str = "call",
    grid_points: int = 100,
    time_steps: int = 200
) -> Dict[str, Any]:
    """
    使用有限差分方法在 Heston 模型下定价障碍期权
    
    :param spot: 标的资产当前价格
    :param strike: 期权行权价
    :param barrier_level: 障碍价格水平
    :param risk_free_rate: 无风险利率（小数）
    :param dividend_yield: 资产股息率（小数）
    :param maturity_date: 期权到期日期 (YYYY-MM-DD)
    :param settlement_date: 计算结算日期 (YYYY-MM-DD)
    :param v0: 初始方差
    :param kappa: 均值回归速度
    :param theta: 长期方差
    :param sigma: 方差波动率
    :param rho: 资产与方差的相关系数
    :param barrier_type: 障碍类型 ('UpAndOut', 'UpAndIn', 'DownAndOut', 'DownAndIn')
    :param rebate: 障碍触发后的补偿
    :param option_type: 期权类型
    :param grid_points: 网格点数
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
        exercise = ql.EuropeanExercise(mat_date)

        # 障碍类型
        barrier_type_map = {
            "UpAndOut": ql.Barrier.UpOut,
            "UpAndIn": ql.Barrier.UpIn,
            "DownAndOut": ql.Barrier.DownOut,
            "DownAndIn": ql.Barrier.DownIn
        }
        barrier_enum = barrier_type_map.get(barrier_type, ql.Barrier.DownOut)

        option = ql.BarrierOption(barrier_enum, barrier_level, rebate, payoff, exercise)

        # 市场数据
        spot_handle = ql.QuoteHandle(ql.SimpleQuote(spot))
        day_count = ql.Actual365Fixed()

        r_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(risk_free_rate)), day_count)
        )
        d_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(dividend_yield)), day_count)
        )

        # Heston 模型
        heston_process = ql.HestonProcess(
            r_ts,
            d_ts,
            spot_handle,
            v0,
            kappa,
            theta,
            sigma,
            rho
        )
        heston_model = ql.HestonModel(heston_process)

        # 有限差分定价引擎
        engine = ql.FdHestonBarrierEngine(
            heston_model,
            ql.Fdm1dMesher.equilines,
            grid_points,
            time_steps
        )
        option.setPricingEngine(engine)

        return {
            "npv": option.NPV(),
            "barrier_type": barrier_type,
            "barrier_level": barrier_level,
            "rebate": rebate
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def calibrate_heston_model(
    settlement_date: str,
    spot: float,
    risk_free_rate: float,
    dividend_yield: float,
    market_options: List[Dict[str, Any]],
    initial_v0: float = 0.04,
    initial_kappa: float = 2.0,
    initial_theta: float = 0.04,
    initial_sigma: float = 0.3,
    initial_rho: float = -0.7
) -> Dict[str, Any]:
    """
    校准 Heston 模型参数到市场期权价格
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param spot: 标的资产价格
    :param risk_free_rate: 无风险利率（小数）
    :param dividend_yield: 资产股息率（小数）
    :param market_options: 市场期权列表 [{"strike": 100, "maturity": "2027-06-25", "market_price": 5.0, "type": "call"}, ...]
    :param initial_v0: 初始 v0 猜测值
    :param initial_kappa: 初始 kappa 猜测值
    :param initial_theta: 初始 theta 猜测值
    :param initial_sigma: 初始 sigma 猜测值
    :param initial_rho: 初始 rho 猜测值
    """
    try:
        eval_date = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = eval_date

        day_count = ql.Actual365Fixed()
        calendar = ql.NullCalendar()

        spot_handle = ql.QuoteHandle(ql.SimpleQuote(spot))
        r_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(risk_free_rate)), day_count)
        )
        d_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(dividend_yield)), day_count)
        )

        # 初始 Heston 参数
        heston_process = ql.HestonProcess(
            r_ts,
            d_ts,
            spot_handle,
            initial_v0,
            initial_kappa,
            initial_theta,
            initial_sigma,
            initial_rho
        )
        heston_model = ql.HestonModel(heston_process)

        # 创建校准助手
        calibration_helpers = []
        market_quotes = []

        for opt in market_options:
            strike = opt['strike']
            maturity = parse_date(opt['maturity'])
            market_price = opt['market_price']
            opt_type = ql.Option.Call if opt.get('type', 'call').lower() == 'call' else ql.Option.Put

            payoff = ql.PlainVanillaPayoff(opt_type, strike)
            exercise = ql.EuropeanExercise(maturity)
            helper = ql.HestonModelHelper(
                exercise,
                r_ts,
                ql.QuoteHandle(ql.SimpleQuote(spot)),
                strike,
                ql.QuoteHandle(ql.SimpleQuote(market_price))
            )
            helper.setPricingEngine(ql.AnalyticHestonEngine(heston_model))
            calibration_helpers.append(helper)
            market_quotes.append({
                "strike": strike,
                "maturity": opt['maturity'],
                "market_price": market_price
            })

        # 执行校准
        heston_model.calibrate(
            calibration_helpers,
            ql.OptimizationMethod.LevenbergMarquardt,
            ql.EndCriteria(400, 40, 1e-8, 1e-8, 1e-8)
        )

        # 获取校准后的参数
        params = heston_model.params()
        calibrated_v0 = params[0]
        calibrated_kappa = params[1]
        calibrated_theta = params[2]
        calibrated_sigma = params[3]
        calibrated_rho = params[4]

        # 计算校准误差
        calibration_errors = []
        for i, (helper, quote) in enumerate(zip(calibration_helpers, market_quotes)):
            model_price = helper.modelValue()
            market_price = quote['market_price']
            error = model_price - market_price
            calibration_errors.append({
                **quote,
                "model_price": round(model_price, 6),
                "error": round(error, 6),
                "relative_error_pct": round(error / market_price * 100, 4) if market_price > 0 else 0
            })

        total_error = sum(abs(e['error']) for e in calibration_errors)

        return {
            "status": "Success",
            "calibrated_parameters": {
                "v0": round(calibrated_v0, 6),
                "kappa": round(calibrated_kappa, 6),
                "theta": round(calibrated_theta, 6),
                "sigma": round(calibrated_sigma, 6),
                "rho": round(calibrated_rho, 6),
                "long_term_volatility": round(calibrated_theta ** 0.5, 6)
            },
            "total_absolute_error": round(total_error, 6),
            "calibration_errors": calibration_errors
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def generate_heston_volatility_surface(
    settlement_date: str,
    spot: float,
    risk_free_rate: float,
    dividend_yield: float,
    v0: float,
    kappa: float,
    theta: float,
    sigma: float,
    rho: float,
    strikes: List[float],
    maturities: List[str]
) -> Dict[str, Any]:
    """
    生成 Heston 模型隐含波动率曲面
    
    :param settlement_date: 结算日期 (YYYY-MM-DD)
    :param spot: 标的资产价格
    :param risk_free_rate: 无风险利率（小数）
    :param dividend_yield: 资产股息率（小数）
    :param v0: 初始方差
    :param kappa: 均值回归速度
    :param theta: 长期方差
    :param sigma: 方差波动率
    :param rho: 相关系数
    :param strikes: 行权价列表
    :param maturities: 到期日列表 (YYYY-MM-DD)
    """
    try:
        eval_date = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = eval_date

        day_count = ql.Actual365Fixed()
        calendar = ql.NullCalendar()

        spot_handle = ql.QuoteHandle(ql.SimpleQuote(spot))
        r_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(risk_free_rate)), day_count)
        )
        d_ts = ql.YieldTermStructureHandle(
            ql.FlatForward(eval_date, ql.QuoteHandle(ql.SimpleQuote(dividend_yield)), day_count)
        )

        # Heston 模型
        heston_process = ql.HestonProcess(
            r_ts, d_ts, spot_handle, v0, kappa, theta, sigma, rho
        )
        heston_model = ql.HestonModel(heston_process)

        # 计算波动率曲面
        vol_surface = []
        for mat_str in maturities:
            mat_date = parse_date(mat_str)
            maturity_row = []
            for strike in strikes:
                payoff = ql.PlainVanillaPayoff(ql.Option.Call, strike)
                exercise = ql.EuropeanExercise(mat_date)
                option = ql.VanillaOption(payoff, exercise)
                engine = ql.AnalyticHestonEngine(heston_model)
                option.setPricingEngine(engine)

                # 计算隐含波动率
                bsm_process = ql.BlackScholesMertonProcess(
                    spot_handle, d_ts, r_ts,
                    ql.BlackVolTermStructureHandle(
                        ql.BlackConstantVol(eval_date, calendar, ql.QuoteHandle(ql.SimpleQuote(0.2)), day_count)
                    )
                )
                try:
                    iv = option.impliedVolatility(
                        option.NPV(), bsm_process, 1e-6, 1000, 0.01, 5.0
                    )
                except:
                    iv = 0.0

                maturity_row.append(round(iv, 6))
            vol_surface.append({
                "maturity": mat_str,
                "strikes": strikes,
                "implied_volatilities": maturity_row
            })

        return {
            "heston_parameters": {
                "v0": v0,
                "kappa": kappa,
                "theta": theta,
                "sigma": sigma,
                "rho": rho
            },
            "volatility_surface": vol_surface
        }
    except Exception as e:
        return {"error": str(e)}
