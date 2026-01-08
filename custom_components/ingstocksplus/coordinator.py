from __future__ import annotations

import logging
import socket
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)


class INGStocksCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, isin: str, update_interval):
        self.isin = isin
        self.display_name: str | None = None
        super().__init__(
            hass,
            _LOGGER,
            name=f"ING Stocks Plus {isin}",
            update_interval=update_interval,
        )

    async def _async_update_data(self) -> dict[str, Any]:
        header_url = (
            f"https://component-api.wertpapiere.ing.de/api/v1/components/instrumentheader/{self.isin}"
        )
        keyfigures_url = (
            f"https://component-api.wertpapiere.ing.de/api/v1/share-ng/keyfigures/{self.isin}"
        )

        # IPv4 erzwingen (hilft bei DNS/Timeouts in manchen Setups)
        session = async_get_clientsession(self.hass, family=socket.AF_INET)

        try:
            # --- 1) instrumentheader
            async with session.get(header_url, timeout=20) as resp:
                if resp.status != 200:
                    raise UpdateFailed(f"instrumentheader HTTP {resp.status}")
                header = await resp.json()

            # --- 2) keyfigures (optional)
            keyfigures: dict[str, Any] = {}
            keyfigures_available = False

            async with session.get(keyfigures_url, timeout=20) as resp:
                if resp.status == 404:
                    _LOGGER.debug("No keyfigures for %s (HTTP 404).", self.isin)
                elif resp.status != 200:
                    raise UpdateFailed(f"keyfigures HTTP {resp.status}")
                else:
                    keyfigures = await resp.json()
                    keyfigures_available = isinstance(keyfigures, dict)

        except UpdateFailed:
            raise
        except Exception as err:
            raise UpdateFailed(f"Fetch error {self.isin}: {err}") from err

        data: dict[str, Any] = {
            # Basis
            "name": header.get("name"),
            "isin": header.get("isin") or self.isin,
            "currency": header.get("currencySign") or "€",
            "exchange": header.get("exchangeName"),

            # Kursdaten
            "price": header.get("price"),
            "change_percent": header.get("changePercent"),
            "change_absolute": header.get("changeAbsolute"),
            "last_update": header.get("priceChangeDate"),

            # 🧠 Typ-/Kategorie-Felder (falls ING sie liefert)
            "instrument_type": header.get("instrumentType") or header.get("type"),
            "instrument_category": header.get("instrumentCategory") or header.get("category"),
            "instrument_group": header.get("instrumentGroup") or header.get("group"),
            "security_type": header.get("securityType") or header.get("securityTypeName"),
            "asset_class": header.get("assetClass") or header.get("assetClassName"),

            # Keyfigures
            "keyfigures_available": keyfigures_available,
            "dividend_yield": keyfigures.get("dividendYield"),
            "dividend_per_share": keyfigures.get("dividendPerShare"),
            "price_earnings_ratio": keyfigures.get("priceEarningsRatio"),
            "market_capitalization": keyfigures.get("marketCapitalization"),
            "market_cap_currency": keyfigures.get("marketCapitalizationCurrencyIsoCode"),
            "52w_low": keyfigures.get("fiftyTwoWeekLow"),
            "52w_high": keyfigures.get("fiftyTwoWeekHigh"),
        }

        if data["price"] is None:
            raise UpdateFailed(f"No price in instrumentheader for {self.isin}")

        return data