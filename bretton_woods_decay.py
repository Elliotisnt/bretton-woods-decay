"""
Bretton Woods Decay - Quarterly Macro Indicator Monitor
========================================================
Tracks key indicators of US dollar/empire structural health:

1. USD share of global foreign exchange reserves (IMF COFER via DBnomics)
2. China holdings of US Treasuries (Treasury TIC)
3. Japan holdings of US Treasuries (Treasury TIC)
4. DXY Dollar Index (Yahoo Finance)
5. US Debt-to-GDP ratio (FRED)
6. Federal interest payments as % of revenue (FRED - quarterly BEA)
7. Interest vs defense spending - Guns vs Debt (FRED)
8. Trade balance as % of GDP (FRED)
9. Empire Premium - VTI/VXUS Price-to-Book spread (Yahoo Finance)

Plus informational context:
- International vs US stock performance (VXUS vs VTI)

Designed to run quarterly (Jan, Apr, Jul, Oct) via GitHub Actions.
Sends a formatted email report via iCloud SMTP.

Developed with assistance from Claude Opus 4.5
"""

import os
import re
import requests
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

# =============================================================================
# CONFIGURATION
# =============================================================================

ICLOUD_EMAIL = os.environ.get("ICLOUD_EMAIL")
ICLOUD_PASSWORD = os.environ.get("ICLOUD_PASSWORD")
TO_EMAIL = os.environ.get("TO_EMAIL", ICLOUD_EMAIL)

HEADERS = {
    "User-Agent": "BrettonWoodsDecay/3.0 (github.com/bretton-woods-decay)",
    "Accept": "application/json"
}

# Thresholds: (warning, critical, direction)
# direction: "below" means warning if value drops below threshold
#            "above" means warning if value rises above threshold
THRESHOLDS = {
    "usd_reserve_share": {
        "warning": 55.0,
        "critical": 50.0,
        "direction": "below",
        "unit": "%",
        "description": "USD share of global FX reserves",
        "context": "Peaked at 71% in 2000. Declined to ~58% by 2024. Below 50% would be unprecedented since tracking began in 1999."
    },
    "china_treasury": {
        "warning": 700.0,
        "critical": 500.0,
        "direction": "below",
        "unit": "B",
        "description": "China holdings of US Treasuries",
        "context": "Peaked at $1.32T in Nov 2013. Has been steadily declining since 2018. Below $500B would signal aggressive divestment."
    },
    "japan_treasury": {
        "warning": 1000.0,
        "critical": 850.0,
        "direction": "below",
        "unit": "B",
        "description": "Japan holdings of US Treasuries",
        "context": "Largest foreign holder. Peaked at $1.29T in Nov 2021. Selling often reflects yen defense rather than dedollarization."
    },
    "dxy": {
        "warning": 90.0,
        "critical": 80.0,
        "direction": "below",
        "unit": "",
        "description": "Dollar Index (DXY)",
        "context": "Created 1973 at 100. All-time high: 164.7 (Feb 1985). All-time low: 70.7 (Mar 2008). Measures USD vs EUR (57.6%), JPY (13.6%), GBP (11.9%), CAD (9.1%), SEK (4.2%), CHF (3.6%)."
    },
    "debt_to_gdp": {
        "warning": 130.0,
        "critical": 150.0,
        "direction": "above",
        "unit": "%",
        "description": "US Federal Debt to GDP ratio",
        "context": "Was 55% in 2000, crossed 100% in 2013, peaked at 126% in 2020. For comparison: Japan ~260%, Italy ~140%, UK ~100%, Germany ~65%."
    },
    "interest_to_revenue": {
        "warning": 20.0,
        "critical": 22.0,
        "direction": "above",
        "unit": "%",
        "description": "Federal interest payments as % of revenue",
        "context": "Previous peak was ~18% in 1991. Fell to ~6% by 2015 due to low rates. In 2025, Japan at ~260% debt/GDP only pays ~8% of revenue to interest due to BoJ ownership and near-zero rates."
    },
    "interest_to_defense": {
        "warning": 100.0,
        "critical": 120.0,
        "direction": "above",
        "unit": "%",
        "description": "Interest payments vs defense spending (Guns vs Debt)",
        "context": "Crossed 100% for the first time in 2024 (~$880B interest vs ~$820B defense). Great powers historically decline when debt service exceeds military spending, true of Hapsburg Spain, ancien régime France, the Ottoman Empire, and the British Empire."
    },
    "trade_balance_gdp": {
        "warning": -1.5,
        "critical": -0.5,
        "direction": "above",
        "unit": "%",
        "description": "Trade balance as % of GDP",
        "context": "The US has run continuous deficits since 1976. Peak deficit was -5.7% in 2006. A rapid move toward zero (less negative) would signal the world is no longer willing to finance US consumption."
    }
}

# =============================================================================
# DATA FETCHING FUNCTIONS
# =============================================================================

def fetch_imf_cofer():
    """
    Fetch USD share of global reserves from DBnomics (mirrors IMF COFER).
    Uses quarterly data: Q.W00.RAXGFXARUSDRT_PT
    """
    try:
        # DBnomics API for IMF COFER - USD share of allocated reserves (quarterly)
        url = "https://api.db.nomics.world/v22/series/IMF/COFER/Q.W00.RAXGFXARUSDRT_PT?observations=1"
        response = requests.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            series = data.get("series", {})
            docs = series.get("docs", [])
            
            if docs:
                doc = docs[0]
                periods = doc.get("period", [])
                values = doc.get("value", [])
                indexed_at = doc.get("indexed_at", "")
                
                # DBnomics indexed_at is when they last updated from IMF
                data_freshness = "Unknown"
                if indexed_at:
                    try:
                        # Parse ISO format
                        if "T" in indexed_at:
                            dt = datetime.fromisoformat(indexed_at.replace("Z", "+00:00"))
                            data_freshness = dt.strftime("%Y-%m-%d")
                    except:
                        data_freshness = indexed_at[:10] if len(indexed_at) >= 10 else indexed_at
                
                if periods and values:
                    # Get latest non-null value
                    latest_idx = len(values) - 1
                    while latest_idx >= 0 and values[latest_idx] is None:
                        latest_idx -= 1
                    
                    if latest_idx >= 0:
                        current = float(values[latest_idx])
                        period = periods[latest_idx]
                        
                        # Get 1-year ago (4 quarters back)
                        year_ago = None
                        year_ago_period = None
                        if latest_idx >= 4:
                            year_ago = float(values[latest_idx - 4]) if values[latest_idx - 4] is not None else None
                            year_ago_period = periods[latest_idx - 4]
                        
                        # Get 5-years ago (20 quarters back)
                        five_year_ago = None
                        five_year_period = None
                        if latest_idx >= 20:
                            five_year_ago = float(values[latest_idx - 20]) if values[latest_idx - 20] is not None else None
                            five_year_period = periods[latest_idx - 20]
                        
                        return {
                            "success": True,
                            "value": round(current, 1),
                            "period": period,
                            "year_ago": round(year_ago, 1) if year_ago else None,
                            "year_ago_period": year_ago_period,
                            "five_year_ago": round(five_year_ago, 1) if five_year_ago else None,
                            "five_year_period": five_year_period,
                            "change_1y": round(current - year_ago, 2) if year_ago else None,
                            "change_5y": round(current - five_year_ago, 2) if five_year_ago else None,
                            "data_freshness": data_freshness,
                            "source": "IMF COFER via DBnomics"
                        }
        
        # Try fallback: direct IMF API
        return fetch_imf_cofer_direct()
        
    except Exception as e:
        return fetch_imf_cofer_direct()


def fetch_imf_cofer_direct():
    """Fallback: try direct IMF API."""
    try:
        url = "https://dataservices.imf.org/REST/SDMX_JSON.svc/CompactData/COFER/Q.W00.RAXGFXARUSDRT_PT"
        response = requests.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            series = data.get("CompactData", {}).get("DataSet", {}).get("Series", {})
            observations = series.get("Obs", [])
            
            if isinstance(observations, dict):
                observations = [observations]
            
            if observations:
                latest = observations[-1]
                current = float(latest.get("@OBS_VALUE", 0))
                period = latest.get("@TIME_PERIOD", "Unknown")
                
                year_ago = float(observations[-5].get("@OBS_VALUE", 0)) if len(observations) >= 5 else None
                five_year_ago = float(observations[-21].get("@OBS_VALUE", 0)) if len(observations) >= 21 else None
                
                return {
                    "success": True,
                    "value": round(current, 1),
                    "period": period,
                    "year_ago": round(year_ago, 1) if year_ago else None,
                    "five_year_ago": round(five_year_ago, 1) if five_year_ago else None,
                    "change_1y": round(current - year_ago, 2) if year_ago else None,
                    "change_5y": round(current - five_year_ago, 2) if five_year_ago else None,
                    "data_freshness": "Live from IMF",
                    "source": "IMF COFER direct API"
                }
        
        return {"success": False, "error": "IMF API unavailable", "source": "IMF COFER"}
    except Exception as e:
        return {"success": False, "error": str(e), "source": "IMF COFER"}


def fetch_treasury_holdings():
    """
    Fetch China and Japan Treasury holdings from Treasury TIC data.
    Uses the newer slt_table5.txt file which is actively updated monthly.
    Data is released monthly with ~6 week lag.
    """
    try:
        # Use the newer SLT table 5 file (updated monthly)
        url = "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table5.txt"
        response = requests.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            
            china_data = None
            japan_data = None
            data_date = None
            date_columns = []
            
            for line in lines:
                # Skip empty lines and notes
                if not line.strip():
                    continue
                if line.startswith('Table 5:') or line.startswith('Holdings at') or line.startswith('Billions') or line.startswith('Link:'):
                    continue
                if line.startswith('Notes:') or line.startswith('The data in') or line.startswith('overseas') or line.startswith('(see TIC'):
                    continue
                if line.startswith('Estimated') or line.startswith('International') or line.startswith('as reported') or line.startswith('and on TIC'):
                    continue
                
                # Tab-separated data
                parts = line.split('\t')
                
                # Header row with dates (Country, 2025-09, 2025-08, ...)
                if parts[0].strip() == 'Country':
                    date_columns = [p.strip() for p in parts[1:] if p.strip()]
                    if date_columns:
                        data_date = date_columns[0]  # Most recent date
                    continue
                
                # Parse country rows
                country = parts[0].strip().lower()
                
                if country == 'japan':
                    values = []
                    for p in parts[1:]:
                        p = p.strip()
                        if p:
                            try:
                                values.append(float(p.replace(',', '')))
                            except ValueError:
                                values.append(None)
                    
                    if values and values[0] is not None:
                        japan_data = {
                            "current": values[0],
                            "6mo_ago": values[6] if len(values) > 6 and values[6] is not None else None,
                            "12mo_ago": values[12] if len(values) > 12 and values[12] is not None else None
                        }
                
                if country == 'china, mainland':
                    values = []
                    for p in parts[1:]:
                        p = p.strip()
                        if p:
                            try:
                                values.append(float(p.replace(',', '')))
                            except ValueError:
                                values.append(None)
                    
                    if values and values[0] is not None:
                        china_data = {
                            "current": values[0],
                            "6mo_ago": values[6] if len(values) > 6 and values[6] is not None else None,
                            "12mo_ago": values[12] if len(values) > 12 and values[12] is not None else None
                        }
            
            result = {
                "success": True, 
                "data_date": data_date,
                "data_freshness": data_date if data_date else "Unknown",
                "source": "Treasury TIC SLT Table 5"
            }
            
            if china_data:
                china_data["change_6mo"] = round(china_data["current"] - china_data["6mo_ago"], 1) if china_data["6mo_ago"] else None
                china_data["change_12mo"] = round(china_data["current"] - china_data["12mo_ago"], 1) if china_data["12mo_ago"] else None
                china_data["data_freshness"] = data_date
                china_data["source"] = "Treasury TIC SLT Table 5"
                result["china"] = china_data
            
            if japan_data:
                japan_data["change_6mo"] = round(japan_data["current"] - japan_data["6mo_ago"], 1) if japan_data["6mo_ago"] else None
                japan_data["change_12mo"] = round(japan_data["current"] - japan_data["12mo_ago"], 1) if japan_data["12mo_ago"] else None
                japan_data["data_freshness"] = data_date
                japan_data["source"] = "Treasury TIC SLT Table 5"
                result["japan"] = japan_data
            
            return result
        
        return {"success": False, "error": f"API returned status {response.status_code}", "source": "Treasury TIC"}
    except Exception as e:
        return {"success": False, "error": str(e), "source": "Treasury TIC"}


def fetch_fred_series(series_id, name):
    """Fetch a data series from FRED (no API key needed for basic CSV access)."""
    try:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        response = requests.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            if len(lines) > 1:
                # Get latest value (last non-empty line)
                for line in reversed(lines[1:]):
                    parts = line.split(',')
                    if len(parts) >= 2 and parts[1].strip() and parts[1] != '.':
                        date = parts[0]
                        value = float(parts[1])
                        return {
                            "success": True,
                            "value": value,
                            "date": date,
                            "data_freshness": date,
                            "source": f"FRED ({series_id})",
                            "name": name
                        }
        
        return {"success": False, "error": f"Could not fetch {name}", "source": f"FRED ({series_id})", "name": name}
    except Exception as e:
        return {"success": False, "error": str(e), "source": f"FRED ({series_id})", "name": name}


def fetch_debt_to_gdp():
    """Fetch US Federal Debt to GDP ratio from FRED."""
    result = fetch_fred_series("GFDEGDQ188S", "Debt-to-GDP")
    if result.get("success"):
        result["value"] = round(result["value"], 1)
    return result


def fetch_interest_to_revenue():
    """
    Calculate interest payments as % of revenue using OMB fiscal year data.
    FYOINT = Federal Outlays: Interest (fiscal year, millions)
    FYFR = Federal Receipts (fiscal year, millions)
    This matches Treasury's reported ~19% figure for FY2025.
    """
    try:
        # OMB fiscal year data (annual, updated each fiscal year)
        interest_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FYOINT"
        revenue_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FYFR"
        
        interest_resp = requests.get(interest_url, headers=HEADERS, timeout=30)
        revenue_resp = requests.get(revenue_url, headers=HEADERS, timeout=30)
        
        if interest_resp.status_code == 200 and revenue_resp.status_code == 200:
            def get_values(text):
                """Get all values as list of (date, value) tuples."""
                lines = text.strip().split('\n')
                values = []
                for line in lines[1:]:
                    parts = line.split(',')
                    if len(parts) >= 2 and parts[1].strip() and parts[1] != '.':
                        values.append((parts[0], float(parts[1])))
                return values
            
            interest_vals = get_values(interest_resp.text)
            revenue_vals = get_values(revenue_resp.text)
            
            if interest_vals and revenue_vals:
                # Get latest values
                interest_date, interest = interest_vals[-1]
                revenue_date, revenue = revenue_vals[-1]
                
                # Calculate ratio
                ratio = (interest / revenue) * 100
                
                # Get historical values for context
                year_ago_ratio = None
                five_year_ratio = None
                
                if len(interest_vals) >= 2 and len(revenue_vals) >= 2:
                    year_ago_ratio = (interest_vals[-2][1] / revenue_vals[-2][1]) * 100
                
                if len(interest_vals) >= 6 and len(revenue_vals) >= 6:
                    five_year_ratio = (interest_vals[-6][1] / revenue_vals[-6][1]) * 100
                
                return {
                    "success": True,
                    "value": round(ratio, 1),
                    "interest": round(interest / 1000, 1),  # Convert to billions
                    "revenue": round(revenue / 1000, 1),    # Convert to billions
                    "date": interest_date,
                    "data_freshness": f"FY {interest_date[:4]}",
                    "source": "FRED (FYOINT / FYFR)",
                    "year_ago": round(year_ago_ratio, 1) if year_ago_ratio else None,
                    "five_year_ago": round(five_year_ratio, 1) if five_year_ratio else None,
                    "change_1y": round(ratio - year_ago_ratio, 1) if year_ago_ratio else None,
                    "change_5y": round(ratio - five_year_ratio, 1) if five_year_ratio else None
                }
        
        return {"success": False, "error": "Could not calculate interest/revenue ratio", "source": "FRED"}
    except Exception as e:
        return {"success": False, "error": str(e), "source": "FRED"}

def fetch_dxy():
    """
    Fetch DXY Dollar Index from Yahoo Finance.
    DXY measures USD against a basket of 6 currencies.
    """
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?interval=1d&range=5y"
        headers = {**HEADERS, "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            result = data.get("chart", {}).get("result", [{}])[0]
            
            closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            timestamps = result.get("timestamp", [])
            
            # Filter out None values
            valid_data = [(t, c) for t, c in zip(timestamps, closes) if c is not None]
            
            if valid_data:
                latest_ts, current = valid_data[-1]
                latest_date = datetime.fromtimestamp(latest_ts).strftime("%Y-%m-%d")
                
                # Get 1 year ago (roughly 252 trading days)
                year_ago = valid_data[-252][1] if len(valid_data) > 252 else None
                year_ago_date = datetime.fromtimestamp(valid_data[-252][0]).strftime("%Y-%m-%d") if len(valid_data) > 252 else None
                
                # Get 3 years ago
                three_year_ago = valid_data[-756][1] if len(valid_data) > 756 else None
                three_year_date = datetime.fromtimestamp(valid_data[-756][0]).strftime("%Y-%m-%d") if len(valid_data) > 756 else None
                
                # Calculate percentage changes
                change_1y_pct = ((current - year_ago) / year_ago * 100) if year_ago else None
                change_3y_pct = ((current - three_year_ago) / three_year_ago * 100) if three_year_ago else None
                
                return {
                    "success": True,
                    "value": round(current, 2),
                    "date": latest_date,
                    "data_freshness": f"Live (as of {latest_date})",
                    "year_ago": round(year_ago, 2) if year_ago else None,
                    "year_ago_date": year_ago_date,
                    "three_year_ago": round(three_year_ago, 2) if three_year_ago else None,
                    "three_year_date": three_year_date,
                    "change_1y": round(change_1y_pct, 1) if change_1y_pct else None,
                    "change_3y": round(change_3y_pct, 1) if change_3y_pct else None,
                    "source": "Yahoo Finance (DX-Y.NYB)"
                }
        
        return {"success": False, "error": f"Could not fetch DXY (status {response.status_code})", "source": "Yahoo Finance"}
    except Exception as e:
        return {"success": False, "error": str(e), "source": "Yahoo Finance"}


def fetch_intl_vs_us_performance():
    """
    Compare international vs US stock performance.
    VXUS = Vanguard Total International Stock ETF (ex-US) - proxy for FTIHX
    VTI = Vanguard Total Stock Market ETF (US) - proxy for FXAIX
    
    VXUS explicitly excludes US stocks, so this gives a clean comparison.
    """
    try:
        def get_prices(symbol):
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=5y"
            headers = {**HEADERS, "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                result = data.get("chart", {}).get("result", [{}])[0]
                closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
                timestamps = result.get("timestamp", [])
                
                valid = [(t, c) for t, c in zip(timestamps, closes) if c is not None]
                return valid
            return []
        
        vxus_data = get_prices("VXUS")
        vti_data = get_prices("VTI")
        
        if vxus_data and vti_data:
            vxus_current = vxus_data[-1][1]
            vti_current = vti_data[-1][1]
            latest_date = datetime.fromtimestamp(vxus_data[-1][0]).strftime("%Y-%m-%d")
            
            # 1 year ago
            vxus_1y = vxus_data[-252][1] if len(vxus_data) > 252 else None
            vti_1y = vti_data[-252][1] if len(vti_data) > 252 else None
            
            # 3 years ago
            vxus_3y = vxus_data[-756][1] if len(vxus_data) > 756 else None
            vti_3y = vti_data[-756][1] if len(vti_data) > 756 else None
            
            result = {
                "success": True,
                "date": latest_date,
                "data_freshness": f"Live (as of {latest_date})",
                "source": "Yahoo Finance (VXUS vs VTI)"
            }
            
            # Calculate returns (positive = international outperforming)
            if vxus_1y and vti_1y:
                vxus_return_1y = ((vxus_current / vxus_1y) - 1) * 100
                vti_return_1y = ((vti_current / vti_1y) - 1) * 100
                result["diff_1y"] = round(vxus_return_1y - vti_return_1y, 1)
                result["intl_return_1y"] = round(vxus_return_1y, 1)
                result["us_return_1y"] = round(vti_return_1y, 1)
            
            if vxus_3y and vti_3y:
                vxus_return_3y = ((vxus_current / vxus_3y) - 1) * 100
                vti_return_3y = ((vti_current / vti_3y) - 1) * 100
                result["diff_3y"] = round(vxus_return_3y - vti_return_3y, 1)
                result["intl_return_3y"] = round(vxus_return_3y, 1)
                result["us_return_3y"] = round(vti_return_3y, 1)
                result["value"] = result["diff_3y"]  # Primary metric
            
            return result
        
        return {"success": False, "error": "Could not fetch ETF data", "source": "Yahoo Finance"}
    except Exception as e:
        return {"success": False, "error": str(e), "source": "Yahoo Finance"}

def fetch_interest_to_defense():
    """
    Calculate interest payments vs defense spending ratio.
    A091RC1Q027SBEA = Federal interest payments (quarterly SAAR, billions)
    FDEFX = National defense consumption & investment (quarterly SAAR, billions)
    """
    try:
        interest_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=A091RC1Q027SBEA"
        defense_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FDEFX"
        
        interest_resp = requests.get(interest_url, headers=HEADERS, timeout=30)
        defense_resp = requests.get(defense_url, headers=HEADERS, timeout=30)
        
        if interest_resp.status_code == 200 and defense_resp.status_code == 200:
            def get_values(text):
                lines = text.strip().split('\n')
                values = []
                for line in lines[1:]:
                    parts = line.split(',')
                    if len(parts) >= 2 and parts[1].strip() and parts[1] != '.':
                        values.append((parts[0], float(parts[1])))
                return values
            
            interest_vals = get_values(interest_resp.text)
            defense_vals = get_values(defense_resp.text)
            
            if interest_vals and defense_vals:
                interest_date, interest = interest_vals[-1]
                defense_date, defense = defense_vals[-1]
                
                ratio = (interest / defense) * 100
                
                year_ago_ratio = None
                if len(interest_vals) >= 5 and len(defense_vals) >= 5:
                    year_ago_ratio = (interest_vals[-5][1] / defense_vals[-5][1]) * 100
                
                return {
                    "success": True,
                    "value": round(ratio, 1),
                    "interest": round(interest, 1),
                    "defense": round(defense, 1),
                    "date": interest_date,
                    "data_freshness": interest_date,
                    "source": "FRED (A091RC1Q027SBEA / FDEFX)",
                    "year_ago": round(year_ago_ratio, 1) if year_ago_ratio else None,
                    "change_1y": round(ratio - year_ago_ratio, 1) if year_ago_ratio else None
                }
        
        return {"success": False, "error": "Could not fetch interest/defense data", "source": "FRED"}
    except Exception as e:
        return {"success": False, "error": str(e), "source": "FRED"}


def fetch_trade_balance_gdp():
    """
    Calculate trade balance as % of GDP.
    BOPGSTB = Trade balance goods & services (monthly, millions)
    GDP = Gross Domestic Product (quarterly, billions)
    """
    try:
        trade_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=BOPGSTB"
        gdp_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GDP"
        
        trade_resp = requests.get(trade_url, headers=HEADERS, timeout=30)
        gdp_resp = requests.get(gdp_url, headers=HEADERS, timeout=30)
        
        if trade_resp.status_code == 200 and gdp_resp.status_code == 200:
            def get_values(text):
                lines = text.strip().split('\n')
                values = []
                for line in lines[1:]:
                    parts = line.split(',')
                    if len(parts) >= 2 and parts[1].strip() and parts[1] != '.':
                        values.append((parts[0], float(parts[1])))
                return values
            
            trade_vals = get_values(trade_resp.text)
            gdp_vals = get_values(gdp_resp.text)
            
            if trade_vals and gdp_vals:
                # Average last 3 months of trade data
                recent_trade = trade_vals[-3:] if len(trade_vals) >= 3 else trade_vals
                avg_trade = sum(v[1] for v in recent_trade) / len(recent_trade)
                trade_date = recent_trade[-1][0]
                
                # Get latest GDP
                gdp_date, gdp = gdp_vals[-1]
                
                # Convert trade from millions to billions, then calculate ratio
                # BOPGSTB is monthly, so annualize by multiplying by 12
                trade_annual_billions = (avg_trade / 1000) * 12
                ratio = (trade_annual_billions / gdp) * 100
                
                # Year ago comparison
                year_ago_ratio = None
                if len(trade_vals) >= 15 and len(gdp_vals) >= 5:
                    year_ago_trade = trade_vals[-15:-12] if len(trade_vals) >= 15 else None
                    if year_ago_trade:
                        avg_trade_1y = sum(v[1] for v in year_ago_trade) / len(year_ago_trade)
                        trade_1y_annual = (avg_trade_1y / 1000) * 12
                        gdp_1y = gdp_vals[-5][1]
                        year_ago_ratio = (trade_1y_annual / gdp_1y) * 100
                
                return {
                    "success": True,
                    "value": round(ratio, 2),
                    "trade_balance": round(trade_annual_billions, 1),
                    "gdp": round(gdp, 1),
                    "date": trade_date,
                    "data_freshness": trade_date,
                    "source": "FRED (BOPGSTB / GDP)",
                    "year_ago": round(year_ago_ratio, 2) if year_ago_ratio else None,
                    "change_1y": round(ratio - year_ago_ratio, 2) if year_ago_ratio else None
                }
        
        return {"success": False, "error": "Could not fetch trade balance/GDP data", "source": "FRED"}
    except Exception as e:
        return {"success": False, "error": str(e), "source": "FRED"}

# =============================================================================
# ANALYSIS FUNCTIONS  
# =============================================================================

def assess_status(value, threshold_key):
    """Determine if a value is stable, warning, or critical."""
    if value is None:
        return "unknown"
    
    t = THRESHOLDS[threshold_key]
    
    if t["direction"] == "below":
        if value < t["critical"]:
            return "critical"
        elif value < t["warning"]:
            return "warning"
        else:
            return "stable"
    else:  # "above"
        if value > t["critical"]:
            return "critical"
        elif value > t["warning"]:
            return "warning"
        else:
            return "stable"


def format_change(value, unit="%"):
    """Format a change value with + or - sign."""
    if value is None:
        return "N/A"
    sign = "+" if value > 0 else ""
    return f"{sign}{value}{unit}"


def format_value(value, unit="", default="N/A"):
    """Format a value with unit."""
    if value is None:
        return default
    return f"{value}{unit}"


# =============================================================================
# REPORT GENERATION
# =============================================================================

def generate_html_report(data):
    """Generate the HTML email report."""
    
    today = datetime.now().strftime('%B %d, %Y')
    
    # Collect all statuses (only from successful fetches)
    statuses = []
    status_counts = {"stable": 0, "warning": 0, "critical": 0, "unknown": 0}
    total_metrics = 8  # Updated count
    
    for key in data:
        if isinstance(data[key], dict) and "status" in data[key]:
            status = data[key].get("status", "unknown")
            # Skip info-only metrics (intl_vs_us) from status counts
            if key == "intl_vs_us":
                continue
            if data[key].get("success", False) or status != "unknown":
                statuses.append(status)
                status_counts[status] = status_counts.get(status, 0) + 1
    
    # Determine overall status and create summary
    warning_count = status_counts.get("warning", 0)
    critical_count = status_counts.get("critical", 0)
    successful_count = len([s for s in statuses if s != "unknown"])
    
    # Overall status logic:
    # Green: 0-1 warnings, 0 criticals
    # Amber: 2+ warnings OR 1 critical
    # Red: 3+ warnings OR 2+ criticals OR (1 critical + 2+ warnings)
    if critical_count >= 2 or (critical_count >= 1 and warning_count >= 2) or warning_count >= 3:
        overall_color = "#dc3545"  # Red
        overall_summary = f"HIGH ALERT: {critical_count} critical, {warning_count} warning out of {successful_count} metrics"
    elif critical_count >= 1 or warning_count >= 2:
        overall_color = "#f39c12"  # Amber
        if critical_count >= 1:
            overall_summary = f"Elevated concern: {critical_count} critical, {warning_count} warning out of {successful_count} metrics"
        else:
            overall_summary = f"Elevated concern: {warning_count} warnings out of {successful_count} metrics"
    elif warning_count == 1:
        overall_color = "#27ae60"  # Green (1 warning is still green)
        overall_summary = f"All {successful_count} metrics stable (1 warning)"
    elif successful_count > 0:
        overall_color = "#27ae60"  # Green
        overall_summary = f"All {successful_count} metrics stable"
    else:
        overall_color = "#95a5a6"  # Gray
        overall_summary = "Data unavailable"

    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            max-width: 700px; 
            margin: 0 auto; 
            padding: 20px; 
            color: #333;
            line-height: 1.5;
        }}
        h1 {{ 
            color: #1a1a1a; 
            border-bottom: 2px solid #ddd; 
            padding-bottom: 10px; 
        }}
        h2 {{ 
            color: #444; 
            margin-top: 30px;
            font-size: 18px;
        }}
        .overall-status {{ 
            background: {overall_color}; 
            color: white; 
            padding: 15px; 
            border-radius: 6px; 
            margin: 20px 0;
            font-size: 16px;
        }}
        .overall-status strong {{
            font-size: 18px;
        }}
        .indicator {{ 
            background: #f8f9fa; 
            padding: 15px; 
            margin: 15px 0; 
            border-radius: 6px; 
            border-left: 4px solid #ddd; 
        }}
        .indicator.critical {{ border-left-color: #dc3545; }}
        .indicator.warning {{ border-left-color: #f39c12; }}
        .indicator.stable {{ border-left-color: #27ae60; }}
        .indicator.info {{ border-left-color: #3498db; }}
        .indicator.unknown {{ border-left-color: #95a5a6; }}
        .indicator-title {{
            font-weight: bold;
            margin-bottom: 8px;
        }}
        .indicator-value {{
            font-size: 24px;
            font-weight: bold;
            margin: 10px 0;
        }}
        .indicator-details {{
            font-size: 14px;
            color: #555;
        }}
        .data-freshness {{
            font-size: 11px;
            color: #888;
            margin-top: 8px;
            font-style: italic;
        }}
        .threshold-note {{
            font-size: 12px;
            color: #777;
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid #eee;
        }}
        .status-label {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 12px;
            font-weight: bold;
            text-transform: uppercase;
        }}
        .status-critical {{ background: #dc3545; color: white; }}
        .status-warning {{ background: #f39c12; color: white; }}
        .status-stable {{ background: #27ae60; color: white; }}
        .status-info {{ background: #3498db; color: white; }}
        .status-unknown {{ background: #95a5a6; color: white; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
            font-size: 14px;
        }}
        td {{
            padding: 5px 0;
        }}
        td:last-child {{
            text-align: right;
        }}
        .footer {{ 
            margin-top: 40px; 
            padding-top: 20px; 
            border-top: 1px solid #ddd; 
            font-size: 12px; 
            color: #666; 
        }}
        .error-note {{
            font-size: 12px;
            color: #dc3545;
            margin-top: 5px;
        }}
    </style>
</head>
<body>
    <h1>Bretton Woods Decay Report</h1>
    <p>Report Date: {today}</p>
    
    <div class="overall-status">
        <strong>Status:</strong> {overall_summary}
    </div>
"""
    
    # 1. USD Reserve Share
    cofer = data.get("cofer", {})
    status = cofer.get("status", "unknown")
    
    if cofer.get("success"):
        value_display = f"{cofer.get('value')}%"
        period_display = cofer.get('period', 'N/A')
        change_1y = format_change(cofer.get('change_1y'), '%')
        change_5y = format_change(cofer.get('change_5y'), '%')
        freshness = cofer.get('data_freshness', 'Unknown')
        source = cofer.get('source', 'IMF COFER')
        error_note = ""
    else:
        value_display = "N/A"
        period_display = "N/A"
        change_1y = "N/A"
        change_5y = "N/A"
        freshness = "Unknown"
        source = cofer.get('source', 'IMF COFER')
        error_note = f'<div class="error-note">Could not fetch data: {cofer.get("error", "Unknown error")}</div>'
    
    html += f"""
    <div class="indicator {status}">
        <div class="indicator-title">
            USD Share of Global Reserves
            <span class="status-label status-{status}">{status.upper()}</span>
        </div>
        <div class="indicator-value">{value_display}</div>
        <div class="indicator-details">
            <table>
                <tr><td>Period</td><td>{period_display}</td></tr>
                <tr><td>1-year change</td><td>{change_1y}</td></tr>
                <tr><td>5-year change</td><td>{change_5y}</td></tr>
            </table>
            {error_note}
        </div>
        <div class="data-freshness">Data as of: {freshness} | Source: {source}</div>
        <div class="threshold-note">
            Warning: below {THRESHOLDS['usd_reserve_share']['warning']}% | 
            Critical: below {THRESHOLDS['usd_reserve_share']['critical']}%<br>
            {THRESHOLDS['usd_reserve_share']['context']}
        </div>
    </div>
"""
    
    # 2. China Treasury Holdings
    china = data.get("china", {})
    status = china.get("status", "unknown")
    
    if china.get("current") is not None:
        value_display = f"${china.get('current')}B"
        change_6mo = format_change(china.get('change_6mo'), 'B')
        change_12mo = format_change(china.get('change_12mo'), 'B')
        trend = 'Selling' if (china.get('change_12mo') or 0) < -10 else 'Accumulating' if (china.get('change_12mo') or 0) > 10 else 'Stable'
        freshness = china.get('data_freshness', 'Unknown')
        source = china.get('source', 'Treasury TIC')
        error_note = ""
    else:
        value_display = "N/A"
        change_6mo = "N/A"
        change_12mo = "N/A"
        trend = "Unknown"
        freshness = "Unknown"
        source = "Treasury TIC"
        error_note = f'<div class="error-note">Could not fetch data: {china.get("error", "Unknown error")}</div>'
    
    html += f"""
    <div class="indicator {status}">
        <div class="indicator-title">
            China Treasury Holdings
            <span class="status-label status-{status}">{status.upper()}</span>
        </div>
        <div class="indicator-value">{value_display}</div>
        <div class="indicator-details">
            <table>
                <tr><td>6-month change</td><td>{change_6mo}</td></tr>
                <tr><td>12-month change</td><td>{change_12mo}</td></tr>
            </table>
            <p>Trend: {trend}</p>
            {error_note}
        </div>
        <div class="data-freshness">Data as of: {freshness} | Source: {source}</div>
        <div class="threshold-note">
            Warning: below ${THRESHOLDS['china_treasury']['warning']}B | 
            Critical: below ${THRESHOLDS['china_treasury']['critical']}B<br>
            {THRESHOLDS['china_treasury']['context']}
        </div>
    </div>
"""
    
    # 3. Japan Treasury Holdings
    japan = data.get("japan", {})
    status = japan.get("status", "unknown")
    
    if japan.get("current") is not None:
        value_display = f"${japan.get('current')}B"
        change_6mo = format_change(japan.get('change_6mo'), 'B')
        change_12mo = format_change(japan.get('change_12mo'), 'B')
        trend = 'Selling' if (japan.get('change_12mo') or 0) < -10 else 'Accumulating' if (japan.get('change_12mo') or 0) > 10 else 'Stable'
        freshness = japan.get('data_freshness', 'Unknown')
        source = japan.get('source', 'Treasury TIC')
        error_note = ""
    else:
        value_display = "N/A"
        change_6mo = "N/A"
        change_12mo = "N/A"
        trend = "Unknown"
        freshness = "Unknown"
        source = "Treasury TIC"
        error_note = f'<div class="error-note">Could not fetch data: {japan.get("error", "Unknown error")}</div>'
    
    html += f"""
    <div class="indicator {status}">
        <div class="indicator-title">
            Japan Treasury Holdings
            <span class="status-label status-{status}">{status.upper()}</span>
        </div>
        <div class="indicator-value">{value_display}</div>
        <div class="indicator-details">
            <table>
                <tr><td>6-month change</td><td>{change_6mo}</td></tr>
                <tr><td>12-month change</td><td>{change_12mo}</td></tr>
            </table>
            <p>Trend: {trend}</p>
            {error_note}
        </div>
        <div class="data-freshness">Data as of: {freshness} | Source: {source}</div>
        <div class="threshold-note">
            Warning: below ${THRESHOLDS['japan_treasury']['warning']}B | 
            Critical: below ${THRESHOLDS['japan_treasury']['critical']}B<br>
            {THRESHOLDS['japan_treasury']['context']}
        </div>
    </div>
"""
    
    # 4. DXY
    dxy = data.get("dxy", {})
    status = dxy.get("status", "unknown")
    
    if dxy.get("success"):
        value_display = f"{dxy.get('value')}"
        change_1y = format_change(dxy.get('change_1y'), '%')
        change_3y = format_change(dxy.get('change_3y'), '%')
        year_ago_display = f"{dxy.get('year_ago', 'N/A')} ({dxy.get('year_ago_date', 'N/A')})"
        freshness = dxy.get('data_freshness', 'Unknown')
        source = dxy.get('source', 'Yahoo Finance')
        error_note = ""
    else:
        value_display = "N/A"
        change_1y = "N/A"
        change_3y = "N/A"
        year_ago_display = "N/A"
        freshness = "Unknown"
        source = dxy.get('source', 'Yahoo Finance')
        error_note = f'<div class="error-note">Could not fetch data: {dxy.get("error", "Unknown error")}</div>'
    
    html += f"""
    <div class="indicator {status}">
        <div class="indicator-title">
            Dollar Index (DXY)
            <span class="status-label status-{status}">{status.upper()}</span>
        </div>
        <div class="indicator-value">{value_display}</div>
        <div class="indicator-details">
            <table>
                <tr><td>1-year ago</td><td>{year_ago_display}</td></tr>
                <tr><td>1-year change</td><td>{change_1y}</td></tr>
                <tr><td>3-year change</td><td>{change_3y}</td></tr>
            </table>
            {error_note}
        </div>
        <div class="data-freshness">Data as of: {freshness} | Source: {source}</div>
        <div class="threshold-note">
            Warning: below {THRESHOLDS['dxy']['warning']} | 
            Critical: below {THRESHOLDS['dxy']['critical']}<br>
            {THRESHOLDS['dxy']['context']}
        </div>
    </div>
"""
    
    # 5. Debt to GDP
    debt = data.get("debt_to_gdp", {})
    status = debt.get("status", "unknown")
    
    if debt.get("success"):
        value_display = f"{debt.get('value')}%"
        date_display = debt.get('date', 'N/A')
        freshness = debt.get('data_freshness', 'Unknown')
        source = debt.get('source', 'FRED')
        error_note = ""
    else:
        value_display = "N/A"
        date_display = "N/A"
        freshness = "Unknown"
        source = debt.get('source', 'FRED')
        error_note = f'<div class="error-note">Could not fetch data: {debt.get("error", "Unknown error")}</div>'
    
    html += f"""
    <div class="indicator {status}">
        <div class="indicator-title">
            US Debt-to-GDP Ratio
            <span class="status-label status-{status}">{status.upper()}</span>
        </div>
        <div class="indicator-value">{value_display}</div>
        <div class="indicator-details">
            {error_note}
        </div>
        <div class="data-freshness">Data as of: {freshness} | Source: {source}</div>
        <div class="threshold-note">
            Warning: above {THRESHOLDS['debt_to_gdp']['warning']}% | 
            Critical: above {THRESHOLDS['debt_to_gdp']['critical']}%<br>
            {THRESHOLDS['debt_to_gdp']['context']}
        </div>
    </div>
"""
    
    # 6. Interest to Revenue
    interest = data.get("interest_to_revenue", {})
    status = interest.get("status", "unknown")
    
    if interest.get("success"):
        value_display = f"{interest.get('value')}%"
        date_display = interest.get('date', 'N/A')
        interest_amt = f"${interest.get('interest', 'N/A')}B"
        revenue_amt = f"${interest.get('revenue', 'N/A')}B"
        change_1y = format_change(interest.get('change_1y'), '%') if interest.get('change_1y') else "N/A"
        freshness = interest.get('data_freshness', 'Unknown')
        source = interest.get('source', 'FRED')
        error_note = ""
    else:
        value_display = "N/A"
        date_display = "N/A"
        interest_amt = "N/A"
        revenue_amt = "N/A"
        change_1y = "N/A"
        freshness = "Unknown"
        source = interest.get('source', 'FRED')
        error_note = f'<div class="error-note">Could not fetch data: {interest.get("error", "Unknown error")}</div>'
    
    html += f"""
    <div class="indicator {status}">
        <div class="indicator-title">
            Interest Payments as % of Revenue
            <span class="status-label status-{status}">{status.upper()}</span>
        </div>
        <div class="indicator-value">{value_display}</div>
        <div class="indicator-details">
            <table>
                <tr><td>Quarterly interest (SAAR)</td><td>{interest_amt}</td></tr>
                <tr><td>Quarterly revenue (SAAR)</td><td>{revenue_amt}</td></tr>
                <tr><td>1-year change</td><td>{change_1y}</td></tr>
            </table>
            {error_note}
        </div>
        <div class="data-freshness">Data as of: {freshness} | Source: {source}</div>
        <div class="threshold-note">
            Warning: above {THRESHOLDS['interest_to_revenue']['warning']}% | 
            Critical: above {THRESHOLDS['interest_to_revenue']['critical']}%<br>
            {THRESHOLDS['interest_to_revenue']['context']}
        </div>
    </div>
"""
    
    # 7. Interest to Defense (Guns vs Debt)
    int_def = data.get("interest_to_defense", {})
    status = int_def.get("status", "unknown")
    
    if int_def.get("success"):
        value_display = f"{int_def.get('value')}%"
        date_display = int_def.get('date', 'N/A')
        interest_amt = f"${int_def.get('interest', 'N/A')}B"
        defense_amt = f"${int_def.get('defense', 'N/A')}B"
        change_1y = format_change(int_def.get('change_1y'), '%') if int_def.get('change_1y') else "N/A"
        freshness = int_def.get('data_freshness', 'Unknown')
        source = int_def.get('source', 'FRED')
        error_note = ""
    else:
        value_display = "N/A"
        date_display = "N/A"
        interest_amt = "N/A"
        defense_amt = "N/A"
        change_1y = "N/A"
        freshness = "Unknown"
        source = int_def.get('source', 'FRED')
        error_note = f'<div class="error-note">Could not fetch data: {int_def.get("error", "Unknown error")}</div>'
    
    html += f"""
    <div class="indicator {status}">
        <div class="indicator-title">
            Interest vs Defense Spending (Guns vs Debt)
            <span class="status-label status-{status}">{status.upper()}</span>
        </div>
        <div class="indicator-value">{value_display}</div>
        <div class="indicator-details">
            <table>
                <tr><td>Interest payments (SAAR)</td><td>{interest_amt}</td></tr>
                <tr><td>Defense spending (SAAR)</td><td>{defense_amt}</td></tr>
                <tr><td>1-year change</td><td>{change_1y}</td></tr>
            </table>
            {error_note}
        </div>
        <div class="data-freshness">Data as of: {freshness} | Source: {source}</div>
        <div class="threshold-note">
            Warning: above {THRESHOLDS['interest_to_defense']['warning']}% | 
            Critical: above {THRESHOLDS['interest_to_defense']['critical']}%<br>
            {THRESHOLDS['interest_to_defense']['context']}
        </div>
    </div>
"""
    
    # 8. Trade Balance / GDP
    trade = data.get("trade_balance_gdp", {})
    status = trade.get("status", "unknown")
    
    if trade.get("success"):
        value_display = f"{trade.get('value')}%"
        date_display = trade.get('date', 'N/A')
        trade_amt = f"${trade.get('trade_balance', 'N/A')}B"
        gdp_amt = f"${trade.get('gdp', 'N/A')}B"
        change_1y = format_change(trade.get('change_1y'), '%') if trade.get('change_1y') else "N/A"
        freshness = trade.get('data_freshness', 'Unknown')
        source = trade.get('source', 'FRED')
        error_note = ""
    else:
        value_display = "N/A"
        date_display = "N/A"
        trade_amt = "N/A"
        gdp_amt = "N/A"
        change_1y = "N/A"
        freshness = "Unknown"
        source = trade.get('source', 'FRED')
        error_note = f'<div class="error-note">Could not fetch data: {trade.get("error", "Unknown error")}</div>'
    
    html += f"""
    <div class="indicator {status}">
        <div class="indicator-title">
            Trade Balance as % of GDP
            <span class="status-label status-{status}">{status.upper()}</span>
        </div>
        <div class="indicator-value">{value_display}</div>
        <div class="indicator-details">
            <table>
                <tr><td>Trade balance (annualized)</td><td>{trade_amt}</td></tr>
                <tr><td>GDP</td><td>{gdp_amt}</td></tr>
                <tr><td>1-year change</td><td>{change_1y}</td></tr>
            </table>
            {error_note}
        </div>
        <div class="threshold-note">
            Warning: less negative than {THRESHOLDS['trade_balance_gdp']['warning']}% | 
            Critical: less negative than {THRESHOLDS['trade_balance_gdp']['critical']}%<br>
            {THRESHOLDS['trade_balance_gdp']['context']}
        </div>
    </div>
"""

    # Market Context Section (Informational - Blue)
    html += """
    <h2>Market Context</h2>
    <p style="font-size: 14px; color: #666; margin-bottom: 15px;">Informational metrics that provide context but don't trigger warnings.</p>
"""
    
    # International vs US Performance (now informational/blue)
    perf = data.get("intl_vs_us", {})
    
    if perf.get("success"):
        diff_3y = perf.get('diff_3y', 0) or 0
        value_display = format_change(perf.get('diff_3y'), '%')
        direction = "International outperforming" if diff_3y > 0 else "US outperforming" if diff_3y < 0 else "Roughly even"
        intl_3y = format_change(perf.get('intl_return_3y'), '%')
        us_3y = format_change(perf.get('us_return_3y'), '%')
        diff_1y = format_change(perf.get('diff_1y'), '%')
        freshness = perf.get('data_freshness', 'Unknown')
        source = perf.get('source', 'Yahoo Finance')
        error_note = ""
    else:
        value_display = "N/A"
        direction = "Unknown"
        intl_3y = "N/A"
        us_3y = "N/A"
        diff_1y = "N/A"
        freshness = "Unknown"
        source = perf.get('source', 'Yahoo Finance')
        error_note = f'<div class="error-note">Could not fetch data: {perf.get("error", "Unknown error")}</div>'
    
    html += f"""
    <div class="indicator info">
        <div class="indicator-title">
            International vs US Stocks (3-Year)
            <span class="status-label status-info">CONTEXT</span>
        </div>
        <div class="indicator-value">{value_display}</div>
        <div class="indicator-details">
            <table>
                <tr><td>International 3yr return (VXUS)</td><td>{intl_3y}</td></tr>
                <tr><td>US 3yr return (VTI)</td><td>{us_3y}</td></tr>
                <tr><td>1-year difference</td><td>{diff_1y}</td></tr>
            </table>
            <p><strong>{direction}</strong></p>
            <p style="font-size: 12px; color: #666;">VXUS (Total International, ex-US) vs VTI (Total US Market). These are good proxies for FTIHX vs FXAIX.</p>
            {error_note}
        </div>
        <div class="data-freshness">Data as of: {freshness} | Source: {source}</div>
        <div class="threshold-note">
            Positive = international outperforming. US has outperformed international for most of 2010-2024. Sustained reversal may signal dollar weakness or valuation normalization.
        </div>
    </div>
"""
    
    # Decision Framework
    html += """
    <h2>Decision Framework</h2>
    <div class="indicator stable">
        <p><strong>What to do with this information:</strong></p>
        <ul>
            <li><strong>All stable:</strong> No action needed. Check back next quarter.</li>
            <li><strong>1-2 warnings:</strong> Note it, but don't react to a single report. Watch for trends across multiple reports.</li>
            <li><strong>Warnings for 2-3 consecutive reports:</strong> Consider gradually shifting from 65/35 to 50/50 domestic/international.</li>
            <li><strong>Multiple critical signals:</strong> More aggressive rebalancing toward international may be warranted.</li>
        </ul>
        <p style="margin-top: 15px;">Remember: These are slow-moving structural indicators. Monetary system changes happen over decades, not months. The goal is to catch sustained trends, not react to noise.</p>
    </div>
"""
    
    # Footer - Calculate next report month
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    # Quarterly schedule: Jan, Apr, Jul, Oct
    quarterly_months = [1, 4, 7, 10]
    next_quarter_months = [m for m in quarterly_months if m > current_month]
    
    if next_quarter_months:
        next_month_num = next_quarter_months[0]
        next_year = current_year
    else:
        next_month_num = quarterly_months[0]  # January
        next_year = current_year + 1
    
    next_month_name = datetime(2000, next_month_num, 1).strftime('%B')
    
    html += f"""
    <div class="footer">
        <p>Generated by freak_the_f***_out_and_sell_everything.py<br>
        This is financial advice and you can hold me, Elliot Allen, legally culpable.<br>
        Next scheduled report: {next_month_name} {next_year}</p>
    </div>
</body>
</html>
"""
    
    return html


def send_email_icloud(subject, body_html):
    """Send email via iCloud SMTP."""
    if not ICLOUD_EMAIL or not ICLOUD_PASSWORD:
        print("Error: Email credentials not configured")
        return False
    
    recipient = TO_EMAIL or ICLOUD_EMAIL
    
    msg = MIMEMultipart()
    msg['From'] = f"Bretton Woods Decay <{ICLOUD_EMAIL}>"
    msg['To'] = recipient
    msg['Subject'] = subject
    msg.attach(MIMEText(body_html, 'html'))
    
    try:
        server = smtplib.SMTP('smtp.mail.me.com', 587)
        server.starttls()
        server.login(ICLOUD_EMAIL, ICLOUD_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"Email sent successfully to {recipient}")
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 60)
    print("Bretton Woods Decay - Quarterly Report")
    print("=" * 60)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    data = {}
    
    # 1. IMF COFER
    print("Fetching USD reserve share (IMF COFER via DBnomics)...")
    cofer = fetch_imf_cofer()
    if cofer.get("success"):
        cofer["status"] = assess_status(cofer.get("value"), "usd_reserve_share")
        print(f"  Value: {cofer['value']}% ({cofer.get('period')}) - Status: {cofer['status']}")
    else:
        cofer["status"] = "unknown"
        print(f"  Failed: {cofer.get('error')}")
    data["cofer"] = cofer
    
    # 2 & 3. Treasury Holdings
    print("Fetching Treasury holdings (TIC)...")
    treasury = fetch_treasury_holdings()
    
    if treasury.get("success"):
        if "china" in treasury:
            china = treasury["china"]
            china["value"] = china["current"]
            china["status"] = assess_status(china["current"], "china_treasury")
            print(f"  China: ${china['current']}B - Status: {china['status']}")
            data["china"] = china
        else:
            data["china"] = {"status": "unknown", "error": "China data not found in TIC report"}
            print("  China: Not found")
        
        if "japan" in treasury:
            japan = treasury["japan"]
            japan["value"] = japan["current"]
            japan["status"] = assess_status(japan["current"], "japan_treasury")
            print(f"  Japan: ${japan['current']}B - Status: {japan['status']}")
            data["japan"] = japan
        else:
            data["japan"] = {"status": "unknown", "error": "Japan data not found in TIC report"}
            print("  Japan: Not found")
    else:
        print(f"  Failed: {treasury.get('error')}")
        data["china"] = {"status": "unknown", "error": treasury.get("error")}
        data["japan"] = {"status": "unknown", "error": treasury.get("error")}
    
    # 4. DXY
    print("Fetching Dollar Index (DXY)...")
    dxy = fetch_dxy()
    if dxy.get("success"):
        dxy["status"] = assess_status(dxy.get("value"), "dxy")
        print(f"  Value: {dxy['value']} - Status: {dxy['status']}")
    else:
        dxy["status"] = "unknown"
        print(f"  Failed: {dxy.get('error')}")
    data["dxy"] = dxy
    
    # 5. Debt to GDP
    print("Fetching Debt-to-GDP ratio (FRED)...")
    debt = fetch_debt_to_gdp()
    if debt.get("success"):
        debt["status"] = assess_status(debt.get("value"), "debt_to_gdp")
        print(f"  Value: {debt['value']}% - Status: {debt['status']}")
    else:
        debt["status"] = "unknown"
        print(f"  Failed: {debt.get('error')}")
    data["debt_to_gdp"] = debt
    
    # 6. Interest to Revenue (now quarterly)
    print("Fetching Interest/Revenue ratio (FRED - quarterly BEA data)...")
    interest = fetch_interest_to_revenue()
    if interest.get("success"):
        interest["status"] = assess_status(interest.get("value"), "interest_to_revenue")
        print(f"  Value: {interest['value']}% - Status: {interest['status']}")
    else:
        interest["status"] = "unknown"
        print(f"  Failed: {interest.get('error')}")
    data["interest_to_revenue"] = interest
    
    # 7. Interest to Defense
    print("Fetching Interest/Defense ratio (FRED)...")
    int_def = fetch_interest_to_defense()
    if int_def.get("success"):
        int_def["status"] = assess_status(int_def.get("value"), "interest_to_defense")
        print(f"  Value: {int_def['value']}% - Status: {int_def['status']}")
    else:
        int_def["status"] = "unknown"
        print(f"  Failed: {int_def.get('error')}")
    data["interest_to_defense"] = int_def
    
    # 8. Trade Balance / GDP
    print("Fetching Trade Balance/GDP ratio (FRED)...")
    trade = fetch_trade_balance_gdp()
    if trade.get("success"):
        trade["status"] = assess_status(trade.get("value"), "trade_balance_gdp")
        print(f"  Value: {trade['value']}% - Status: {trade['status']}")
    else:
        trade["status"] = "unknown"
        print(f"  Failed: {trade.get('error')}")
    data["trade_balance_gdp"] = trade
    
    # 10. International vs US Performance (informational only)
    print("Fetching International vs US performance (VXUS vs VTI)...")
    perf = fetch_intl_vs_us_performance()
    if perf.get("success"):
        perf["status"] = "info"  # Always info, not assessed
        print(f"  3yr diff: {perf.get('diff_3y')}% - Status: {perf['status']}")
    else:
        perf["status"] = "unknown"
        print(f"  Failed: {perf.get('error')}")
    data["intl_vs_us"] = perf

    # Generate report
    print()
    print("Generating report...")
    html = generate_html_report(data)
    
    # Save locally
    with open("bretton_woods_report.html", "w") as f:
        f.write(html)
    print("Saved to bretton_woods_report.html")
    
    # Determine subject based on known statuses only
    statuses = []
    for d in data.values():
        if isinstance(d, dict) and d.get("success", False):
            statuses.append(d.get("status", "unknown"))
    
    warning_count = statuses.count("warning")
    critical_count = statuses.count("critical")
    
    if critical_count > 0:
        subject = f"Bretton Woods Decay: {critical_count} CRITICAL - {datetime.now().strftime('%B %Y')}"
    elif warning_count > 0:
        subject = f"Bretton Woods Decay: {warning_count} Warning - {datetime.now().strftime('%B %Y')}"
    elif statuses:
        subject = f"Bretton Woods Decay: All Stable - {datetime.now().strftime('%B %Y')}"
    else:
        subject = f"Bretton Woods Decay: Data Unavailable - {datetime.now().strftime('%B %Y')}"
    
    # Send email
    print()
    print("Sending email...")
    if send_email_icloud(subject, html):
        print("Done!")
    else:
        print("Email failed - check bretton_woods_report.html for report")
    
    return 0


if __name__ == "__main__":
    exit(main())
