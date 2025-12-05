# Bretton Woods Decay 🏛️

Semi-annual macro indicator emails to keep tabs on the slow decline of the US financial system and the dollar. Focused on empire decline rather than market crashes. Indicators are lagging, but give more signal than my noisy twitter feed. Will use for consideration of shifting retirement composition from FXAIX to FTIHX.

## What It Monitors

### 1. USD Share of Global Reserves (IMF COFER)
- **Source:** International Monetary Fund COFER database
- **What it shows:** What percentage of global central bank reserves are held in US dollars
- **Why it matters:** A declining share indicates gradual de-dollarization. This moves slowly over years/decades.
- **Thresholds:** 
  - Warning: Below 55%
  - Critical: Below 50%
- **Current context:** USD share peaked at ~71% in 2000, has declined to ~58% as of 2024

### 2. Foreign Holdings of US Treasuries (Treasury TIC Data)
- **Source:** US Treasury International Capital System
- **What it shows:** How much US government debt major countries (China, Japan, etc.) hold
- **Why it matters:** Consistent selling by major holders could indicate loss of confidence
- **Key thresholds:**
  - China: Warning <$750B, Critical <$600B
  - Japan: Warning <$1000B, Critical <$800B
  - Top 10 holders 6-month change: Warning <-$100B, Critical <-$200B

### 3. Macro Fund Positioning (SEC 13F Filings)
- **Source:** SEC EDGAR database
- **What it shows:** Latest quarterly filings from Bridgewater and Berkshire Hathaway
- **Why it matters:** These large macro-focused funds sometimes signal broader market concerns
- **Note:** 13F filings have a ~45 day lag from quarter-end

## Setup

### 1. Create a GitHub Repository

Create a new repository and add these files:
```
your-repo/
├── empire_watch.py
├── .github/
│   └── workflows/
│       └── empire_watch.yml
└── README.md
```

### 2. Generate an iCloud App-Specific Password

1. Go to [appleid.apple.com](https://appleid.apple.com)
2. Sign in and go to **Sign-In and Security → App-Specific Passwords**
3. Click **Generate an App-Specific Password**
4. Name it "EmpireWatch" and copy the generated code (format: `xxxx-xxxx-xxxx-xxxx`)

### 3. Configure GitHub Secrets

In your repository, go to **Settings → Secrets and variables → Actions → New repository secret**

Add these three secrets:

| Secret Name | Value |
|-------------|-------|
| `ICLOUD_EMAIL` | Your iCloud email address (e.g., `you@icloud.com`) |
| `ICLOUD_PASSWORD` | The app-specific password from step 2 |
| `TO_EMAIL` | Email address to receive reports (can be same as ICLOUD_EMAIL, or different) |

### 4. Test It

1. Go to **Actions** tab in your repository
2. Click **Empire Watch Semi-Annual Report**
3. Click **Run workflow** → **Run workflow**
4. Wait ~1 minute for completion
5. Check your email!

## Schedule

The report runs automatically on:
- **January 15th** at 2PM UTC (9AM Eastern)
- **July 15th** at 2PM UTC (9AM Eastern)

You can also run it manually anytime via the Actions tab.

## Understanding the Report

### Status Indicators
- 🟢 **Stable:** All indicators within normal ranges
- 🟡 **Warning:** One or more indicators below warning thresholds - worth monitoring
- 🔴 **Critical:** One or more indicators at concerning levels - consider reviewing your allocation

### Decision Framework

These indicators move slowly. The suggested approach:

1. **Single warning report:** Note it, but don't act immediately
2. **2-3 consecutive warning/critical reports:** Consider gradually shifting your domestic/international allocation (e.g., from 65/35 to 50/50)
3. **Sustained critical signals:** More aggressive rebalancing may be warranted

Remember: These are structural indicators that shift over years, not days. Six-month check-ins are appropriate.

## Customization

### Adjust Thresholds

Edit the `THRESHOLDS` dictionary in `empire_watch.py` to change warning/critical levels.

### Add More Funds

Add entries to the `FUNDS` dictionary with the fund name and SEC CIK number:
```python
FUNDS = {
    "Bridgewater Associates": "1350694",
    "Berkshire Hathaway": "1067983",
    "Your New Fund": "CIK_NUMBER",
}
```

### Change Schedule

Edit the cron expressions in `.github/workflows/empire_watch.yml`:
```yaml
schedule:
  - cron: '0 14 15 1 *'   # January 15th at 2PM UTC
  - cron: '0 14 15 7 *'   # July 15th at 2PM UTC
```

## Data Sources

- **IMF COFER:** https://data.imf.org/en/datasets/IMF.STA:COFER
- **Treasury TIC:** https://home.treasury.gov/data/treasury-international-capital-tic-system
- **SEC EDGAR:** https://www.sec.gov/edgar/searchedgar/companysearch

## Limitations

- All data has reporting lags (1-3 months typically)
- Treasury data attributes holdings by custodian location, not ultimate owner
- 13F filings show point-in-time snapshots, not real-time positions
- IMF COFER is quarterly data

## License

MIT - Do whatever you want with this.

---

*This is informational only, not financial advice. Past performance doesn't guarantee future results. Do your own research.*
