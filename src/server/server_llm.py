import datetime
from typing import List, Dict, Any, Optional
import QuantLib as ql
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("QuantLib Service")

# Helper function to parse ISO date strings
def parse_date(date_str: str) -> ql.Date:
    """Parses 'YYYY-MM-DD' string to QuantLib.Date."""
    dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    return ql.Date(dt.day, dt.month, dt.year)

# ==========================================
# EXISTING TOOLS (Abbreviated for space)
# ==========================================
@mcp.tool()
def price_european_option(
    spot: float, strike: float, volatility: float, risk_free_rate: float,
    dividend_yield: float, maturity_date: str, settlement_date: str, option_type: str = "call"
) -> Dict[str, Any]:
    # ... (Keep existing implementation from Step 2)
    pass

# ==========================================
# NEW TOOLS FOR SWAPS & CALLABLE BONDS
# ==========================================

@mcp.tool()
def price_interest_rate_swap(
    settlement_date: str,
    maturity_date: str,
    fixed_rate: float,
    floating_spread: float,
    nominal: float = 10_000_000.0,
    fixed_leg_frequency: int = 1, # 1 = Annual, 2 = Semiannual
    floating_leg_frequency: int = 2, # 2 = Semiannual, 4 = Quarterly
    yield_rate: float = 0.04
) -> Dict[str, Any]:
    """
    Prices a vanilla Fixed-vs-Floating Interest Rate Swap (IRS) using a flat yield curve.
    
    :param settlement_date: Valuation/effective date (YYYY-MM-DD)
    :param maturity_date: Maturity date of the swap (YYYY-MM-DD)
    :param fixed_rate: Coupon rate of the fixed leg (decimal)
    :param floating_spread: Spread added to the floating rate (decimal)
    :param nominal: Notional amount of the contract
    :param fixed_leg_frequency: Frequency of fixed coupon payments
    :param floating_leg_frequency: Frequency of floating coupon payments
    :param yield_rate: Market reference/discount rate (decimal)
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.TARGET()
        day_counter = ql.Actual360()

        # Generate Schedules
        fixed_schedule = ql.Schedule(
            settle_d, mat_d, ql.Period(fixed_leg_frequency), calendar,
            ql.ModifiedFollowing, ql.ModifiedFollowing, ql.DateGeneration.Forward, False
        )
        floating_schedule = ql.Schedule(
            settle_d, mat_d, ql.Period(floating_leg_frequency), calendar,
            ql.ModifiedFollowing, ql.ModifiedFollowing, ql.DateGeneration.Forward, False
        )

        # Index and Term Structure
        discount_curve = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(yield_rate)), day_counter)
        )
        index = ql.Euribor(ql.Period(floating_leg_frequency), discount_curve)

        # Create Swap
        swap = ql.VanillaSwap(
            ql.VanillaSwap.Payer,
            nominal,
            fixed_schedule,
            fixed_rate,
            day_counter,
            floating_schedule,
            index,
            floating_spread,
            day_counter
        )

        # Pricing Engine
        engine = ql.DiscountingSwapEngine(discount_curve)
        swap.setPricingEngine(engine)

        return {
            "npv": swap.NPV(),
            "fair_rate": swap.fairRate(),
            "fair_spread": swap.fairSpread(),
            "fixed_leg_npv": swap.fixedLegNPV(),
            "floating_leg_npv": swap.floatingLegNPV()
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
    Prices a Callable Fixed-Rate Bond using the Hull-White one-factor short-rate model on a lattice.
    
    :param settlement_date: Calculation settlement date (YYYY-MM-DD)
    :param maturity_date: Bond maturity date (YYYY-MM-DD)
    :param coupon_rate: Coupon rate (decimal)
    :param call_price: Price at which issuer can call the bond (typically 100.0 or 101.0)
    :param call_date: Date the bond becomes callable (YYYY-MM-DD)
    :param yield_rate: Flat curve reference rate (decimal)
    :param hull_white_a: Mean reversion speed parameter for the Hull-White model
    :param hull_white_sigma: Volatility parameter for the Hull-White model
    """
    try:
        settle_d = parse_date(settlement_date)
        mat_d = parse_date(maturity_date)
        call_d = parse_date(call_date)
        ql.Settings.instance().evaluationDate = settle_d

        calendar = ql.UnitedStates(ql.UnitedStates.GovernmentBond)
        day_counter = ql.Thirty360(ql.Thirty360.USA)

        # Generate payment schedule
        schedule = ql.Schedule(
            settle_d, mat_d, ql.Period(frequency), calendar,
            ql.Unadjusted, ql.Unadjusted, ql.DateGeneration.Backward, False
        )

        # Create Callability Schedule
        null_calendar = ql.NullCalendar()
        callability_price = ql.BondPrice(call_price, ql.BondPrice.Clean)
        callability = ql.Callability(callability_price, ql.Callability.Call, call_d)
        callability_schedule = ql.CallabilitySchedule([callability])

        # Define Callable Bond
        # QuantLib uses 0 settlement days to match pricing to the direct settlement date
        bond = ql.CallableFixedRateBond(
            0, face_value, schedule, [coupon_rate], day_counter,
            ql.Following, face_value, mat_d, callability_schedule
        )

        # Set up Flat Yield Curve and Short-rate Model
        term_structure = ql.YieldTermStructureHandle(
            ql.FlatForward(settle_d, ql.QuoteHandle(ql.SimpleQuote(yield_rate)), day_counter)
        )
        model = ql.HullWhite(term_structure, hull_white_a, hull_white_sigma)
        
        # Hull-White Tree Pricing Engine
        grid_steps = 40
        engine = ql.TreeCallableFixedRateBondEngine(model, grid_steps)
        bond.setPricingEngine(engine)

        return {
            "npv": bond.NPV(),
            "clean_price": bond.cleanPrice(),
            "dirty_price": bond.dirtyPrice(),
            "accrued_amount": bond.accruedAmount()
        }
    except Exception as e:
        return {"error": str(e)}


# ==========================================
# PROMPT TEMPLATES
# ==========================================

@mcp.prompt()
def create_interest_rate_swap(
    notional: float = 10000000.0,
    currency: str = "USD"
) -> str:
    """
    Generates a prompt template guiding the user to structure and price an Interest Rate Swap (IRS).
    """
    return f"""
You want to analyze or create an Interest Rate Swap with a Notional of {currency} {notional:,.2f}.

To do this, we need to gather or assume some key parameters:
1. **Settlement/Effective Date**: Usually today or a spot date.
2. **Maturity/Tenor**: e.g., 5 Years, 10 Years.
3. **Fixed Rate**: The rate paid by the fixed leg.
4. **Floating Spread**: The margin added to the index (often 0.0).
5. **Yield/Discount Curve**: The reference market rate to discount future cash flows.

Please reply with the dates and rates you would like to use. If you are unsure, let me know, and I can suggest a standard market setup and invoke the `price_interest_rate_swap` tool to calculate the Fair Swap Rate and Leg NPVs for you.
"""


@mcp.prompt()
def price_callable_bond_workflow(
    maturity_years: int = 10,
    face_value: float = 100.0
) -> str:
    """
    Generates a prompt template guiding the user through the valuation of a callable bond using Hull-White.
    """
    return f"""
You are looking to price a Callable Fixed-Rate Bond with a face value of {face_value} and a tentative maturity of {maturity_years} years.

Valuing a callable bond requires a short-rate framework because the embedded option value is sensitive to the path of interest rates. We will use the **Hull-White One-Factor Model**.

To perform this pricing, we need:
1. **Dates**: Settlement date, Maturity date, and the Call Date (when the issuer can first exercise).
2. **Rates**: Coupon Rate and the current yield curve (as a flat reference rate).
3. **Model Parameters**: 
   - Mean reversion speed ($a$, default: 0.03)
   - Short-rate volatility ($\sigma$, default: 0.012)
   - Call price (typically 100.0 or 101.0)

Please provide these values, or ask me to prepare a benchmark scenario (e.g., a bond callable in 5 years). I will then use the `price_callable_bond` tool to determine the option-adjusted clean and dirty prices.
"""

if __name__ == "__main__":
    # If called by mcp dev, export the official Server object
    import sys
    if "mcp" in sys.modules and hasattr(mcp, "_server"):
        # fastmcp has an official Server object embedded, expose it
        mcp._server.run()
    else:
        # If called by manual python server.py, use fastmcp's own startup
        mcp.run()