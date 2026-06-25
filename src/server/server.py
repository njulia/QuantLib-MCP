import datetime
from typing import List, Dict, Any
import QuantLib as ql
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("QuantLib Service")

# 导出所有工具模块，供工具文件共享 mcp 实例
__all__ = ['mcp', 'bonds', 'swaps', 'options', 'volatility', 'credit', 'money_market']

# 导入所有工具模块（这些模块会使用上面的 mcp 实例注册工具）
from .tools import bonds
from .tools import swaps
from .tools import options
from .tools import volatility
from .tools import credit
from .tools import money_market

# Helper function to parse ISO date strings
def parse_date(date_str: str) -> ql.Date:
    """Parses 'YYYY-MM-DD' string to QuantLib.Date."""
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    return ql.Date(dt.day, dt.month, dt.year)

@mcp.tool()
def price_european_option(
    spot: float,
    strike: float,
    volatility: float,
    risk_free_rate: float,
    dividend_yield: float,
    maturity_date: str,
    settlement_date: str,
    option_type: str = "call"
) -> Dict[str, Any]:
    """
    Prices a European option and calculates Greeks using the Black-Scholes-Merton model.
    
    :param spot: Current asset price
    :param strike: Option strike price
    :param volatility: Asset volatility (decimal, e.g., 0.20 for 20%)
    :param risk_free_rate: Risk-free interest rate (decimal)
    :param dividend_yield: Asset dividend yield (decimal)
    :param maturity_date: Option expiration date (YYYY-MM-DD)
    :param settlement_date: Calculation settlement date (YYYY-MM-DD)
    :param option_type: "call" or "put"
    """
    try:
        # Set evaluation date
        eval_date = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = eval_date

        # Option setup
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

        # Market data processes
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
        
        # Engine assignment
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
def price_fixed_rate_bond(
    settlement_date: str,
    maturity_date: str,
    coupon_rate: float,
    yield_rate: float,
    frequency: int = 2,
    face_value: float = 100.0,
    day_count_convention: str = "Thirty360"
) -> Dict[str, Any]:
    """
    Prices a fixed-rate bond and calculates analytical properties like duration and convexity.
    
    :param settlement_date: Date of bond purchase/settlement (YYYY-MM-DD)
    :param maturity_date: Bond maturity date (YYYY-MM-DD)
    :param coupon_rate: Annual coupon rate (decimal, e.g., 0.05 for 5%)
    :param yield_rate: Market yield to maturity (decimal)
    :param frequency: Coupon payments per year (1=annual, 2=semiannual, 4=quarterly)
    :param face_value: Bond par value
    :param day_count_convention: 'Thirty360' or 'Actual365Fixed'
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        ql.Settings.instance().evaluationDate = settle_d

        # Calendar and Day counter
        calendar = ql.UnitedStates(ql.UnitedStates.GovernmentBond)
        
        if day_count_convention == "Actual365Fixed":
            day_counter = ql.Actual365Fixed()
        else:
            day_counter = ql.Thirty360(ql.Thirty360.USA)

        # Coupon schedule
        tenor = ql.Period(frequency)
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

        # Create Fixed Rate Bond
        coupons = [coupon_rate]
        bond = ql.FixedRateBond(
            0, # settlement days
            face_value,
            schedule,
            coupons,
            day_counter
        )

        # Flat yield term structure for pricing
        interest_rate = ql.InterestRate(yield_rate, day_counter, ql.Compounded, frequency)
        
        clean_price = bond.cleanPrice(yield_rate, day_counter, ql.Compounded, frequency)
        dirty_price = bond.dirtyPrice(yield_rate, day_counter, ql.Compounded, frequency)
        
        # Risk measures
        duration = ql.BondFunctions.duration(bond, interest_rate, ql.Duration.Modified)
        convexity = ql.BondFunctions.convexity(bond, interest_rate)

        return {
            "clean_price": clean_price,
            "dirty_price": dirty_price,
            "accrued_amount": bond.accruedAmount(),
            "modified_duration": duration,
            "convexity": convexity
        }
    except Exception as e:
        return {"error": str(e)}


@mcp.tool()
def bootstrap_yield_curve(
    settlement_date: str,
    helpers_data: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Bootstraps a zero-coupon yield curve using market rate helpers (deposits and swaps).
    
    :param settlement_date: Curve reference/settlement date (YYYY-MM-DD)
    :param helpers_data: List of instruments with 'type' ('deposit' or 'swap'), 'tenor' (e.g. '3M', '5Y'), and 'rate' (decimal)
    """
    try:
        settle_d = parse_date(settlement_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.TARGET()
        day_count = ql.Actual360()

        instruments = []
        for h in helpers_data:
            rate = h['rate']
            tenor_str = h['tenor']
            inst_type = h['type'].lower()

            # Parse tenor string (e.g., "6M" -> ql.Period(6, ql.Months))
            val = int(tenor_str[:-1])
            unit_char = tenor_str[-1].upper()
            if unit_char == 'M':
                tenor = ql.Period(val, ql.Months)
            elif unit_char == 'Y':
                tenor = ql.Period(val, ql.Years)
            else:
                tenor = ql.Period(val, ql.Days)

            if inst_type == "deposit":
                helper = ql.DepositRateHelper(
                    ql.QuoteHandle(ql.SimpleQuote(rate)),
                    tenor,
                    2, # fixing days
                    calendar,
                    ql.ModifiedFollowing,
                    False,
                    day_count
                )
            elif inst_type == "swap":
                # Basic swap helper assumptions
                sw_freq = ql.Annual
                sw_convention = ql.ModifiedFollowing
                sw_daycount = ql.Thirty360(ql.Thirty360.BondBasis)
                index = ql.Euribor(ql.Period(6, ql.Months)) # Reference index
                
                helper = ql.SwapRateHelper(
                    ql.QuoteHandle(ql.SimpleQuote(rate)),
                    tenor,
                    calendar,
                    sw_freq,
                    sw_convention,
                    sw_daycount,
                    index
                )
            else:
                continue
            instruments.append(helper)

        # Bootstrap curve
        yield_curve = ql.PiecewiseFlatForward(settle_d, instruments, ql.Actual365Fixed())
        
        # Sample zero rates at year marks to return
        curve_nodes = {}
        for years in range(1, 11):
            target_date = settle_d + ql.Period(years, ql.Years)
            zero_rate = yield_curve.zeroRate(target_date, ql.Actual365Fixed(), ql.Continuous).value()
            curve_nodes[f"{years}Y"] = zero_rate

        return {
            "status": "Success",
            "zero_rates_365_continuous": curve_nodes
        }
    except Exception as e:
        return {"error": str(e)}


if __name__ == "__main__":
    # If called by mcp dev, export the official Server object
    import sys
    if "mcp" in sys.modules and hasattr(mcp, "_server"):
        # fastmcp has an official Server object embedded, expose it
        mcp._server.run()
    else:
        # If called by manual python server.py, use fastmcp's own startup
        mcp.run()