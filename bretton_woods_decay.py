"""
Bretton Woods Decay - Semi-Annual Macro Indicator Monitor
=========================================================
Tracks key indicators of US dollar/empire structural health:

1. USD share of global foreign exchange reserves (IMF COFER)
2. China holdings of US Treasuries (Treasury TIC)
3. Japan holdings of US Treasuries (Treasury TIC)
4. DXY Dollar Index
5. US Debt-to-GDP ratio (FRED)
6. Federal interest payments as % of revenue (FRED)
7. International vs US stock performance (FTIHX vs FXAIX proxy)

Designed to run twice yearly (January and July) via GitHub Actions.
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
    "User-Agent": "BrettonWoodsDecay/1.0 (github.com/bretton-woods-decay)",
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
        "context": "Peaked at 71% in 2000, currently around 58%"
    },
    "china_treasury": {
        "warning": 700.0,
        "critical": 500.0,
        "direction": "below",
        "unit": "B",
        "description": "China holdings of US Treasuries",
        "context": "Peaked at $1.3T in 2013, now around $775B"
    },
    "japan_treasury": {
        "warning": 1000.0,
        "critical": 850.0,
        "direction": "below",
        "unit": "B",
        "description": "Japan holdings of US Treasuries",
        "context": "Largest holder, typically $1.0-1.2T"
    },
    "dxy": {
        "warning": 95.0,
        "critical": 85.0,
        "direction": "below",
        "unit": "",
        "description": "Dollar Index (DXY)",
        "context": "Measures USD vs basket of currencies. 100 is neutral-ish."
    },
    "debt_to_gdp": {
        "warning": 130.0,
        "critical": 150.0,
        "direction": "above",
        "unit": "%",
        "description": "US Federal Debt to GDP ratio",
        "context": "Was 60% in 2000, 100% in 2012, now around 120%"
    },
    "interest_to_revenue": {
        "warning": 25.0,
        "critical": 33.0,
        "direction": "above",
        "unit": "%",
        "description": "Federal interest payments as % of revenue",
        "context": "Above 33% means 1/3 of all revenue goes to interest"
    },
    "intl_vs_us_3yr": {
        "warning": 15.0,
        "critical": 30.0,
        "direction": "above",
        "unit": "%",
        "description": "International vs US stocks (3-year cumulative)",
        "context": "Positive = international outperforming US"
    }
}


# =============================================================================
# DATA FETCHING FUNCTIONS
# =============================================================================

def fetch_imf_cofer():
    """Fetch USD share of global reserves from IMF."""
    try:
        # IMF SDMX API - USD share of allocated reserves
        # Try multiple URL formats as IMF has changed their API
        urls_to_try = [
            "https://dataservices.imf.org/REST/SDMX_JSON.svc/CompactData/COFER/Q.W00.RAXGFXARUSDRT_PT",
            "http://dataservices.imf.org/REST/SDMX_JSON.svc/CompactData/COFER/Q.W00.RAXGFXARUSDRT_PT",
        ]
        
        for url in urls_to_try:
            try:
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
                        
                        # Get 1-year ago (4 quarters back)
                        year_ago = None
                        if len(observations) >= 5:
                            year_ago = float(observations[-5].get("@OBS_VALUE", 0))
                        
                        # Get 5-years ago (20 quarters back)
                        five_year_ago = None
                        if len(observations) >= 21:
                            five_year_ago = float(observations[-21].get("@OBS_VALUE", 0))
                        
                        return {
                            "success": True,
                            "value": round(current, 1),
                            "period": period,
                            "year_ago": round(year_ago, 1) if year_ago else None,
                            "five_year_ago": round(five_year_ago, 1) if five_year_ago else None,
                            "change_1y": round(current - year_ago, 2) if year_ago else None,
                            "change_5y": round(current - five_year_ago, 2) if five_year_ago else None
                        }
            except Exception:
                continue
        
        return {"success": False, "error": "IMF API unavailable"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def fetch_treasury_holdings():
    """Fetch China and Japan Treasury holdings from TIC data."""
    try:
        url = "https://ticdata.treasury.gov/Publish/mfh.txt"
        response = requests.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            
            china_data = None
            japan_data = None
            data_date = None
            
            for line in lines:
                # Skip headers and separators
                if not line.strip() or '------' in line:
                    continue
                if line.startswith('MAJOR') or line.startswith('HOLDINGS'):
                    continue
                    
                # Look for the header line with dates
                if line.strip().startswith('Country'):
                    # Extract the first date column (most recent)
                    parts = line.split()
                    # Find something that looks like a month abbreviation
                    for i, part in enumerate(parts):
                        if part in ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']:
                            # Next part should be year
                            if i + 1 < len(parts):
                                data_date = f"{part} {parts[i+1]}"
                            else:
                                data_date = part
                            break
                    continue
                
                # Parse country data
                line_lower = line.lower().strip()
                
                # Match Japan (must start with Japan)
                if line_lower.startswith('japan'):
                    values = re.findall(r'[\d.]+', line)
                    if values:
                        japan_data = {
                            "current": float(values[0]),
                            "6mo_ago": float(values[6]) if len(values) > 6 else None,
                            "12mo_ago": float(values[12]) if len(values) > 12 else None
                        }
                
                # Match China, Mainland
                if 'china' in line_lower and 'mainland' in line_lower:
                    values = re.findall(r'[\d.]+', line)
                    if values:
                        china_data = {
                            "current": float(values[0]),
                            "6mo_ago": float(values[6]) if len(values) > 6 else None,
                            "12mo_ago": float(values[12]) if len(values) > 12 else None
                        }
            
            result = {"success": True, "data_date": data_date}
            
            if china_data:
                china_data["change_6mo"] = round(china_data["current"] - china_data["6mo_ago"], 1) if china_data["6mo_ago"] else None
                china_data["change_12mo"] = round(china_data["current"] - china_data["12mo_ago"], 1) if china_data["12mo_ago"] else None
                result["china"] = china_data
            
            if japan_data:
                japan_data["change_6mo"] = round(japan_data["current"] - japan_data["6mo_ago"], 1) if japan_data["6mo_ago"] else None
                japan_data["change_12mo"] = round(japan_data["current"] - japan_data["12mo_ago"], 1) if japan_data["12mo_ago"] else None
                result["japan"] = japan_data
            
            return result
        
        return {"success": False, "error": f"API returned status {response.status_code}"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def fetch_fred_series(series_id, name):
    """Fetch a data series from FRED (no API key needed for basic access)."""
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
                            "value": round(value, 1),  # Round to 1 decimal
                            "date": date,
                            "name": name
                        }
        
        return {"success": False, "error": f"Could not fetch {name}", "name": name}
    except Exception as e:
        return {"success": False, "error": str(e), "name": name}


def fetch_debt_to_gdp():
    """Fetch US Federal Debt to GDP ratio from FRED."""
    # GFDEGDQ188S = Federal Debt: Total Public Debt as Percent of GDP
    return fetch_fred_series("GFDEGDQ188S", "Debt-to-GDP")


def fetch_interest_to_revenue():
    """
    Calculate interest payments as % of revenue.
    This requires two series and a calculation.
    """
    try:
        # A091RC1Q027SBEA = Federal government interest payments
        # W006RC1Q027SBEA = Federal government current receipts (revenue)
        
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
                    "date": i_date
                }
        
        return {"success": False, "error": "Could not calculate interest/revenue ratio"}
    except Exception as e:
        return {"success": False, "error": str(e)}


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
            
            # Filter out None values and get latest
            valid_data = [(t, c) for t, c in zip(timestamps, closes) if c is not None]
            
            if valid_data:
                latest_ts, current = valid_data[-1]
                latest_date = datetime.fromtimestamp(latest_ts).strftime("%Y-%m-%d")
                
                # Get 1 year ago (roughly 252 trading days)
                year_ago = None
                if len(valid_data) > 252:
                    year_ago = valid_data[-252][1]
                
                # Get 3 years ago
                three_year_ago = None
                if len(valid_data) > 756:
                    three_year_ago = valid_data[-756][1]
                
                return {
                    "success": True,
                    "value": round(current, 1),
                    "date": latest_date,
                    "year_ago": round(year_ago, 1) if year_ago else None,
                    "three_year_ago": round(three_year_ago, 1) if three_year_ago else None,
                    "change_1y": round(current - year_ago, 1) if year_ago else None,
                    "change_3y": round(current - three_year_ago, 1) if three_year_ago else None
                }
        
        return {"success": False, "error": f"Could not fetch DXY (status {response.status_code})"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def fetch_intl_vs_us_performance():
    """
    Compare international vs US stock performance.
    Uses VXUS (international) vs VTI (US) as proxies for FTIHX vs FXAIX.
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
            
            # 1 year ago
            vxus_1y = vxus_data[-252][1] if len(vxus_data) > 252 else None
            vti_1y = vti_data[-252][1] if len(vti_data) > 252 else None
            
            # 3 years ago
            vxus_3y = vxus_data[-756][1] if len(vxus_data) > 756 else None
            vti_3y = vti_data[-756][1] if len(vti_data) > 756 else None
            
            result = {
                "success": True,
                "date": datetime.fromtimestamp(vxus_data[-1][0]).strftime("%Y-%m-%d")
            }
            
            # Calculate relative performance (international vs US)
            # Positive = international outperforming
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
        
        return {"success": False, "error": "Could not fetch ETF data"}
    except Exception as e:
        return {"success": False, "error": str(e)}


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
    
    # Collect all statuses (only from indicators that succeeded)
    statuses = []
    for key in data:
        if isinstance(data[key], dict):
            status = data[key].get("status")
            # Only count statuses from successful fetches
            if status and status != "unknown":
                statuses.append(status)
    
    if "critical" in statuses:
        overall = "CRITICAL - Review your allocation"
        overall_color = "#dc3545"
    elif "warning" in statuses:
        overall = "WARNING - Monitor closely"
        overall_color = "#e67e22"
    elif not statuses:
        overall = "DATA UNAVAILABLE - Check API connections"
        overall_color = "#95a5a6"
    else:
        overall = "STABLE - No immediate concerns"
        overall_color = "#27ae60"
    
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
        }}
        .indicator {{ 
            background: #f8f9fa; 
            padding: 15px; 
            margin: 15px 0; 
            border-radius: 6px; 
            border-left: 4px solid #ddd; 
        }}
        .indicator.critical {{ border-left-color: #dc3545; }}
        .indicator.warning {{ border-left-color: #e67e22; }}
        .indicator.stable {{ border-left-color: #27ae60; }}
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
        .status-warning {{ background: #e67e22; color: white; }}
        .status-stable {{ background: #27ae60; color: white; }}
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
    </style>
</head>
<body>
    <h1>Bretton Woods Decay Report</h1>
    <p>Report Date: {today}</p>
    
    <div class="overall-status">
        <strong>Overall Assessment:</strong> {overall}
    </div>
"""
    
    # 1. USD Reserve Share
    cofer = data.get("cofer", {})
    status = cofer.get("status", "unknown")
    if cofer.get("success"):
        html += f"""
    <div class="indicator {status}">
        <div class="indicator-title">
            USD Share of Global Reserves
            <span class="status-label status-{status}">{status}</span>
        </div>
        <div class="indicator-value">{cofer.get('value', 'N/A')}%</div>
        <div class="indicator-details">
            <table>
                <tr><td>Period</td><td>{cofer.get('period', 'N/A')}</td></tr>
                <tr><td>1-year change</td><td>{format_change(cofer.get('change_1y'), '%')}</td></tr>
                <tr><td>5-year change</td><td>{format_change(cofer.get('change_5y'), '%')}</td></tr>
            </table>
        </div>
        <div class="threshold-note">
            Warning: below {THRESHOLDS['usd_reserve_share']['warning']}% | 
            Critical: below {THRESHOLDS['usd_reserve_share']['critical']}%<br>
            {THRESHOLDS['usd_reserve_share']['context']}
        </div>
    </div>
"""
    else:
        html += f"""
    <div class="indicator unknown">
        <div class="indicator-title">
            USD Share of Global Reserves
            <span class="status-label status-unknown">unavailable</span>
        </div>
        <div class="indicator-details">
            Could not fetch data: {cofer.get('error', 'Unknown error')}<br>
            Source: IMF COFER database
        </div>
    </div>
"""
    
    # 2. China Treasury Holdings
    china = data.get("china", {})
    status = china.get("status", "unknown")
    if china.get("current") or china.get("value"):
        val = china.get('value') or china.get('current', 'N/A')
        html += f"""
    <div class="indicator {status}">
        <div class="indicator-title">
            China Treasury Holdings
            <span class="status-label status-{status}">{status}</span>
        </div>
        <div class="indicator-value">${val}B</div>
        <div class="indicator-details">
            <table>
                <tr><td>6-month change</td><td>{format_change(china.get('change_6mo'), 'B')}</td></tr>
                <tr><td>12-month change</td><td>{format_change(china.get('change_12mo'), 'B')}</td></tr>
            </table>
            <p>Trend: {'Selling' if (china.get('change_12mo') or 0) < 0 else 'Accumulating' if (china.get('change_12mo') or 0) > 0 else 'Flat'}</p>
        </div>
        <div class="threshold-note">
            Warning: below ${THRESHOLDS['china_treasury']['warning']}B | 
            Critical: below ${THRESHOLDS['china_treasury']['critical']}B<br>
            {THRESHOLDS['china_treasury']['context']}
        </div>
    </div>
"""
    else:
        html += f"""
    <div class="indicator unknown">
        <div class="indicator-title">
            China Treasury Holdings
            <span class="status-label status-unknown">unavailable</span>
        </div>
        <div class="indicator-details">
            Could not fetch data: {china.get('error', 'Unknown error')}<br>
            Source: Treasury TIC data
        </div>
    </div>
"""
    
    # 3. Japan Treasury Holdings
    japan = data.get("japan", {})
    status = japan.get("status", "unknown")
    if japan.get("current") or japan.get("value"):
        val = japan.get('value') or japan.get('current', 'N/A')
        html += f"""
    <div class="indicator {status}">
        <div class="indicator-title">
            Japan Treasury Holdings
            <span class="status-label status-{status}">{status}</span>
        </div>
        <div class="indicator-value">${val}B</div>
        <div class="indicator-details">
            <table>
                <tr><td>6-month change</td><td>{format_change(japan.get('change_6mo'), 'B')}</td></tr>
                <tr><td>12-month change</td><td>{format_change(japan.get('change_12mo'), 'B')}</td></tr>
            </table>
            <p>Trend: {'Selling' if (japan.get('change_12mo') or 0) < 0 else 'Accumulating' if (japan.get('change_12mo') or 0) > 0 else 'Flat'}</p>
        </div>
        <div class="threshold-note">
            Warning: below ${THRESHOLDS['japan_treasury']['warning']}B | 
            Critical: below ${THRESHOLDS['japan_treasury']['critical']}B<br>
            {THRESHOLDS['japan_treasury']['context']}
        </div>
    </div>
"""
    else:
        html += f"""
    <div class="indicator unknown">
        <div class="indicator-title">
            Japan Treasury Holdings
            <span class="status-label status-unknown">unavailable</span>
        </div>
        <div class="indicator-details">
            Could not fetch data: {japan.get('error', 'Unknown error')}<br>
            Source: Treasury TIC data
        </div>
    </div>
"""
    
    # 4. DXY
    dxy = data.get("dxy", {})
    status = dxy.get("status", "unknown")
    if dxy.get("success"):
        html += f"""
    <div class="indicator {status}">
        <div class="indicator-title">
            Dollar Index (DXY)
            <span class="status-label status-{status}">{status}</span>
        </div>
        <div class="indicator-value">{dxy.get('value', 'N/A')}</div>
        <div class="indicator-details">
            <table>
                <tr><td>1-year change</td><td>{format_change(dxy.get('change_1y'))}</td></tr>
                <tr><td>3-year change</td><td>{format_change(dxy.get('change_3y'))}</td></tr>
            </table>
        </div>
        <div class="threshold-note">
            Warning: below {THRESHOLDS['dxy']['warning']} | 
            Critical: below {THRESHOLDS['dxy']['critical']}<br>
            {THRESHOLDS['dxy']['context']}
        </div>
    </div>
"""
    else:
        html += f"""
    <div class="indicator unknown">
        <div class="indicator-title">
            Dollar Index (DXY)
            <span class="status-label status-unknown">unavailable</span>
        </div>
        <div class="indicator-details">
            Could not fetch data: {dxy.get('error', 'Unknown error')}<br>
            Source: Yahoo Finance
        </div>
    </div>
"""
    
    # 5. Debt to GDP
    debt = data.get("debt_to_gdp", {})
    status = debt.get("status", "unknown")
    if debt.get("success"):
        html += f"""
    <div class="indicator {status}">
        <div class="indicator-title">
            US Debt-to-GDP Ratio
            <span class="status-label status-{status}">{status}</span>
        </div>
        <div class="indicator-value">{debt.get('value', 'N/A')}%</div>
        <div class="indicator-details">
            As of: {debt.get('date', 'N/A')}
        </div>
        <div class="threshold-note">
            Warning: above {THRESHOLDS['debt_to_gdp']['warning']}% | 
            Critical: above {THRESHOLDS['debt_to_gdp']['critical']}%<br>
            {THRESHOLDS['debt_to_gdp']['context']}
        </div>
    </div>
"""
    else:
        html += f"""
    <div class="indicator unknown">
        <div class="indicator-title">
            US Debt-to-GDP Ratio
            <span class="status-label status-unknown">unavailable</span>
        </div>
        <div class="indicator-details">
            Could not fetch data: {debt.get('error', 'Unknown error')}<br>
            Source: FRED (St. Louis Fed)
        </div>
    </div>
"""
    
    # 6. Interest to Revenue
    interest = data.get("interest_to_revenue", {})
    status = interest.get("status", "unknown")
    if interest.get("success"):
        html += f"""
    <div class="indicator {status}">
        <div class="indicator-title">
            Interest Payments as % of Revenue
            <span class="status-label status-{status}">{status}</span>
        </div>
        <div class="indicator-value">{interest.get('value', 'N/A')}%</div>
        <div class="indicator-details">
            As of: {interest.get('date', 'N/A')}
        </div>
        <div class="threshold-note">
            Warning: above {THRESHOLDS['interest_to_revenue']['warning']}% | 
            Critical: above {THRESHOLDS['interest_to_revenue']['critical']}%<br>
            {THRESHOLDS['interest_to_revenue']['context']}
        </div>
    </div>
"""
    else:
        html += f"""
    <div class="indicator unknown">
        <div class="indicator-title">
            Interest Payments as % of Revenue
            <span class="status-label status-unknown">unavailable</span>
        </div>
        <div class="indicator-details">
            Could not fetch data: {interest.get('error', 'Unknown error')}<br>
            Source: FRED (St. Louis Fed)
        </div>
    </div>
"""
    
    # 7. International vs US Performance
    perf = data.get("intl_vs_us", {})
    status = perf.get("status", "unknown")
    if perf.get("success"):
        diff_3y = perf.get('diff_3y', 0) or 0
        direction = "International outperforming" if diff_3y > 0 else "US outperforming" if diff_3y < 0 else "Roughly even"
        html += f"""
    <div class="indicator {status}">
        <div class="indicator-title">
            International vs US Stocks (3-Year)
            <span class="status-label status-{status}">{status}</span>
        </div>
        <div class="indicator-value">{format_change(perf.get('diff_3y'), '%')}</div>
        <div class="indicator-details">
            <table>
                <tr><td>International 3yr return (VXUS)</td><td>{format_change(perf.get('intl_return_3y'), '%')}</td></tr>
                <tr><td>US 3yr return (VTI)</td><td>{format_change(perf.get('us_return_3y'), '%')}</td></tr>
                <tr><td>1-year difference</td><td>{format_change(perf.get('diff_1y'), '%')}</td></tr>
            </table>
            <p>{direction}</p>
        </div>
        <div class="threshold-note">
            Warning: International ahead by {THRESHOLDS['intl_vs_us_3yr']['warning']}%+ | 
            Critical: ahead by {THRESHOLDS['intl_vs_us_3yr']['critical']}%+<br>
            {THRESHOLDS['intl_vs_us_3yr']['context']}
        </div>
    </div>
"""
    else:
        html += f"""
    <div class="indicator unknown">
        <div class="indicator-title">
            International vs US Stocks (3-Year)
            <span class="status-label status-unknown">unavailable</span>
        </div>
        <div class="indicator-details">
            Could not fetch data: {perf.get('error', 'Unknown error')}<br>
            Source: Yahoo Finance (VXUS vs VTI)
        </div>
    </div>
"""
    
    # Decision Framework
    html += """
    <h2>Decision Framework</h2>
    <div class="indicator stable">
        <p><strong>What to do with this information:</strong></p>
        <ul>
            <li><strong>All stable:</strong> No action needed. Check back in 6 months.</li>
            <li><strong>1-2 warnings:</strong> Note it, but don't react to a single report. Watch for trends.</li>
            <li><strong>Warnings for 2-3 consecutive reports:</strong> Consider gradually shifting from 65/35 to 50/50 domestic/international.</li>
            <li><strong>Multiple critical signals:</strong> More aggressive rebalancing toward international may be warranted.</li>
        </ul>
        <p>Remember: These are slow-moving structural indicators. Empire decline happens over decades, not months.</p>
    </div>
"""
    
    # Footer
    next_month = "July" if datetime.now().month <= 6 else "January"
    next_year = datetime.now().year if datetime.now().month <= 6 else datetime.now().year + 1
    
    html += f"""
    <div class="footer">
        <p>Generated by Bretton Woods Decay v2.1<br>
        This is informational only, not financial advice.<br>
        Next scheduled report: {next_month} {next_year}</p>
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
    print("Bretton Woods Decay - Semi-Annual Report")
    print("=" * 60)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    data = {}
    
    # 1. IMF COFER
    print("Fetching USD reserve share (IMF COFER)...")
    cofer = fetch_imf_cofer()
    if cofer.get("success"):
        cofer["status"] = assess_status(cofer.get("value"), "usd_reserve_share")
        print(f"  Value: {cofer['value']}% - Status: {cofer['status']}")
    else:
        cofer["status"] = "unknown"
        print(f"  Failed: {cofer.get('error')}")
    data["cofer"] = cofer
    
    # 2 & 3. Treasury Holdings
    print("Fetching Treasury holdings (TIC)...")
    treasury = fetch_treasury_holdings()
    
    if treasury.get("success"):
        print(f"  Data date: {treasury.get('data_date', 'Unknown')}")
        
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
    
    # 7. International vs US Performance
    print("Fetching International vs US performance...")
    perf = fetch_intl_vs_us_performance()
    if perf.get("success"):
        perf["status"] = assess_status(perf.get("value"), "intl_vs_us_3yr")
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
    
    # Determine subject
    statuses = [d.get("status") for d in data.values() if isinstance(d, dict) and d.get("status") != "unknown"]
    if "critical" in statuses:
        subject = f"Bretton Woods Decay: CRITICAL - {datetime.now().strftime('%B %Y')}"
    elif "warning" in statuses:
        subject = f"Bretton Woods Decay: Warning - {datetime.now().strftime('%B %Y')}"
    else:
        subject = f"Bretton Woods Decay: Stable - {datetime.now().strftime('%B %Y')}"
    
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
