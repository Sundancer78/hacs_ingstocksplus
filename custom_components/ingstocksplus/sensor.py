from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN, CONF_NAME
from .coordinator import INGStocksCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    coordinator: INGStocksCoordinator = hass.data[DOMAIN][entry.entry_id]

    custom_name = entry.options.get(CONF_NAME, entry.data.get(CONF_NAME))
    if custom_name:
        coordinator.display_name = custom_name
    else:
        coordinator.display_name = coordinator.data.get("name") or entry.title

    base_keys = ["price", "change_percent", "change_absolute", "last_update"]
    sensors: list[SensorEntity] = [
        INGStockValueSensor(coordinator, entry, "price", "Preis", SensorDeviceClass.MONETARY, "€", 3),
        INGStockValueSensor(coordinator, entry, "change_percent", "Änderung %", None, "%", 2),
        INGStockValueSensor(coordinator, entry, "change_absolute", "Änderung", SensorDeviceClass.MONETARY, "€", 3),
        INGStockLastUpdateSensor(coordinator, entry),
    ]

    keyfig_keys = ["dividend_yield", "price_earnings_ratio", "market_capitalization", "52w_low", "52w_high"]
    if coordinator.data.get("keyfigures_available"):
        sensors.extend(
            [
                INGStockValueSensor(coordinator, entry, "dividend_yield", "Dividendenrendite", None, "%", 4),
                INGStockValueSensor(coordinator, entry, "price_earnings_ratio", "KGV", None, None, 2),
                INGStockValueSensor(coordinator, entry, "market_capitalization", "Marktkapitalisierung", None, None, 0),
                INGStockValueSensor(coordinator, entry, "52w_low", "52W Tief", SensorDeviceClass.MONETARY, "€", 3),
                INGStockValueSensor(coordinator, entry, "52w_high", "52W Hoch", SensorDeviceClass.MONETARY, "€", 3),
            ]
        )

    created = base_keys + (keyfig_keys if coordinator.data.get("keyfigures_available") else [])
    _LOGGER.info(
        "ING Stocks Plus entities: ISIN=%s, keyfigures=%s, sensors=%s",
        coordinator.isin,
        bool(coordinator.data.get("keyfigures_available")),
        ",".join(created),
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
        key: str,
        entity_name: str,
        device_class: SensorDeviceClass | None,
        unit: str | None,
        precision: int | None,
    ):
        super().__init__(coordinator, entry)
        self.key = key
        self._attr_name = entity_name
        self._attr_device_class = device_class
        self._attr_native_unit_of_measurement = unit
        self._precision = precision

        # ✅ monetary darf nicht measurement sein (neue HA-Regel)
        if device_class == SensorDeviceClass.MONETARY:
            self._attr_state_class = None
        else:
            self._attr_state_class = SensorStateClass.MEASUREMENT

        self._attr_unique_id = f"{DOMAIN}_{coordinator.isin}_{key}"

    @property
    def extra_state_attributes(self):
        d = self.coordinator.data or {}
        return {"isin": d.get("isin"), "exchange": d.get("exchange"), "currency": d.get("currency")}

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
    def native_value(self):
        raw = (self.coordinator.data or {}).get("last_update")
        if not raw:
            return None
        dt = dt_util.parse_datetime(raw)
        return dt_util.as_utc(dt) if dt else None