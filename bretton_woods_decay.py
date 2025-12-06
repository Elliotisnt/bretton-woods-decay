"""
Bretton Woods Decay - Quarterly Macro Indicator Monitor
========================================================
Tracks key indicators of US dollar/empire structural health:

1. USD share of global foreign exchange reserves (IMF COFER via DBnomics)
2. China holdings of US Treasuries (Treasury TIC)
3. Japan holdings of US Treasuries (Treasury TIC)
4. DXY Dollar Index (Yahoo Finance)
5. US Debt-to-GDP ratio (FRED)
6. Federal interest payments as % of revenue (FRED)
7. Interest payments vs Defense spending - "Guns vs Debt" (FRED)
8. Trade Balance as % of GDP (FRED)
9. Empire Premium - VTI/VXUS Price-to-Book spread (Yahoo Finance)

Plus: Performance History context (VTI/VXUS 1, 3, 5, 10-year returns) - informational only.

Designed to run quarterly (Jan, Apr, Jul, Oct) via GitHub Actions.
Sends a formatted email report via iCloud SMTP.
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
        "context": "Peaked at 71% in 2000. Declined to ~58% by 2024. Below 50% unprecedented since tracking began 1999."
    },
    "china_treasury": {
        "warning": 700.0,
        "critical": 500.0,
        "direction": "below",
        "unit": "B",
        "description": "China holdings of US Treasuries",
        "context": "Peaked at $1.32T in Nov 2013. Has been steadily declining since 2018."
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
        "context": "Previous peak ~18% in 1991. Fell to ~6% by 2015 due to low rates. Japan at ~260% debt/GDP only pays ~8% of revenue to interest due to BoJ ownership and near-zero rates."
    },
    "interest_to_defense": {
        "warning": 90.0,
        "critical": 100.0,
        "direction": "above",
        "unit": "%",
        "description": "Interest payments vs Defense spending (Guns vs Debt)",
        "context": "Tracks if US spends more on past mistakes (debt service) than future power (defense). At 100% = crossover point where interest exceeds defense."
    },
    "trade_balance_gdp": {
        "warning": -1.5,
        "critical": -0.5,
        "direction": "above",
        "unit": "%",
        "description": "Trade Balance as % of GDP",
        "context": "Currently ~-3% of GDP. Narrowing toward zero could signal world stops extending credit (forced close of deficit)."
    },
    "empire_premium": {
        "warning": 2.0,
        "critical": 1.5,
        "direction": "below",
        "unit": "x",
        "description": "Empire Premium (VTI/VXUS Price-to-Book)",
        "context": "Measures US valuation premium over international. Below 2.0x = premium fading. Below 1.5x = structural parity, no empire premium."
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
                
                data_freshness = "Unknown"
                if indexed_at:
                    try:
                        if "T" in indexed_at:
                            dt = datetime.fromisoformat(indexed_at.replace("Z", "+00:00"))
                            data_freshness = dt.strftime("%Y-%m-%d")
                    except:
                        data_freshness = indexed_at[:10] if len(indexed_at) >= 10 else indexed_at
                
                if periods and values:
                    latest_idx = len(values) - 1
                    while latest_idx >= 0 and values[latest_idx] is None:
                        latest_idx -= 1
                    
                    if latest_idx >= 0:
                        current = float(values[latest_idx])
                        period = periods[latest_idx]
                        
                        year_ago = None
                        if latest_idx >= 4:
                            year_ago = float(values[latest_idx - 4]) if values[latest_idx - 4] is not None else None
                        
                        five_year_ago = None
                        if latest_idx >= 20:
                            five_year_ago = float(values[latest_idx - 20]) if values[latest_idx - 20] is not None else None
                        
                        return {
                            "success": True,
                            "value": round(current, 1),
                            "period": period,
                            "year_ago": round(year_ago, 1) if year_ago else None,
                            "five_year_ago": round(five_year_ago, 1) if five_year_ago else None,
                            "change_1y": round(current - year_ago, 2) if year_ago else None,
                            "change_5y": round(current - five_year_ago, 2) if five_year_ago else None,
                            "data_freshness": data_freshness,
                            "source": "IMF COFER via DBnomics"
                        }
        
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
    """Fetch China and Japan Treasury holdings from Treasury TIC data."""
    try:
        url = "https://ticdata.treasury.gov/resource-center/data-chart-center/tic/Documents/slt_table5.txt"
        response = requests.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            
            china_data = None
            japan_data = None
            data_date = None
            
            for line in lines:
                if not line.strip():
                    continue
                if any(line.startswith(x) for x in ['Table 5:', 'Holdings at', 'Billions', 'Link:', 'Notes:', 'The data in', 'overseas', '(see TIC', 'Estimated', 'International', 'as reported', 'and on TIC']):
                    continue
                
                parts = line.split('\t')
                
                if parts[0].strip() == 'Country':
                    date_columns = [p.strip() for p in parts[1:] if p.strip()]
                    if date_columns:
                        data_date = date_columns[0]
                    continue
                
                country = parts[0].strip().lower()
                
                if country in ['japan', 'china, mainland']:
                    values = []
                    for p in parts[1:]:
                        p = p.strip()
                        if p:
                            try:
                                values.append(float(p.replace(',', '')))
                            except ValueError:
                                values.append(None)
                    
                    if values and values[0] is not None:
                        country_data = {
                            "current": values[0],
                            "6mo_ago": values[6] if len(values) > 6 and values[6] is not None else None,
                            "12mo_ago": values[12] if len(values) > 12 and values[12] is not None else None
                        }
                        if country == 'japan':
                            japan_data = country_data
                        else:
                            china_data = country_data
            
            result = {"success": True, "data_date": data_date, "data_freshness": data_date or "Unknown", "source": "Treasury TIC SLT Table 5"}
            
            for name, cdata in [("china", china_data), ("japan", japan_data)]:
                if cdata:
                    cdata["change_6mo"] = round(cdata["current"] - cdata["6mo_ago"], 1) if cdata["6mo_ago"] else None
                    cdata["change_12mo"] = round(cdata["current"] - cdata["12mo_ago"], 1) if cdata["12mo_ago"] else None
                    cdata["data_freshness"] = data_date
                    cdata["source"] = "Treasury TIC SLT Table 5"
                    result[name] = cdata
            
            return result
        
        return {"success": False, "error": f"API returned status {response.status_code}", "source": "Treasury TIC"}
    except Exception as e:
        return {"success": False, "error": str(e), "source": "Treasury TIC"}


def fetch_fred_series(series_id, name):
    """Fetch a data series from FRED."""
    try:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        response = requests.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            if len(lines) > 1:
                for line in reversed(lines[1:]):
                    parts = line.split(',')
                    if len(parts) >= 2 and parts[1].strip() and parts[1] != '.':
                        return {
                            "success": True,
                            "value": float(parts[1]),
                            "date": parts[0],
                            "data_freshness": parts[0],
                            "source": f"FRED ({series_id})",
                            "name": name
                        }
        
        return {"success": False, "error": f"Could not fetch {name}", "source": f"FRED ({series_id})"}
    except Exception as e:
        return {"success": False, "error": str(e), "source": f"FRED ({series_id})"}


def fetch_debt_to_gdp():
    """Fetch US Federal Debt to GDP ratio from FRED."""
    result = fetch_fred_series("GFDEGDQ188S", "Debt-to-GDP")
    if result.get("success"):
        result["value"] = round(result["value"], 1)
    return result


def fetch_interest_to_revenue():
    """Calculate interest payments as % of revenue using quarterly SAAR data."""
    try:
        interest_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=A091RC1Q027SBEA"
        revenue_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=W006RC1Q027SBEA"
        
        interest_resp = requests.get(interest_url, headers=HEADERS, timeout=30)
        revenue_resp = requests.get(revenue_url, headers=HEADERS, timeout=30)
        
        if interest_resp.status_code == 200 and revenue_resp.status_code == 200:
            def get_latest(text):
                lines = text.strip().split('\n')
                for line in reversed(lines[1:]):
                    parts = line.split(',')
                    if len(parts) >= 2 and parts[1].strip() and parts[1] != '.':
                        return float(parts[1]), parts[0]
                return None, None
            
            interest, i_date = get_latest(interest_resp.text)
            revenue, r_date = get_latest(revenue_resp.text)
            
            if interest and revenue:
                ratio = (interest / revenue) * 100
                return {
                    "success": True,
                    "value": round(ratio, 1),
                    "interest": round(interest, 1),
                    "revenue": round(revenue, 1),
                    "date": i_date,
                    "data_freshness": i_date,
                    "source": "FRED (A091RC1Q027SBEA / W006RC1Q027SBEA)"
                }
        
        return {"success": False, "error": "Could not calculate interest/revenue ratio", "source": "FRED"}
    except Exception as e:
        return {"success": False, "error": str(e), "source": "FRED"}


def fetch_interest_to_defense():
    """Calculate interest payments as % of defense spending (Guns vs Debt)."""
    try:
        interest_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=A091RC1Q027SBEA"
        defense_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=FDEFX"
        
        interest_resp = requests.get(interest_url, headers=HEADERS, timeout=30)
        defense_resp = requests.get(defense_url, headers=HEADERS, timeout=30)
        
        if interest_resp.status_code == 200 and defense_resp.status_code == 200:
            def get_latest(text):
                lines = text.strip().split('\n')
                for line in reversed(lines[1:]):
                    parts = line.split(',')
                    if len(parts) >= 2 and parts[1].strip() and parts[1] != '.':
                        return float(parts[1]), parts[0]
                return None, None
            
            interest, i_date = get_latest(interest_resp.text)
            defense, d_date = get_latest(defense_resp.text)
            
            if interest and defense:
                ratio = (interest / defense) * 100
                return {
                    "success": True,
                    "value": round(ratio, 1),
                    "interest": round(interest, 1),
                    "defense": round(defense, 1),
                    "date": i_date,
                    "data_freshness": i_date,
                    "source": "FRED (A091RC1Q027SBEA / FDEFX)"
                }
        
        return {"success": False, "error": "Could not calculate interest/defense ratio", "source": "FRED"}
    except Exception as e:
        return {"success": False, "error": str(e), "source": "FRED"}


def fetch_trade_balance_gdp():
    """Calculate trade balance as % of GDP."""
    try:
        trade_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=BOPGSTB"
        gdp_url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=GDP"
        
        trade_resp = requests.get(trade_url, headers=HEADERS, timeout=30)
        gdp_resp = requests.get(gdp_url, headers=HEADERS, timeout=30)
        
        if trade_resp.status_code == 200 and gdp_resp.status_code == 200:
            trade_lines = trade_resp.text.strip().split('\n')
            trade_values = []
            trade_date = None
            for line in reversed(trade_lines[1:]):
                parts = line.split(',')
                if len(parts) >= 2 and parts[1].strip() and parts[1] != '.':
                    if len(trade_values) < 3:
                        trade_values.append(float(parts[1]))
                        if trade_date is None:
                            trade_date = parts[0]
                    else:
                        break
            
            gdp_lines = gdp_resp.text.strip().split('\n')
            gdp_value = None
            for line in reversed(gdp_lines[1:]):
                parts = line.split(',')
                if len(parts) >= 2 and parts[1].strip() and parts[1] != '.':
                    gdp_value = float(parts[1])
                    break
            
            if trade_values and gdp_value:
                avg_monthly_trade = sum(trade_values) / len(trade_values)
                annual_trade = avg_monthly_trade * 12
                ratio = (annual_trade / gdp_value) * 100
                
                return {
                    "success": True,
                    "value": round(ratio, 2),
                    "trade_balance_monthly": round(avg_monthly_trade, 1),
                    "gdp": round(gdp_value, 1),
                    "date": trade_date,
                    "data_freshness": trade_date,
                    "source": "FRED (BOPGSTB / GDP)"
                }
        
        return {"success": False, "error": "Could not calculate trade balance/GDP ratio", "source": "FRED"}
    except Exception as e:
        return {"success": False, "error": str(e), "source": "FRED"}


def fetch_dxy():
    """Fetch DXY Dollar Index from Yahoo Finance."""
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/DX-Y.NYB?interval=1d&range=5y"
        headers = {**HEADERS, "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            result = data.get("chart", {}).get("result", [{}])[0]
            
            closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
            timestamps = result.get("timestamp", [])
            
            valid_data = [(t, c) for t, c in zip(timestamps, closes) if c is not None]
            
            if valid_data:
                latest_ts, current = valid_data[-1]
                latest_date = datetime.fromtimestamp(latest_ts).strftime("%Y-%m-%d")
                
                year_ago = valid_data[-252][1] if len(valid_data) > 252 else None
                year_ago_date = datetime.fromtimestamp(valid_data[-252][0]).strftime("%Y-%m-%d") if len(valid_data) > 252 else None
                
                three_year_ago = valid_data[-756][1] if len(valid_data) > 756 else None
                
                change_1y_pct = ((current / year_ago) - 1) * 100 if year_ago else None
                change_3y_pct = ((current / three_year_ago) - 1) * 100 if three_year_ago else None
                
                return {
                    "success": True,
                    "value": round(current, 2),
                    "date": latest_date,
                    "data_freshness": f"Live (as of {latest_date})",
                    "year_ago": round(year_ago, 2) if year_ago else None,
                    "year_ago_date": year_ago_date,
                    "change_1y_pct": round(change_1y_pct, 1) if change_1y_pct else None,
                    "change_3y_pct": round(change_3y_pct, 1) if change_3y_pct else None,
                    "source": "Yahoo Finance (DX-Y.NYB)"
                }
        
        return {"success": False, "error": f"Could not fetch DXY", "source": "Yahoo Finance"}
    except Exception as e:
        return {"success": False, "error": str(e), "source": "Yahoo Finance"}


def fetch_empire_premium():
    """Fetch Empire Premium - VTI/VXUS Price-to-Book ratio spread."""
    try:
        def get_pb_ratio(symbol):
            url = f"https://query1.finance.yahoo.com/v10/finance/quoteSummary/{symbol}?modules=defaultKeyStatistics"
            headers = {**HEADERS, "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                stats = data.get("quoteSummary", {}).get("result", [{}])[0].get("defaultKeyStatistics", {})
                pb = stats.get("priceToBook", {})
                if isinstance(pb, dict):
                    return pb.get("raw")
                return pb
            return None
        
        vti_pb = get_pb_ratio("VTI")
        vxus_pb = get_pb_ratio("VXUS")
        
        if vti_pb and vxus_pb and vxus_pb > 0:
            ratio = vti_pb / vxus_pb
            return {
                "success": True,
                "value": round(ratio, 2),
                "vti_pb": round(vti_pb, 2),
                "vxus_pb": round(vxus_pb, 2),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "data_freshness": f"Live (as of {datetime.now().strftime('%Y-%m-%d')})",
                "source": "Yahoo Finance (VTI/VXUS P/B)"
            }
        
        return {"success": False, "error": "Could not fetch P/B ratios", "source": "Yahoo Finance"}
    except Exception as e:
        return {"success": False, "error": str(e), "source": "Yahoo Finance"}


def fetch_performance_history():
    """Fetch VTI and VXUS performance history for 1, 3, 5, 10-year periods."""
    try:
        def get_prices(symbol):
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?interval=1d&range=10y"
            headers = {**HEADERS, "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                result = data.get("chart", {}).get("result", [{}])[0]
                closes = result.get("indicators", {}).get("quote", [{}])[0].get("close", [])
                timestamps = result.get("timestamp", [])
                return [(t, c) for t, c in zip(timestamps, closes) if c is not None]
            return []
        
        vti_data = get_prices("VTI")
        vxus_data = get_prices("VXUS")
        
        result = {"success": True, "date": datetime.now().strftime("%Y-%m-%d"), "source": "Yahoo Finance (VTI/VXUS)"}
        
        if vti_data and vxus_data:
            vti_current = vti_data[-1][1]
            vxus_current = vxus_data[-1][1]
            
            periods = {"1y": 252, "3y": 756, "5y": 1260, "10y": 2520}
            
            for period_name, days in periods.items():
                if len(vti_data) > days and len(vxus_data) > days:
                    vti_start = vti_data[-days][1]
                    vxus_start = vxus_data[-days][1]
                    years = days / 252
                    
                    vti_return = ((vti_current / vti_start) ** (1/years) - 1) * 100
                    vxus_return = ((vxus_current / vxus_start) ** (1/years) - 1) * 100
                    
                    result[f"vti_{period_name}"] = round(vti_return, 1)
                    result[f"vxus_{period_name}"] = round(vxus_return, 1)
        
        return result
        
    except Exception as e:
        return {"success": False, "error": str(e), "source": "Yahoo Finance"}


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
    else:
        if value > t["critical"]:
            return "critical"
        elif value > t["warning"]:
            return "warning"
        else:
            return "stable"


def format_change(value, unit=""):
    """Format a change value with + or - sign."""
    if value is None:
        return "N/A"
    sign = "+" if value > 0 else ""
    return f"{sign}{value}{unit}"


# =============================================================================
# REPORT GENERATION
# =============================================================================

def generate_html_report(data):
    """Generate the HTML email report."""
    
    today = datetime.now().strftime('%B %d, %Y')
    
    # Collect statuses
    statuses = []
    status_counts = {"critical": 0, "warning": 0, "stable": 0, "unknown": 0}
    for key in data:
        if key == "performance":
            continue
        if isinstance(data[key], dict) and "status" in data[key]:
            status = data[key]["status"]
            if data[key].get("success", False) or status != "unknown":
                statuses.append(status)
                status_counts[status] = status_counts.get(status, 0) + 1
    
    known_statuses = [s for s in statuses if s != "unknown"]
    total_metrics = len(known_statuses)
    
    if status_counts["critical"] > 0:
        overall = f"CRITICAL - {status_counts['critical']} critical, {status_counts['warning']} warning out of {total_metrics} metrics"
        overall_color = "#dc3545"
    elif status_counts["warning"] > 0:
        overall = f"WARNING - {status_counts['warning']} warning out of {total_metrics} metrics"
        overall_color = "#e67e22"
    elif known_statuses:
        overall = f"STABLE - All {total_metrics} metrics within normal range"
        overall_color = "#27ae60"
    else:
        overall = "UNKNOWN - Data unavailable"
        overall_color = "#95a5a6"
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px; color: #333; line-height: 1.5; }}
        h1 {{ color: #1a1a1a; border-bottom: 2px solid #ddd; padding-bottom: 10px; }}
        h2 {{ color: #444; margin-top: 30px; font-size: 18px; }}
        .overall-status {{ background: {overall_color}; color: white; padding: 15px; border-radius: 6px; margin: 20px 0; }}
        .indicator {{ background: #f8f9fa; padding: 15px; margin: 15px 0; border-radius: 6px; border-left: 4px solid #ddd; }}
        .indicator.critical {{ border-left-color: #dc3545; }}
        .indicator.warning {{ border-left-color: #e67e22; }}
        .indicator.stable {{ border-left-color: #27ae60; }}
        .indicator.unknown {{ border-left-color: #95a5a6; }}
        .indicator.info {{ border-left-color: #3498db; }}
        .indicator-title {{ font-weight: bold; margin-bottom: 8px; }}
        .indicator-value {{ font-size: 24px; font-weight: bold; margin: 10px 0; }}
        .indicator-details {{ font-size: 14px; color: #555; }}
        .data-freshness {{ font-size: 11px; color: #888; margin-top: 8px; font-style: italic; }}
        .threshold-note {{ font-size: 12px; color: #777; margin-top: 10px; padding-top: 10px; border-top: 1px solid #eee; }}
        .status-label {{ display: inline-block; padding: 2px 8px; border-radius: 3px; font-size: 12px; font-weight: bold; text-transform: uppercase; }}
        .status-critical {{ background: #dc3545; color: white; }}
        .status-warning {{ background: #e67e22; color: white; }}
        .status-stable {{ background: #27ae60; color: white; }}
        .status-unknown {{ background: #95a5a6; color: white; }}
        .status-info {{ background: #3498db; color: white; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; font-size: 14px; }}
        td {{ padding: 5px 0; }}
        td:last-child {{ text-align: right; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; font-size: 12px; color: #666; }}
        .error-note {{ font-size: 12px; color: #dc3545; margin-top: 5px; }}
    </style>
</head>
<body>
    <h1>Bretton Woods Decay Report</h1>
    <p>Report Date: {today}</p>
    <div class="overall-status"><strong>Overall Assessment:</strong> {overall}</div>
"""
    
    # Helper function for indicator blocks
    def add_indicator(title, data_key, threshold_key, value_fmt, extra_rows=None, extra_note=""):
        nonlocal html
        d = data.get(data_key, {})
        status = d.get("status", "unknown")
        
        if d.get("success") or d.get("current") is not None:
            value = d.get("value") if d.get("value") is not None else d.get("current")
            value_display = value_fmt(value) if value is not None else "N/A"
            freshness = d.get('data_freshness', 'Unknown')
            source = d.get('source', '')
            error_note = ""
        else:
            value_display = "N/A"
            freshness = "Unknown"
            source = d.get('source', '')
            error_note = f'<div class="error-note">Could not fetch data: {d.get("error", "Unknown error")}</div>'
        
        rows_html = ""
        if extra_rows:
            rows_html = "<table>" + "".join(f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in extra_rows(d)) + "</table>"
        
        t = THRESHOLDS[threshold_key]
        direction = "below" if t["direction"] == "below" else "above"
        
        html += f"""
    <div class="indicator {status}">
        <div class="indicator-title">{title} <span class="status-label status-{status}">{status.upper()}</span></div>
        <div class="indicator-value">{value_display}</div>
        <div class="indicator-details">{rows_html}{extra_note}{error_note}</div>
        <div class="data-freshness">Data as of: {freshness} | Source: {source}</div>
        <div class="threshold-note">Warning: {direction} {t['warning']}{t.get('unit','')} | Critical: {direction} {t['critical']}{t.get('unit','')}<br>{t['context']}</div>
    </div>
"""
    
    # 1. USD Reserve Share
    add_indicator("USD Share of Global Reserves", "cofer", "usd_reserve_share",
        lambda v: f"{v}%",
        lambda d: [("Period", d.get('period', 'N/A')), ("1-year change", format_change(d.get('change_1y'), '%')), ("5-year change", format_change(d.get('change_5y'), '%'))])
    
    # 2. China Treasury
    add_indicator("China Treasury Holdings", "china", "china_treasury",
        lambda v: f"${v}B",
        lambda d: [("6-month change", format_change(d.get('change_6mo'), 'B')), ("12-month change", format_change(d.get('change_12mo'), 'B'))])
    
    # 3. Japan Treasury
    add_indicator("Japan Treasury Holdings", "japan", "japan_treasury",
        lambda v: f"${v}B",
        lambda d: [("6-month change", format_change(d.get('change_6mo'), 'B')), ("12-month change", format_change(d.get('change_12mo'), 'B'))])
    
    # 4. DXY
    add_indicator("Dollar Index (DXY)", "dxy", "dxy",
        lambda v: f"{v}",
        lambda d: [("1-year ago", f"{d.get('year_ago', 'N/A')} ({d.get('year_ago_date', 'N/A')})"), ("1-year change", format_change(d.get('change_1y_pct'), '%')), ("3-year change", format_change(d.get('change_3y_pct'), '%'))])
    
    # 5. Debt to GDP
    add_indicator("US Debt-to-GDP Ratio", "debt_to_gdp", "debt_to_gdp",
        lambda v: f"{v}%",
        lambda d: [("As of", d.get('date', 'N/A'))])
    
    # 6. Interest to Revenue
    add_indicator("Interest Payments as % of Revenue", "interest_to_revenue", "interest_to_revenue",
        lambda v: f"{v}%",
        lambda d: [("Quarterly interest (SAAR)", f"${d.get('interest', 'N/A')}B"), ("Quarterly revenue (SAAR)", f"${d.get('revenue', 'N/A')}B"), ("As of", d.get('date', 'N/A'))])
    
    # 7. Interest to Defense
    add_indicator("Guns vs Debt (Interest / Defense)", "interest_to_defense", "interest_to_defense",
        lambda v: f"{v}%",
        lambda d: [("Interest payments (SAAR)", f"${d.get('interest', 'N/A')}B"), ("Defense spending (SAAR)", f"${d.get('defense', 'N/A')}B"), ("As of", d.get('date', 'N/A'))])
    
    # 8. Trade Balance / GDP
    add_indicator("Trade Balance / GDP", "trade_balance_gdp", "trade_balance_gdp",
        lambda v: f"{v}%",
        lambda d: [("Monthly trade balance (avg)", f"${d.get('trade_balance_monthly', 'N/A')}B"), ("Quarterly GDP", f"${d.get('gdp', 'N/A')}B"), ("As of", d.get('date', 'N/A'))])
    
    # 9. Empire Premium
    premium = data.get("empire_premium", {})
    status = premium.get("status", "unknown")
    if premium.get("success"):
        html += f"""
    <div class="indicator {status}">
        <div class="indicator-title">Empire Premium (VTI/VXUS P/B Spread) <span class="status-label status-{status}">{status.upper()}</span></div>
        <div class="indicator-value">{premium.get('value')}x</div>
        <div class="indicator-details">
            <table>
                <tr><td>VTI Price-to-Book</td><td>{premium.get('vti_pb', 'N/A')}</td></tr>
                <tr><td>VXUS Price-to-Book</td><td>{premium.get('vxus_pb', 'N/A')}</td></tr>
            </table>
            <p style="font-size: 12px; color: #666;">VTI (Total US Market) vs VXUS (Total International, ex-US). Proxies for FXAIX vs FTIHX.</p>
        </div>
        <div class="data-freshness">Data as of: {premium.get('data_freshness', 'Unknown')} | Source: {premium.get('source', 'Yahoo Finance')}</div>
        <div class="threshold-note">Warning: below {THRESHOLDS['empire_premium']['warning']}x | Critical: below {THRESHOLDS['empire_premium']['critical']}x<br>{THRESHOLDS['empire_premium']['context']}</div>
    </div>
"""
    else:
        html += f"""
    <div class="indicator unknown">
        <div class="indicator-title">Empire Premium (VTI/VXUS P/B Spread) <span class="status-label status-unknown">UNKNOWN</span></div>
        <div class="indicator-value">N/A</div>
        <div class="indicator-details"><div class="error-note">Could not fetch data: {premium.get('error', 'Unknown error')}</div></div>
    </div>
"""
    
    # Performance History
    perf = data.get("performance", {})
    if perf.get("success"):
        html += """
    <h2>Market Context: Performance History</h2>
    <div class="indicator info">
        <div class="indicator-title">VTI vs VXUS Annualized Returns <span class="status-label status-info">INFO</span></div>
        <div class="indicator-details">
            <p style="font-size: 12px; color: #666; margin-bottom: 10px;">Informational only - does not trigger warnings.</p>
            <table>
                <tr><td><strong>Period</strong></td><td><strong>VTI (US)</strong></td><td><strong>VXUS (Intl)</strong></td></tr>
"""
        for period in ["1y", "3y", "5y", "10y"]:
            vti_return = perf.get(f"vti_{period}")
            vxus_return = perf.get(f"vxus_{period}")
            if vti_return is not None and vxus_return is not None:
                html += f"<tr><td>{period.upper()}</td><td>{format_change(vti_return, '%')}</td><td>{format_change(vxus_return, '%')}</td></tr>\n"
        
        html += f"""
            </table>
        </div>
        <div class="data-freshness">Source: {perf.get('source', 'Yahoo Finance')}</div>
        <div class="threshold-note">US has outperformed international for most of 2010-2024. Sustained reversal may signal dollar weakness or valuation normalization.</div>
    </div>
"""
    
    # Decision Framework
    html += """
    <h2>Decision Framework</h2>
    <div class="indicator stable">
        <p><strong>What to do with this information:</strong></p>
        <ul>
            <li><strong>All stable:</strong> No action needed. Check back next quarter.</li>
            <li><strong>1-2 warnings:</strong> Note it, but don't react to a single report.</li>
            <li><strong>Warnings for 2-3 consecutive reports:</strong> Consider shifting from 65/35 to 50/50.</li>
            <li><strong>Multiple critical signals:</strong> More aggressive rebalancing may be warranted.</li>
        </ul>
        <p style="margin-top: 15px;">These are slow-moving structural indicators. The goal is to catch sustained trends, not react to noise.</p>
    </div>
"""
    
    # Footer
    current_month = datetime.now().month
    if current_month < 4:
        next_report = f"April {datetime.now().year}"
    elif current_month < 7:
        next_report = f"July {datetime.now().year}"
    elif current_month < 10:
        next_report = f"October {datetime.now().year}"
    else:
        next_report = f"January {datetime.now().year + 1}"
    
    html += f"""
    <div class="footer">
        <p>Generated by Bretton Woods Decay v3.0<br>
        This is informational only, not financial advice.<br>
        Next scheduled report: {next_report}</p>
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
            data["china"] = {"status": "unknown", "error": "China data not found"}
            print("  China: Not found")
        
        if "japan" in treasury:
            japan = treasury["japan"]
            japan["value"] = japan["current"]
            japan["status"] = assess_status(japan["current"], "japan_treasury")
            print(f"  Japan: ${japan['current']}B - Status: {japan['status']}")
            data["japan"] = japan
        else:
            data["japan"] = {"status": "unknown", "error": "Japan data not found"}
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
    
    # 6. Interest to Revenue
    print("Fetching Interest/Revenue ratio (FRED)...")
    interest = fetch_interest_to_revenue()
    if interest.get("success"):
        interest["status"] = assess_status(interest.get("value"), "interest_to_revenue")
        print(f"  Value: {interest['value']}% - Status: {interest['status']}")
    else:
        interest["status"] = "unknown"
        print(f"  Failed: {interest.get('error')}")
    data["interest_to_revenue"] = interest
    
    # 7. Interest to Defense (Guns vs Debt)
    print("Fetching Interest/Defense ratio (Guns vs Debt)...")
    guns_debt = fetch_interest_to_defense()
    if guns_debt.get("success"):
        guns_debt["status"] = assess_status(guns_debt.get("value"), "interest_to_defense")
        print(f"  Value: {guns_debt['value']}% - Status: {guns_debt['status']}")
    else:
        guns_debt["status"] = "unknown"
        print(f"  Failed: {guns_debt.get('error')}")
    data["interest_to_defense"] = guns_debt
    
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
    
    # 9. Empire Premium (P/B Spread)
    print("Fetching Empire Premium (VTI/VXUS P/B)...")
    premium = fetch_empire_premium()
    if premium.get("success"):
        premium["status"] = assess_status(premium.get("value"), "empire_premium")
        print(f"  Value: {premium['value']}x - Status: {premium['status']}")
    else:
        premium["status"] = "unknown"
        print(f"  Failed: {premium.get('error')}")
    data["empire_premium"] = premium
    
    # 10. Performance History (informational only)
    print("Fetching Performance History (VTI/VXUS)...")
    perf = fetch_performance_history()
    if perf.get("success"):
        print(f"  VTI 1Y: {perf.get('vti_1y')}%, VXUS 1Y: {perf.get('vxus_1y')}%")
    else:
        print(f"  Failed: {perf.get('error')}")
    data["performance"] = perf
    
    # Generate report
    print()
    print("Generating report...")
    html = generate_html_report(data)
    
    # Save locally
    with open("bretton_woods_report.html", "w") as f:
        f.write(html)
    print("Saved to bretton_woods_report.html")
    
    # Determine subject
    statuses = []
    for key, d in data.items():
        if key == "performance":
            continue
        if isinstance(d, dict) and d.get("success", False):
            statuses.append(d.get("status", "unknown"))
    
    critical_count = statuses.count("critical")
    warning_count = statuses.count("warning")
    
    if critical_count > 0:
        subject = f"Bretton Woods Decay: CRITICAL ({critical_count}) - {datetime.now().strftime('%B %Y')}"
    elif warning_count > 0:
        subject = f"Bretton Woods Decay: Warning ({warning_count}) - {datetime.now().strftime('%B %Y')}"
    elif statuses:
        subject = f"Bretton Woods Decay: Stable - {datetime.now().strftime('%B %Y')}"
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
