"""
Bretton Woods Decay - Semi-Annual Macro Indicator Monitor
=========================================================
Tracks key indicators of US dollar/empire structural health:
1. USD share of global foreign exchange reserves (IMF COFER)
2. Major foreign holders of US Treasuries (Treasury TIC data)
3. Macro fund positioning (SEC 13F filing dates for Bridgewater, Berkshire)

Designed to run twice yearly (January and July) via GitHub Actions.
Sends a formatted email report via iCloud SMTP.
"""

import os
import requests
import json
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import smtplib

# =============================================================================
# CONFIGURATION
# =============================================================================

# Email settings (from GitHub Secrets)
ICLOUD_EMAIL = os.environ.get("ICLOUD_EMAIL")
ICLOUD_PASSWORD = os.environ.get("ICLOUD_PASSWORD")  # App-specific password
TO_EMAIL = os.environ.get("TO_EMAIL", ICLOUD_EMAIL)  # Recipient (defaults to sender if not set)

# Request headers (SEC requires a User-Agent with contact info)
HEADERS = {
    "User-Agent": "BrettonWoodsDecay/1.0",
    "Accept": "application/json"
}

# Thresholds for concern
THRESHOLDS = {
    "usd_reserve_share": {
        "warning": 55.0,      # Percent - below this is concerning
        "critical": 50.0,     # Percent - below this is very concerning
        "context": "USD share peaked at ~71% in 2000, has declined to ~58% as of 2024"
    },
    "china_treasury_holdings": {
        "warning": 750.0,     # Billions USD - below this suggests accelerated selling
        "critical": 600.0,    # Billions USD - major de-dollarization signal
        "context": "China held ~$1.3T at peak (2013), now around $800B"
    },
    "japan_treasury_holdings": {
        "warning": 1000.0,    # Billions USD
        "critical": 800.0,    # Billions USD
        "context": "Japan is the largest holder, typically ~$1.1T"
    },
    "top10_change_6mo": {
        "warning": -100.0,    # Billions USD - net outflow over 6 months
        "critical": -200.0,   # Billions USD - significant coordinated selling
        "context": "Large net outflows suggest coordinated de-dollarization"
    }
}

# Fund CIKs for 13F tracking
FUNDS = {
    "Bridgewater Associates": "1350694",
    "Berkshire Hathaway": "1067983"
}


# =============================================================================
# DATA FETCHING FUNCTIONS
# =============================================================================

def fetch_imf_cofer_data():
    """
    Fetch USD share of global foreign exchange reserves from IMF COFER database.
    Returns the most recent quarterly data available.
    
    The IMF SDMX API uses this structure:
    - Dataflow: COFER
    - Dimensions vary by indicator
    
    We'll try to fetch the USD share percentage directly.
    """
    try:
        # IMF SDMX REST API endpoint for COFER data
        # Format: CompactData/COFER/[frequency].[reference_area].[indicator]
        # We want quarterly (Q), World (W00), USD share of allocated reserves
        
        # Try the newer data.imf.org API first
        url = "http://dataservices.imf.org/REST/SDMX_JSON.svc/CompactData/COFER/Q.W00.RAXGFXARUSDRT_PT"
        
        response = requests.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            # Navigate the SDMX-JSON structure to extract observations
            try:
                series = data["CompactData"]["DataSet"]["Series"]
                observations = series.get("Obs", [])
                
                if isinstance(observations, dict):
                    observations = [observations]
                
                if observations:
                    # Get the most recent observation
                    latest = observations[-1]
                    period = latest.get("@TIME_PERIOD", "Unknown")
                    value = float(latest.get("@OBS_VALUE", 0))
                    
                    # Get previous period for comparison
                    prev_value = None
                    if len(observations) >= 5:  # ~1 year ago (4 quarters)
                        prev_obs = observations[-5]
                        prev_value = float(prev_obs.get("@OBS_VALUE", 0))
                    
                    return {
                        "success": True,
                        "current_value": value,
                        "period": period,
                        "year_ago_value": prev_value,
                        "change_1y": value - prev_value if prev_value else None
                    }
            except (KeyError, TypeError, IndexError) as e:
                return {"success": False, "error": f"Error parsing IMF data: {e}"}
        
        return {"success": False, "error": f"IMF API returned status {response.status_code}"}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def fetch_treasury_tic_data():
    """
    Fetch Major Foreign Holders of Treasury Securities from Treasury TIC data.
    Returns holdings for top countries and calculates recent changes.
    """
    try:
        # Primary URL for the MFH (Major Foreign Holders) data
        url = "https://ticdata.treasury.gov/Publish/mfh.txt"
        
        response = requests.get(url, headers=HEADERS, timeout=30)
        
        if response.status_code == 200:
            lines = response.text.strip().split('\n')
            
            # Parse the header to understand column structure
            # Format is typically: Country, then monthly values going back
            data = {}
            header_found = False
            months = []
            
            for line in lines:
                # Skip empty lines and header text
                if not line.strip() or line.startswith('MAJOR') or line.startswith('HOLDINGS'):
                    continue
                if line.startswith('Country') or '------' in line:
                    if 'Country' in line:
                        # Parse month headers
                        parts = line.split()
                        months = parts[1:]  # Skip 'Country'
                    header_found = True
                    continue
                
                if header_found and line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        # Country name might have spaces, values are at the end
                        # Find where numbers start
                        values = []
                        name_parts = []
                        for part in parts:
                            try:
                                val = float(part.replace(',', ''))
                                values.append(val)
                            except ValueError:
                                if not values:  # Still in name
                                    name_parts.append(part)
                        
                        country = ' '.join(name_parts)
                        if country and values:
                            data[country] = {
                                "current": values[0] if values else None,
                                "6mo_ago": values[6] if len(values) > 6 else None,
                                "12mo_ago": values[12] if len(values) > 12 else None,
                                "all_values": values[:13] if len(values) >= 13 else values
                            }
            
            # Extract key countries
            result = {
                "success": True,
                "data_date": months[0] if months else "Unknown",
                "countries": {}
            }
            
            key_countries = ["Japan", "China, Mainland", "United Kingdom", "Belgium", 
                           "Luxembourg", "Switzerland", "Cayman Islands", "Canada",
                           "Taiwan", "India", "France", "Brazil"]
            
            for country in key_countries:
                if country in data:
                    result["countries"][country] = data[country]
                # Also check without comma
                alt_name = country.replace(", Mainland", "").replace(", ", " ")
                if alt_name in data and country not in result["countries"]:
                    result["countries"][country] = data[alt_name]
            
            # Calculate totals for top 10
            sorted_countries = sorted(data.items(), key=lambda x: x[1]["current"] or 0, reverse=True)[:10]
            top10_current = sum(c[1]["current"] or 0 for c in sorted_countries)
            top10_6mo = sum(c[1]["6mo_ago"] or 0 for c in sorted_countries if c[1]["6mo_ago"])
            
            result["top10_current"] = top10_current
            result["top10_6mo_ago"] = top10_6mo
            result["top10_change"] = top10_current - top10_6mo if top10_6mo else None
            result["top10_countries"] = [c[0] for c in sorted_countries]
            
            return result
            
        return {"success": False, "error": f"Treasury API returned status {response.status_code}"}
        
    except Exception as e:
        return {"success": False, "error": str(e)}


def fetch_sec_13f_info(fund_name, cik):
    """
    Fetch latest 13F filing info from SEC EDGAR for a given fund.
    Returns the filing date and a link to the filing.
    """
    try:
        # SEC requires CIK to be padded to 10 digits
        padded_cik = cik.zfill(10)
        url = f"https://data.sec.gov/submissions/CIK{padded_cik}.json"
        
        # SEC requires a descriptive User-Agent
        sec_headers = {
            "User-Agent": f"EmpireWatch/1.0 ({ICLOUD_EMAIL})",
            "Accept": "application/json"
        }
        
        response = requests.get(url, headers=sec_headers, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            
            # Find the most recent 13F filing
            filings = data.get("filings", {}).get("recent", {})
            forms = filings.get("form", [])
            dates = filings.get("filingDate", [])
            accessions = filings.get("accessionNumber", [])
            
            for i, form in enumerate(forms):
                if "13F" in form:
                    filing_date = dates[i] if i < len(dates) else "Unknown"
                    accession = accessions[i] if i < len(accessions) else ""
                    
                    # Build URL to the filing
                    accession_clean = accession.replace("-", "")
                    filing_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={cik}&type=13F&dateb=&owner=exclude&count=10"
                    
                    return {
                        "success": True,
                        "fund_name": fund_name,
                        "latest_13f_date": filing_date,
                        "filing_url": filing_url
                    }
            
            return {"success": False, "fund_name": fund_name, "error": "No 13F filings found"}
            
        return {"success": False, "fund_name": fund_name, "error": f"SEC API returned status {response.status_code}"}
        
    except Exception as e:
        return {"success": False, "fund_name": fund_name, "error": str(e)}


# =============================================================================
# ANALYSIS FUNCTIONS
# =============================================================================

def analyze_cofer_data(cofer_result):
    """Analyze IMF COFER data and generate assessment."""
    if not cofer_result.get("success"):
        return {
            "status": "unknown",
            "icon": "❓",
            "summary": f"Could not fetch IMF data: {cofer_result.get('error', 'Unknown error')}",
            "details": []
        }
    
    value = cofer_result["current_value"]
    change = cofer_result.get("change_1y")
    
    thresholds = THRESHOLDS["usd_reserve_share"]
    
    if value < thresholds["critical"]:
        status = "critical"
        icon = "🔴"
        summary = f"USD reserve share at {value:.1f}% - CRITICAL (below {thresholds['critical']}%)"
    elif value < thresholds["warning"]:
        status = "warning"
        icon = "🟡"
        summary = f"USD reserve share at {value:.1f}% - WARNING (below {thresholds['warning']}%)"
    else:
        status = "stable"
        icon = "🟢"
        summary = f"USD reserve share at {value:.1f}% - Stable"
    
    details = [
        f"Period: {cofer_result['period']}",
        f"Current: {value:.2f}%"
    ]
    
    if change is not None:
        direction = "↓" if change < 0 else "↑" if change > 0 else "→"
        details.append(f"1-year change: {direction} {abs(change):.2f}%")
    
    details.append(f"Context: {thresholds['context']}")
    
    return {
        "status": status,
        "icon": icon,
        "summary": summary,
        "details": details,
        "value": value
    }


def analyze_treasury_data(tic_result):
    """Analyze Treasury TIC data and generate assessment."""
    if not tic_result.get("success"):
        return {
            "status": "unknown",
            "icon": "❓",
            "summary": f"Could not fetch Treasury data: {tic_result.get('error', 'Unknown error')}",
            "details": []
        }
    
    analyses = []
    overall_status = "stable"
    
    # Check China holdings
    china = tic_result.get("countries", {}).get("China, Mainland", {})
    if china.get("current"):
        china_val = china["current"]
        thresh = THRESHOLDS["china_treasury_holdings"]
        
        if china_val < thresh["critical"]:
            status = "critical"
            analyses.append(("🔴", f"China: ${china_val:.0f}B - CRITICAL"))
            overall_status = "critical"
        elif china_val < thresh["warning"]:
            status = "warning"
            analyses.append(("🟡", f"China: ${china_val:.0f}B - Below warning threshold"))
            if overall_status != "critical":
                overall_status = "warning"
        else:
            analyses.append(("🟢", f"China: ${china_val:.0f}B - Stable"))
    
    # Check Japan holdings
    japan = tic_result.get("countries", {}).get("Japan", {})
    if japan.get("current"):
        japan_val = japan["current"]
        thresh = THRESHOLDS["japan_treasury_holdings"]
        
        if japan_val < thresh["critical"]:
            analyses.append(("🔴", f"Japan: ${japan_val:.0f}B - CRITICAL"))
            overall_status = "critical"
        elif japan_val < thresh["warning"]:
            analyses.append(("🟡", f"Japan: ${japan_val:.0f}B - Below warning threshold"))
            if overall_status != "critical":
                overall_status = "warning"
        else:
            analyses.append(("🟢", f"Japan: ${japan_val:.0f}B - Stable"))
    
    # Check top 10 aggregate change
    top10_change = tic_result.get("top10_change")
    if top10_change is not None:
        thresh = THRESHOLDS["top10_change_6mo"]
        
        if top10_change < thresh["critical"]:
            analyses.append(("🔴", f"Top 10 holders 6-month change: ${top10_change:.0f}B - SIGNIFICANT OUTFLOW"))
            overall_status = "critical"
        elif top10_change < thresh["warning"]:
            analyses.append(("🟡", f"Top 10 holders 6-month change: ${top10_change:.0f}B - Notable outflow"))
            if overall_status != "critical":
                overall_status = "warning"
        else:
            direction = "+" if top10_change >= 0 else ""
            analyses.append(("🟢", f"Top 10 holders 6-month change: {direction}${top10_change:.0f}B"))
    
    # Build summary
    icon = "🔴" if overall_status == "critical" else "🟡" if overall_status == "warning" else "🟢"
    
    return {
        "status": overall_status,
        "icon": icon,
        "summary": f"Foreign Treasury Holdings as of {tic_result.get('data_date', 'Unknown')}",
        "analyses": analyses,
        "top10": tic_result.get("top10_countries", [])
    }


# =============================================================================
# EMAIL GENERATION
# =============================================================================

def generate_html_report(cofer_analysis, treasury_analysis, fund_filings):
    """Generate the HTML email report."""
    
    today = datetime.now().strftime('%B %d, %Y')
    
    # Determine overall status
    statuses = [cofer_analysis["status"], treasury_analysis["status"]]
    if "critical" in statuses:
        overall = "CRITICAL - Action may be warranted"
        overall_color = "#dc3545"
    elif "warning" in statuses:
        overall = "WARNING - Monitor closely"
        overall_color = "#ffc107"
    else:
        overall = "STABLE - No immediate concerns"
        overall_color = "#28a745"
    
    # Build HTML
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               max-width: 700px; margin: 0 auto; padding: 20px; color: #333; }}
        h1 {{ color: #1a1a1a; border-bottom: 2px solid #ddd; padding-bottom: 10px; }}
        h2 {{ color: #444; margin-top: 30px; }}
        .overall-status {{ background: {overall_color}; color: white; padding: 15px; 
                          border-radius: 8px; margin: 20px 0; font-size: 18px; }}
        .section {{ background: #f8f9fa; padding: 15px; margin: 15px 0; border-radius: 8px; 
                   border-left: 4px solid #ddd; }}
        .section.critical {{ border-left-color: #dc3545; }}
        .section.warning {{ border-left-color: #ffc107; }}
        .section.stable {{ border-left-color: #28a745; }}
        .detail {{ margin: 5px 0; padding: 3px 0; }}
        .threshold-info {{ font-size: 12px; color: #666; margin-top: 10px; 
                          padding-top: 10px; border-top: 1px solid #ddd; }}
        .fund-link {{ color: #0066cc; }}
        ul {{ padding-left: 20px; }}
        li {{ margin: 8px 0; }}
        .footer {{ margin-top: 40px; padding-top: 20px; border-top: 1px solid #ddd; 
                  font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <h1>🏛️ Bretton Woods Decay Report</h1>
    <p><strong>Report Date:</strong> {today}</p>
    
    <div class="overall-status">
        <strong>Overall Assessment:</strong> {overall}
    </div>
    
    <h2>1. USD Global Reserve Share (IMF COFER)</h2>
    <div class="section {cofer_analysis['status']}">
        <strong>{cofer_analysis['icon']} {cofer_analysis['summary']}</strong>
        <ul>
"""
    
    for detail in cofer_analysis.get("details", []):
        html += f"            <li class='detail'>{detail}</li>\n"
    
    html += f"""
        </ul>
        <div class="threshold-info">
            <strong>Thresholds:</strong> Warning below {THRESHOLDS['usd_reserve_share']['warning']}%, 
            Critical below {THRESHOLDS['usd_reserve_share']['critical']}%
        </div>
    </div>
    
    <h2>2. Foreign Holdings of US Treasuries</h2>
    <div class="section {treasury_analysis['status']}">
        <strong>{treasury_analysis['icon']} {treasury_analysis['summary']}</strong>
        <ul>
"""
    
    for icon, text in treasury_analysis.get("analyses", []):
        html += f"            <li class='detail'>{icon} {text}</li>\n"
    
    if treasury_analysis.get("top10"):
        html += f"""
        </ul>
        <p><strong>Current Top 10 Holders:</strong> {', '.join(treasury_analysis['top10'][:5])}...</p>
        <div class="threshold-info">
            <strong>Key Thresholds:</strong><br>
            • China Warning: &lt;${THRESHOLDS['china_treasury_holdings']['warning']:.0f}B, 
              Critical: &lt;${THRESHOLDS['china_treasury_holdings']['critical']:.0f}B<br>
            • Japan Warning: &lt;${THRESHOLDS['japan_treasury_holdings']['warning']:.0f}B, 
              Critical: &lt;${THRESHOLDS['japan_treasury_holdings']['critical']:.0f}B<br>
            • Top 10 6-month change: Warning &lt;${THRESHOLDS['top10_change_6mo']['warning']:.0f}B, 
              Critical &lt;${THRESHOLDS['top10_change_6mo']['critical']:.0f}B
        </div>
    </div>
"""
    else:
        html += """
        </ul>
    </div>
"""
    
    # Fund filings section
    html += """
    <h2>3. Macro Fund 13F Filings</h2>
    <div class="section stable">
        <p>Latest quarterly 13F filings from major macro-focused funds. 
        Review these to see how institutional investors are positioned.</p>
        <ul>
"""
    
    for filing in fund_filings:
        if filing.get("success"):
            html += f"""
            <li><strong>{filing['fund_name']}</strong><br>
                Latest 13F: {filing['latest_13f_date']}<br>
                <a href="{filing['filing_url']}" class="fund-link">View filings on SEC EDGAR →</a>
            </li>
"""
        else:
            html += f"""
            <li><strong>{filing['fund_name']}</strong><br>
                Could not fetch: {filing.get('error', 'Unknown error')}
            </li>
"""
    
    html += f"""
        </ul>
        <div class="threshold-info">
            <strong>Note:</strong> 13F filings are released quarterly with a ~45 day lag. 
            They show what funds held at quarter-end, not current positions.
        </div>
    </div>
    
    <h2>📋 What These Indicators Mean</h2>
    <div class="section stable">
        <p><strong>USD Reserve Share:</strong> Central banks worldwide hold reserves in various currencies. 
        A declining USD share indicates gradual diversification away from dollar assets. 
        This moves slowly (over years/decades), not suddenly.</p>
        
        <p><strong>Foreign Treasury Holdings:</strong> Major creditors like Japan and China hold significant 
        US government debt. Consistent selling could indicate loss of confidence, but normal 
        fluctuations are common. Watch for sustained trends, not single-month changes.</p>
        
        <p><strong>Your Decision Framework:</strong> Based on our earlier discussion, if you see concerning 
        signals over multiple consecutive reports (2-3+ reports showing warning/critical), 
        consider gradually shifting your 65/35 domestic/international allocation toward 50/50 or 
        even more international exposure.</p>
    </div>
    
    <div class="footer">
        <p>Generated automatically by Bretton Woods Decay v1.0<br>
        This is informational only, not financial advice. These structural indicators move slowly; 
        check-ins every 6 months are appropriate.<br>
        Next scheduled report: {"July" if datetime.now().month <= 6 else "January"} {datetime.now().year + (1 if datetime.now().month > 6 else 0)}</p>
    </div>
</body>
</html>
"""
    
    return html


def send_email_icloud(subject, body_html):
    """Send email via iCloud SMTP."""
    if not ICLOUD_EMAIL or not ICLOUD_PASSWORD:
        print("❌ Error: Email credentials not configured")
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
        print(f"✅ Email sent successfully to {recipient}")
        return True
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False


# =============================================================================
# MAIN EXECUTION
# =============================================================================

def main():
    print("=" * 60)
    print("Bretton Woods Decay - Semi-Annual Macro Indicator Report")
    print("=" * 60)
    print(f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Fetch all data
    print("📊 Fetching IMF COFER data...")
    cofer_result = fetch_imf_cofer_data()
    print(f"   Result: {'Success' if cofer_result.get('success') else 'Failed - ' + cofer_result.get('error', 'Unknown')}")
    
    print("📊 Fetching Treasury TIC data...")
    tic_result = fetch_treasury_tic_data()
    print(f"   Result: {'Success' if tic_result.get('success') else 'Failed - ' + tic_result.get('error', 'Unknown')}")
    
    print("📊 Fetching SEC 13F filing info...")
    fund_filings = []
    for fund_name, cik in FUNDS.items():
        result = fetch_sec_13f_info(fund_name, cik)
        fund_filings.append(result)
        print(f"   {fund_name}: {'Success' if result.get('success') else 'Failed'}")
    
    # Analyze data
    print("\n🔍 Analyzing data...")
    cofer_analysis = analyze_cofer_data(cofer_result)
    treasury_analysis = analyze_treasury_data(tic_result)
    
    print(f"   COFER Status: {cofer_analysis['status']}")
    print(f"   Treasury Status: {treasury_analysis['status']}")
    
    # Generate report
    print("\n📝 Generating report...")
    html_report = generate_html_report(cofer_analysis, treasury_analysis, fund_filings)
    
    # Determine subject line based on status
    statuses = [cofer_analysis["status"], treasury_analysis["status"]]
    if "critical" in statuses:
        subject = f"🔴 Bretton Woods Decay: CRITICAL Alert - {datetime.now().strftime('%B %Y')}"
    elif "warning" in statuses:
        subject = f"🟡 Bretton Woods Decay: Warning Indicators - {datetime.now().strftime('%B %Y')}"
    else:
        subject = f"🟢 Bretton Woods Decay: All Stable - {datetime.now().strftime('%B %Y')}"
    
    # Save report locally (for debugging/GitHub artifacts)
    with open("empire_report.html", "w") as f:
        f.write(html_report)
    print("   Saved to empire_report.html")
    
    # Send email
    print("\n📧 Sending email...")
    if send_email_icloud(subject, html_report):
        print("\n✅ Report complete and sent!")
    else:
        print("\n⚠️ Report generated but email failed to send")
        print("   Check the empire_report.html file for the report content")
    
    return 0


if __name__ == "__main__":
    exit(main())
