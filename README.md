# Bretton Woods Decay Monitor

Semi-annual macro indicator monitoring system to track structural changes in US dollar hegemony.

## Purpose

This tool tracks slow-moving structural indicators that might signal a shift in dollar dominance and help inform long-term retirement allocation decisions (e.g., shifting from 65/35 to 50/50 domestic/international).

**Important:** This monitors *decades-long structural trends*, not short-term market movements.

## Indicators Tracked

| Indicator | Source | Warning | Critical |
|-----------|--------|---------|----------|
| USD Share of Global Reserves | IMF COFER (via DBnomics) | <55% | <50% |
| China Treasury Holdings | Treasury TIC | <$700B | <$500B |
| Japan Treasury Holdings | Treasury TIC | <$1000B | <$850B |
| Dollar Index (DXY) | Yahoo Finance | <95 | <85 |
| US Debt-to-GDP | FRED | >130% | >150% |
| Interest/Revenue Ratio | FRED | >25% | >33% |
| International vs US Stocks (3yr) | Yahoo Finance | +15% | +30% |

## Setup

### 1. Create GitHub Repository

Create a new repository (can be public or private).

### 2. Add Files

Upload:
- `bretton_woods_decay.py` 
- `.github/workflows/bretton_woods_decay.yml`

### 3. Configure Secrets

Go to **Settings → Secrets and variables → Actions** and add:

| Secret | Description |
|--------|-------------|
| `ICLOUD_EMAIL` | Your iCloud email (sender) |
| `ICLOUD_PASSWORD` | App-specific password (see below) |
| `TO_EMAIL` | Recipient email (optional, defaults to sender) |

#### Getting an App-Specific Password

1. Go to [appleid.apple.com](https://appleid.apple.com)
2. Sign in → Security → App-Specific Passwords
3. Click "Generate" and name it (e.g., "Bretton Woods")
4. Copy the generated password

### 4. Test

Go to **Actions → Bretton Woods Decay Report → Run workflow** to test manually.

## Schedule

Runs automatically on:
- January 15 at 9 AM Eastern
- July 15 at 9 AM Eastern

## Data Sources

- **IMF COFER**: Currency Composition of Official Foreign Exchange Reserves (via DBnomics mirror)
- **Treasury TIC**: Treasury International Capital reporting (ticdata.treasury.gov)
- **FRED**: Federal Reserve Economic Data
- **Yahoo Finance**: Market data for DXY and ETFs

## ETF Proxies

- **VTI** (Vanguard Total US Stock Market) ≈ FXAIX (Fidelity 500 Index)
- **VXUS** (Vanguard Total International Stock, **excludes US**) ≈ FTIHX (Fidelity Total International)

These are good proxies for comparing US vs international performance. VXUS explicitly excludes US stocks, giving a clean comparison.

## Decision Framework

- **All stable**: No action. Check in 6 months.
- **1-2 warnings**: Note but don't react to single report.
- **Warnings 2-3 consecutive reports**: Consider shifting 65/35 → 50/50.
- **Multiple critical signals**: More aggressive rebalancing may be warranted.

## Disclaimer

This is informational only and not financial advice. These are structural macro indicators, not trading signals.
