from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import (
    DOMAIN,
    CONF_NAME,
    CONF_INSTRUMENT_TYPE,
    INSTRUMENT_TYPE_AUTO,
    INSTRUMENT_TYPE_ETF,
    INSTRUMENT_TYPE_STOCK,
)
from .coordinator import INGStocksCoordinator

_LOGGER = logging.getLogger(__name__)


def _safe_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _instrument_icon_auto(data: dict, name: str | None) -> str:
    """Auto-Erkennung: erst Typ-Felder aus Coordinator nutzen, sonst Heuristik über Name."""
    for k in ("instrument_type", "instrument_category", "instrument_group", "security_type", "asset_class"):
        v = data.get(k)
        if isinstance(v, str) and v.strip():
            s = v.lower()
            if "etf" in s or "ucits" in s or "fund" in s or "fonds" in s:
                return "mdi:chart-box-outline"  # ETF/Basket
            if "stock" in s or "equity" in s or "aktie" in s or "share" in s:
                return "mdi:chart-line"  # Aktie

    if name:
        n = name.lower()
        if "etf" in n or "ucits" in n or "fund" in n or "fonds" in n:
            return "mdi:chart-box-outline"
        return "mdi:chart-line"

    return "mdi:finance"


def _instrument_icon_for_type(instrument_type: str, data: dict, name: str | None) -> str:
    """Setzt ETF/Aktie Icon je nach manueller Auswahl, sonst Auto."""
    if instrument_type == INSTRUMENT_TYPE_ETF:
        return "mdi:chart-box-outline"
    if instrument_type == INSTRUMENT_TYPE_STOCK:
        return "mdi:chart-line"
    return _instrument_icon_auto(data, name)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: INGStocksCoordinator = hass.data[DOMAIN][entry.entry_id]

    # Anzeige-Name
    custom_name = entry.options.get(CONF_NAME, entry.data.get(CONF_NAME))
    if custom_name:
        coordinator.display_name = custom_name
    else:
        coordinator.display_name = (coordinator.data or {}).get("name") or entry.title

    # Instrument-Typ (Optionen überschreiben data)
    instrument_type = entry.options.get(
        CONF_INSTRUMENT_TYPE,
        entry.data.get(CONF_INSTRUMENT_TYPE, INSTRUMENT_TYPE_AUTO),
    )

    sensors: list[SensorEntity] = [
        INGStockValueSensor(
            coordinator, entry, instrument_type, "price", "Preis", SensorDeviceClass.MONETARY, "€", 3
        ),
        INGStockValueSensor(
            coordinator, entry, instrument_type, "change_percent", "Änderung %", None, "%", 2
        ),
        INGStockValueSensor(
            coordinator, entry, instrument_type, "change_absolute", "Änderung", SensorDeviceClass.MONETARY, "€", 3
        ),
        INGStockLastUpdateSensor(coordinator, entry),
    ]

    if (coordinator.data or {}).get("keyfigures_available"):
        sensors.extend(
            [
                INGStockValueSensor(
                    coordinator, entry, instrument_type, "dividend_yield", "Dividendenrendite", None, "%", 4
                ),
                INGStockValueSensor(
                    coordinator, entry, instrument_type, "price_earnings_ratio", "KGV", None, None, 2
                ),
                INGStockValueSensor(
                    coordinator, entry, instrument_type, "market_capitalization", "Marktkapitalisierung", None, None, 0
                ),
                INGStockValueSensor(
                    coordinator, entry, instrument_type, "52w_low", "52W Tief", SensorDeviceClass.MONETARY, "€", 3
                ),
                INGStockValueSensor(
                    coordinator, entry, instrument_type, "52w_high", "52W Hoch", SensorDeviceClass.MONETARY, "€", 3
                ),
            ]
        )

    async_add_entities(sensors, True)


class INGStockBaseSensor(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: INGStocksCoordinator, entry: ConfigEntry):
        self.coordinator = coordinator
        self.entry = entry

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success and (self.coordinator.data or {}).get("price") is not None

    @property
    def device_info(self):
        d = self.coordinator.data or {}
        return {
            "identifiers": {(DOMAIN, self.coordinator.isin)},
            "name": self.coordinator.display_name or d.get("name") or self.entry.title,
            "manufacturer": "ING (component-api.wertpapiere.ing.de)",
            "model": self.coordinator.isin,
        }

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(self.coordinator.async_add_listener(self.async_write_ha_state))

    async def async_update(self) -> None:
        await self.coordinator.async_request_refresh()


class INGStockValueSensor(INGStockBaseSensor):
    def __init__(
        self,
        coordinator: INGStocksCoordinator,
        entry: ConfigEntry,
        instrument_type: str,
        key: str,
        entity_name: str,
        device_class: SensorDeviceClass | None,
        unit: str | None,
        precision: int | None,
    ):
        super().__init__(coordinator, entry)
        self.instrument_type = instrument_type
        self.key = key
        self._attr_name = entity_name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._precision = precision

        # ✅ monetary darf nicht measurement sein (HA-Regel)
        if device_class == SensorDeviceClass.MONETARY:
            self._attr_state_class = None
        else:
            self._attr_state_class = SensorStateClass.MEASUREMENT

        self._attr_unique_id = f"{DOMAIN}_{coordinator.isin}_{key}"

    @property
    def icon(self) -> str | None:
        d = self.coordinator.data or {}
        name = d.get("name")

        # Preis
        if self.key == "price":
            return "mdi:chart-line"

        # Änderung dynamisch
        if self.key in ("change_percent", "change_absolute"):
            v = _safe_float(d.get(self.key))
            if v is None:
                return "mdi:trending-neutral"
            if v > 0:
                return "mdi:trending-up"
            if v < 0:
                return "mdi:trending-down"
            return "mdi:trending-neutral"

        # Kennzahlen
        if self.key == "dividend_yield":
            return "mdi:cash-percent"
        if self.key == "price_earnings_ratio":
            return "mdi:calculator-variant"
        if self.key == "market_capitalization":
            return "mdi:bank"
        if self.key in ("52w_low", "52w_high"):
            return "mdi:arrow-expand-vertical"
        if self.key == "dividend_per_share":
            return "mdi:cash"

        # Fallback: ETF/Aktie je nach Auswahl/Auto-Erkennung
        return _instrument_icon_for_type(self.instrument_type, d, name)

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data or {}
        return {
            "isin": d.get("isin"),
            "exchange": d.get("exchange"),
            "currency": d.get("currency"),
            "instrument_type_selected": self.instrument_type,
            # optional: API/Auto-Felder zur Diagnose
            "instrument_type": d.get("instrument_type"),
            "instrument_category": d.get("instrument_category"),
            "instrument_group": d.get("instrument_group"),
            "security_type": d.get("security_type"),
            "asset_class": d.get("asset_class"),
        }

    @property
    def native_value(self):
        value = (self.coordinator.data or {}).get(self.key)
        if value is None:
            return None
        if isinstance(value, (int, float)) and self._precision is not None:
            return round(float(value), self._precision)
        return value


class INGStockLastUpdateSensor(INGStockBaseSensor):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_name = "Letztes Update"

    def __init__(self, coordinator: INGStocksCoordinator, entry: ConfigEntry):
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{DOMAIN}_{coordinator.isin}_last_update"

    @property
    def icon(self) -> str | None:
        return "mdi:clock-outline"

    @property
    def native_value(self):
        raw = (self.coordinator.data or {}).get("last_update")
        if not raw:
            return None
        dt = dt_util.parse_datetime(raw)
        return dt_util.as_utc(dt) if dt else None