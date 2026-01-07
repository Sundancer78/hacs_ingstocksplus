# hacs_ingstocksplus

ING Stocks Plus — Home Assistant Integration



# ING Stocks Plus

**ING Stocks Plus** is a Home Assistant integration to fetch stock/ETF data

from ING’s public API. It supports dynamic keyfigures, configurable scan interval,

and plays nicely with HACS and ApexCharts.


---


##Features

- Fetch price and summary data for instruments by ISIN

- Optional keyfigures if available (dividend yield, 52w high/low, etc.)

- Per-entry scan interval configuration (via Options)

- Designed for efficient polling with DataUpdateCoordinator

- Works with ApexCharts for stock charts


---


##Installation

1. Add this repository to HACS:

* HACS → Integrations → … (Add custom repository)

* Repo type: **Integration**, URL:  

	https://github.com/Sundancer78/hacs_ingstocksplus

2. Install **ING Stocks Plus**

3. Restart Home Assistant


---


##Configuration

1. Go to **Settings → Devices & Services**

2. Click **Add Integration**

3. Search for **ING Stocks Plus**

4. Enter an **ISIN**

5. Set **Scan Interval** and optional **Name**


> Example ISIN: `IE0008GRJRO8`


---


##Sensors Created

The following sensors are created per ISIN (where available):


| Entity Key              | Meaning |
|-------------------------|---------|
| `price`                 | Last price |
| `change_percent`        | Percentage change |
| `change_absolute`       | Absolute change |
| `last_update`           | Last update timestamp |
| `dividend_yield`        | Dividend yield (if available) |
| `price_earnings_ratio`  | P/E ratio (if available) |
| `market_capitalization` | Market cap (if available) |
| `52w_low` / `52w_high`  | 52-week low/high (if available) |



---


##Notes

- Some instruments may not have keyfigures → those sensors won’t be created
- Choose scan intervals wisely (e.g., 5–30 minutes) to avoid API throttling


##Example Lovelace Card

With **ApexCharts Card**:


```yaml
type: custom:apexcharts-card
header:
  show: true
  title: Vanguard FTSE All-World UCITS ETF USD Acc
  show_states: true
  colorize_states: true
graph_span: 1d
series:
  - entity: sensor.vanguard_ftse_all_world_ucits_etf_usd_acc_preis_2
    name: Kurs
    stroke_width: 2
    extend_to: false