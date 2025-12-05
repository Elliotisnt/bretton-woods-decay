# Bretton Woods Decay

Semi-annual macro indicator emails to keep tabs on the slow decline of the US financial system and the dollar. Focused on empire decline rather than market crashes. Indicators are lagging, but give more signal than my noisy twitter feed. Will use for consideration of shifting retirement composition from FXAIX to FTIHX.

## Indicators

### 1. USD Share of Global Reserves (IMF COFER)
What percentage of global central bank reserves are held in US dollars.
- **Warning:** Below 55%
- **Critical:** Below 50%
- **Context:** Peaked at 71% in 2000, currently around 58%

### 2. China Treasury Holdings
How much US government debt China holds.
- **Warning:** Below $700B
- **Critical:** Below $500B
- **Context:** Peaked at $1.3T in 2013, now around $775B

### 3. Japan Treasury Holdings
How much US government debt Japan holds.
- **Warning:** Below $1T
- **Critical:** Below $850B
- **Context:** Largest holder, typically $1.0-1.2T

### 4. Dollar Index (DXY)
USD strength vs a basket of major currencies.
- **Warning:** Below 95
- **Critical:** Below 85
- **Context:** 100 is roughly neutral. Sustained weakness signals confidence loss.

### 5. US Debt-to-GDP Ratio
Federal debt as a percentage of economic output.
- **Warning:** Above 130%
- **Critical:** Above 150%
- **Context:** Was 60% in 2000, 100% in 2012, now around 120%

### 6. Interest Payments as % of Revenue
How much of federal revenue goes to servicing debt.
- **Warning:** Above 25%
- **Critical:** Above 33%
- **Context:** Above 33% means 1/3 of all revenue goes to interest

### 7. International vs US Stocks (3-Year)
Cumulative performance difference between international and US stocks.
- **Warning:** International ahead by 15%+
- **Critical:** International ahead by 30%+
- **Context:** Sustained international outperformance suggests rotation away from US

## Setup

### 1. Create a GitHub Repository

Create a new repo called `bretton-woods-decay` (or whatever you want).

### 2. Upload the Files

Upload these files to your repo:
```
bretton-woods-decay/
├── .github/
│   └── workflows/
│       └── bretton_woods_decay.yml
├── bretton_woods_decay.py
└── README.md
```

### 3. Generate an iCloud App-Specific Password

1. Go to [appleid.apple.com](https://appleid.apple.com)
2. Sign in -> Sign-In and Security -> App-Specific Passwords
3. Generate a password, name it "BrettonWoodsDecay"
4. Copy the code (format: `xxxx-xxxx-xxxx-xxxx`)

### 4. Configure GitHub Secrets

In your repo: Settings -> Secrets and variables -> Actions -> New repository secret

| Secret Name | Value |
|-------------|-------|
| `ICLOUD_EMAIL` | Your iCloud email address (used to send) |
| `ICLOUD_PASSWORD` | The app-specific password from step 3 |
| `TO_EMAIL` | Email address to receive reports |

### 5. Test It

Actions -> Bretton Woods Decay Report -> Run workflow

This will send you an email immediately.

## Schedule

Runs automatically on:
- January 15th at 9 AM Eastern
- July 15th at 9 AM Eastern

## Decision Framework

- **All stable:** No action needed. Check back in 6 months.
- **1-2 warnings:** Note it, don't react to a single report.
- **Warnings for 2-3 consecutive reports:** Consider shifting from 65/35 to 50/50 domestic/international.
- **Multiple critical signals:** More aggressive rebalancing toward international may be warranted.

These are slow-moving structural indicators. Empire decline happens over decades, not months.

## Data Sources

- IMF COFER: https://data.imf.org
- Treasury TIC: https://home.treasury.gov/data/treasury-international-capital-tic-system
- FRED: https://fred.stlouisfed.org
- Yahoo Finance: Market data for DXY and ETFs

## License

MIT
