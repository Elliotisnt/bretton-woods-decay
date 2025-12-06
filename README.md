# Bretton Woods Decay Monitor

A quarterly macro indicator monitoring system that tracks structural changes in US dollar hegemony.

## What It Is

This tool tracks seven slow-moving structural indicators that might signal a shift in dollar dominance:

| Indicator | What It Measures | Warning | Critical |
|-----------|------------------|---------|----------|
| **USD Share of Global Reserves** | Percentage of global FX reserves held in USD | <55% | <50% |
| **China Treasury Holdings** | China's holdings of US Treasury securities | <$700B | <$500B |
| **Japan Treasury Holdings** | Japan's holdings of US Treasury securities | <$1000B | <$850B |
| **Dollar Index (DXY)** | USD vs basket of 6 major currencies | <90 | <80 |
| **US Debt-to-GDP** | Federal debt as percentage of GDP | >130% | >150% |
| **Interest/Revenue Ratio** | Federal interest payments as % of revenue | >20% | >25% |
| **Intl vs US Stocks (3yr)** | International equity outperformance | +15% | +30% |

Each indicator includes historical context for scale. For example, the DXY hit an all-time high of 164.7 in February 1985 and an all-time low of 70.7 in March 2008. Japan maintains ~260% debt-to-GDP but only pays ~8% of revenue to interest due to domestic ownership and near-zero rates—demonstrating that debt levels alone don't tell the whole story.

## Why I Made It

Long-term retirement allocation decisions (like whether to hold 65/35 or 50/50 domestic/international) shouldn't be made based on short-term market noise. But they also shouldn't ignore structural shifts in the global monetary system.

This tool sends me a quarterly email with these indicators so I can:
- Notice sustained trends over multiple reports
- Have data-driven context for allocation decisions
- Avoid the temptation to check obsessively

These are *decades-long* structural trends, not trading signals.

## How I Use It

- **All stable**: No action. Check next quarter.
- **1-2 warnings**: Note it, but don't react to a single report.
- **Warnings for 2-3 consecutive reports**: Consider shifting from 65/35 → 50/50.
- **Multiple critical signals**: More aggressive rebalancing may be warranted.

The goal is to catch sustained trends, not react to noise.

## Data Sources

- **IMF COFER**: Currency Composition of Official Foreign Exchange Reserves (via DBnomics)
- **Treasury TIC**: Treasury International Capital reporting
- **FRED**: Federal Reserve Economic Data (OMB fiscal year series for interest/revenue)
- **Yahoo Finance**: DXY and ETF data (VXUS vs VTI)

## Disclaimer

This is informational only, not financial advice.
