"""Platform for sensor integration."""
from __future__ import annotations
from datetime import datetime, timezone
import enum
import logging
from typing import cast, Any
from homeassistant.util import slugify
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.core import callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.components.sensor import SensorEntity, SensorStateClass, SensorEntityDescription, SensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from .coordinator import BrewfatherCoordinator, BrewfatherCoordinatorData
from .const import (
    DOMAIN,
    COORDINATOR,
    CONF_ALL_BATCH_INFO_SENSOR
)

_LOGGER = logging.getLogger(__name__)
SENSOR_PREFIX = "Brewfather"

class SensorUpdateData:
    state: Any
    attr_available: bool
    extra_state_attributes: dict[str, Any]
    
    def __init__(self):
        self.state = None
        self.attr_available = False
        self.extra_state_attributes = {}

class BrewfatherStatusSensor(CoordinatorEntity, SensorEntity):
    """Brewfather integration status sensor."""
    
    def __init__(
        self, 
        coordinator: BrewfatherCoordinator,
        entry: ConfigEntry,
        entity_description: SensorEntityDescription,
    ):
        """Initialize the sensor."""
        super().__init__(coordinator, context=None)
        self.entity_description = entity_description
        self._entry = entry
        self._attr_unique_id = f"{SENSOR_PREFIX}_{entry.entry_id}_{entity_description.key}"
        self._attr_name = f"{SENSOR_PREFIX} {entity_description.name}"

    @property
    def state(self) -> str:
        """Return the state of the sensor."""
        if not self.coordinator.last_update_success:
            return "disconnected"
        elif self._entry.data.get("custom_stream_enabled", False):
            return "monitoring"
        else:
            return "connected"
    
    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return additional state attributes."""
        attrs = {
            "api_connection": "✅ Connected" if self.coordinator.last_update_success else "❌ Disconnected",
            "last_update": self.coordinator.last_update_success_time.isoformat() if self.coordinator.last_update_success_time else None,
        }
        
        if self._entry.data.get("custom_stream_enabled", False):
            attrs["custom_stream"] = "✅ Enabled"
            entity_name = self._entry.data.get("custom_stream_temperature_entity_name")
            if entity_name:
                entity = self.hass.states.get(entity_name)
                if entity:
                    unit = entity.attributes.get("unit_of_measurement", "°C")
                    attrs["temperature_entity"] = f"🌡️ {entity_name} ({unit})"
                    attrs["last_temperature"] = f"{entity.state}{unit}"
            
            # Add gravity info if configured
            gravity_entity_name = self._entry.data.get("custom_stream_gravity_entity_name")
            if gravity_entity_name:
                gravity_entity = self.hass.states.get(gravity_entity_name)
                if gravity_entity:
                    attrs["gravity_entity"] = f"🍺 {gravity_entity_name}"
                    attrs["last_gravity"] = f"{gravity_entity.state}"
        else:
            attrs["custom_stream"] = "⚪ Disabled"
            
        return attrs

    @property
    def icon(self) -> str:
        """Return the icon for the sensor."""
        if not self.coordinator.last_update_success:
            return "mdi:beer-off"
        elif self._entry.data.get("custom_stream_enabled", False):
            return "mdi:beer-outline"
        else:
            return "mdi:beer"

async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    """Set up the sensor platforms."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]
    
    # 1. Створюємо ГЛОБАЛЬНІ сенсори (статус інтеграції та загальне інфо).
    # Вони створюються лише один раз під час ініціалізації.
    static_sensors = []
    status_description = SensorEntityDescription(
        key="status", name="Integration Status", icon="mdi:beer"
    )
    static_sensors.append(BrewfatherStatusSensor(coordinator, entry, status_description))

    if entry.data.get(CONF_ALL_BATCH_INFO_SENSOR, False):
        static_sensors.append(
            BrewfatherSensor(
                coordinator=coordinator,
                batch_id="all_batches_global",
                sensorKind=SensorKinds.all_batch_info,
                description=SensorEntityDescription(key="all_batches_data", name="All batches data", icon="mdi:database"),
            )
        ) 
    
    async_add_entities(static_sensors, update_before_add=False)

    # 2. Описуємо всі типи сенсорів, які потрібно створювати для КОЖНОГО батча
    sensor_definitions = [
        (SensorKinds.fermenting_name, SensorEntityDescription(key="recipe_name", name="Recipe name", icon="mdi:glass-mug")),
        (SensorKinds.brewer, SensorEntityDescription(key="brewer", name="Brewer", icon="mdi:account")),
        (SensorKinds.fermenting_current_temperature, SensorEntityDescription(key="target_temperature", name="Target temperature", icon="mdi:thermometer", native_unit_of_measurement=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT)),
        (SensorKinds.fermenting_next_temperature, SensorEntityDescription(key="upcoming_target_temperature", name="Upcoming target temperature", icon="mdi:thermometer-chevron-up", native_unit_of_measurement=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE)),
        (SensorKinds.fermenting_next_date, SensorEntityDescription(key="upcoming_target_temperature_change", name="Upcoming target temperature change", icon="mdi:clock", device_class=SensorDeviceClass.TIMESTAMP)),
        (SensorKinds.fermenting_last_reading, SensorEntityDescription(key="last_reading", name="Last reading", icon="mdi:chart-line", state_class=SensorStateClass.MEASUREMENT)),
        (SensorKinds.fermenting_start_date, SensorEntityDescription(key="fermentation_start_date", name="Fermentation start", icon="mdi:clock", device_class=SensorDeviceClass.TIMESTAMP)),
        (SensorKinds.batch_notes, SensorEntityDescription(key="batch_notes", name="Batch notes", icon="mdi:note-text")),
        (SensorKinds.events, SensorEntityDescription(key="events", name="Events", icon="mdi:calendar-clock")),
        (SensorKinds.status, SensorEntityDescription(key="status", name="Status", icon="mdi:list-status")),
        (SensorKinds.batch_no, SensorEntityDescription(key="batch_no", name="Batch Number", icon="mdi:pound")),
        (SensorKinds.batch_name, SensorEntityDescription(key="batch_name", name="Batch Name", icon="mdi:pound")),
        (SensorKinds.recipe_name, SensorEntityDescription(key="recipe_name", name="Recipe Name", icon="mdi:glass-mug")),
        (SensorKinds.measured_abv, SensorEntityDescription(key="measured_abv", name="Measured ABV", icon="mdi:percent", native_unit_of_measurement="%")),
        (SensorKinds.measured_og, SensorEntityDescription(key="measured_og", name="Measured OG", icon="mdi:water-percent", state_class=SensorStateClass.MEASUREMENT)),
        (SensorKinds.measured_fg, SensorEntityDescription(key="measured_fg", name="Measured FG", icon="mdi:water-percent", state_class=SensorStateClass.MEASUREMENT)),
        (SensorKinds.brew_date, SensorEntityDescription(key="brew_date", name="Brew Date", icon="mdi:calendar", device_class=SensorDeviceClass.TIMESTAMP)),
    ]

    # 3. Створюємо сховище для відстеження вже відомих батчів
    if "known_batches" not in hass.data[DOMAIN][entry.entry_id]:
        hass.data[DOMAIN][entry.entry_id]["known_batches"] = set()
    
    known_batches = hass.data[DOMAIN][entry.entry_id]["known_batches"]

    @callback
    def async_discover_batches():
        """Шукає нові батчі та видаляє архівні під час кожного оновлення координатора."""
        if not coordinator.last_update_success or not coordinator.data:
            return

        # Збираємо актуальні ID батчів з API
        current_batches = set()
        if getattr(coordinator.data, "batch_id", None):
            current_batches.add(coordinator.data.batch_id)
        if hasattr(coordinator.data, "other_batches") and coordinator.data.other_batches:
            for b in coordinator.data.other_batches:
                if getattr(b, "batch_id", None):
                    current_batches.add(b.batch_id)

        # Крок А: Шукаємо та додаємо НОВІ батчі
        new_batch_ids = current_batches - known_batches
        if new_batch_ids:
            new_entities = []
            for batch_id in new_batch_ids:
                _LOGGER.info("Знайдено новий батч: %s. Створюємо сутності.", batch_id)
                for sensor_kind, description in sensor_definitions:
                    new_entities.append(
                        BrewfatherSensor(
                            coordinator=coordinator,
                            batch_id=batch_id,
                            sensorKind=sensor_kind,
                            description=description,
                        )
                    )
            
            async_add_entities(new_entities)
            known_batches.update(new_batch_ids)

        # Крок Б: Видаляємо АРХІВНІ батчі (ті, що зникли з API)
        removed_batch_ids = known_batches - current_batches
        if removed_batch_ids:
            dev_reg = dr.async_get(hass)
            for batch_id in removed_batch_ids:
                _LOGGER.info("Батч %s більше не активний. Видаляємо пристрій.", batch_id)
                # Шукаємо пристрій у реєстрі за нашим identifier
                device = dev_reg.async_get_device(identifiers={(DOMAIN, batch_id)})
                if device:
                    dev_reg.async_remove_device(device.id) # Це автоматично видалить і всі сенсори!
                
                known_batches.remove(batch_id)

    # 4. Реєструємо слухача, який буде викликати async_discover_batches при кожному оновленні
    entry.async_on_unload(
        coordinator.async_add_listener(async_discover_batches)
    )

    # 5. Робимо перший виклик вручну, щоб створити сутності при старті системи
    async_discover_batches()

class BrewfatherSensor(CoordinatorEntity[BrewfatherCoordinator], SensorEntity):
    """An entity using CoordinatorEntity."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        batch_id: str,
        sensorKind: SensorKinds,
        description: SensorEntityDescription,
    ):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        self._batch_id = batch_id
        self._entity_description = description
        self._sensor_type = sensorKind

        self._attr_has_entity_name = True
        self._attr_name = self._entity_description.name
        
        # unique_id залишаємо на базі batch_id (GUID від API), він і так унікальний
        self._attr_unique_id = f"{SENSOR_PREFIX}_{batch_id}_{self._entity_description.key}"

        self._attr_icon = self._entity_description.icon
        self._attr_state_class = self._entity_description.state_class
        self._attr_native_unit_of_measurement = self._entity_description.native_unit_of_measurement
        self._attr_device_class = self._entity_description.device_class
        
        self._update_internal_state()

        # --- МОДИФІКАЦІЯ ENTITY_ID ---
        if batch_id == "all_batches_global":
            self.entity_id = f"sensor.brewfather_all_batches_data"
        else:
            batch_data = self._get_my_batch_data()
            batch_name = getattr(batch_data, "name", "") if batch_data else ""
            batch_no = getattr(batch_data, "batch_no", "??") if batch_data else "??"
            recipe_name = getattr(batch_data, "recipe_name", "") if batch_data else ""
            print("--------------------------------------")
            print(recipe_name)
            safe_recipe_name = slugify(recipe_name)
            safe_batch_name = slugify(batch_name)            
            # Тепер ID буде: sensor.brewfather_batch_12_nelson_sauvin_status
            self.entity_id = f"sensor.bf_batch_{batch_no}_{self._entity_description.key}"

    @property
    def device_info(self) -> DeviceInfo | None:
        """Group entities into a Device representing a specific batch."""
        if self._batch_id == "all_batches_global":
            return None
            
        batch_data = self._get_my_batch_data()
        recipe_name = getattr(batch_data, "recipe_name", "") if batch_data else ""
        batch_no = getattr(batch_data, "batch_no", "??") if batch_data else "??"
        batch_name = getattr(batch_data, "name", "") if batch_data else ""
            
        return DeviceInfo(
            identifiers={(DOMAIN, self._batch_id)},
            # Тепер у списку пристроїв буде: "Batch #12: Nelson Sauvin"
            name=f"Batch #{batch_no} {batch_name}: {recipe_name}",
            manufacturer="Brewfather",
            model="Brew Batch",
        )
    def _get_my_batch_data(self) -> Any:
        """Finds the specific batch data for this entity from the coordinator."""
        data = self.coordinator.data
        if not data:
            return None
            
        if getattr(data, "batch_id", None) == self._batch_id:
            return data
            
        if hasattr(data, "other_batches") and data.other_batches:
            for b in data.other_batches:
                if getattr(b, "batch_id", None) == self._batch_id:
                    return b
        return None

    def _update_internal_state(self):
        """Updates internal state variables from coordinator data."""
        batch_data = self._get_my_batch_data()
        
        # Для глобального сенсора all_batches передаємо весь coordinator.data
        if self._batch_id == "all_batches_global":
            batch_data = self.coordinator.data

        sensor_data = self._refresh_sensor_data(
            batch_data, 
            self._sensor_type, 
            self._attr_device_class, 
            self.entity_id
        )
        self._state = sensor_data.state
        self._attr_available = sensor_data.attr_available
        self._attr_extra_state_attributes = sensor_data.extra_state_attributes

    @property
    def state(self) -> StateType:
        """Return the state."""
        return self._state

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_available

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        _LOGGER.debug("Updating state of the sensors for batch %s.", self._batch_id)
        self._update_internal_state()
        self.async_write_ha_state()

    @staticmethod
    def _refresh_sensor_data(
        batch_data: Any,
        sensor_type: SensorKinds,
        device_class: SensorDeviceClass | None,
        entity_id: str | None
    ) -> SensorUpdateData:
        """Get sensor data strictly for ONE batch."""
        sensor_data = SensorUpdateData()
        if batch_data is None:
            return sensor_data
        
        sensor_data.attr_available = True
        custom_attributes: dict[str, Any] = dict()
        
        # Додаємо базовий атрибут до всіх
        if hasattr(batch_data, "batch_id"):
            custom_attributes["batch_id"] = batch_data.batch_id

        if sensor_type == SensorKinds.fermenting_name:
            sensor_data.state = getattr(batch_data, "brew_name", None)

        elif sensor_type == SensorKinds.brewer:
            sensor_data.state = getattr(batch_data, "brewer", None)

        elif sensor_type == SensorKinds.fermenting_current_temperature:
            sensor_data.state = getattr(batch_data, "current_step_temperature", None)

        elif sensor_type == SensorKinds.fermenting_next_date:
            sensor_data.state = getattr(batch_data, "next_step_date", None)

        elif sensor_type == SensorKinds.fermenting_next_temperature:
            sensor_data.state = getattr(batch_data, "next_step_temperature", None)

        elif sensor_type == SensorKinds.fermenting_last_reading:
            reading = getattr(batch_data, "last_reading", None)
            if reading is not None:
                sensor_data.state = getattr(reading, "sg", None)
                custom_attributes["angle"] = getattr(reading, "angle", None)
                custom_attributes["temp"] = getattr(reading, "temp", None)
                time_ms = getattr(reading, "time", None)
                if time_ms:
                    custom_attributes["time_ms"] = time_ms
                    custom_attributes["time"] = datetime.fromtimestamp(time_ms / 1000, timezone.utc)

        elif sensor_type == SensorKinds.all_batch_info:
            all_batches = []
            if hasattr(batch_data, "all_batches_data"):
                for other_batch in batch_data.all_batches_data:
                    if hasattr(other_batch, "to_attribute_entry_hassio"):
                        all_batches.append(other_batch.to_attribute_entry_hassio())
            custom_attributes["data"] = all_batches
            sensor_data.state = len(all_batches)

        elif sensor_type == SensorKinds.fermenting_start_date:
            sensor_data.state = getattr(batch_data, "start_date", None)

        elif sensor_type == SensorKinds.batch_notes:
            sensor_data.state = getattr(batch_data, "batch_notes", None)

        elif sensor_type == SensorKinds.events:
            current_time = datetime.now(timezone.utc).timestamp() * 1000
            future_events = []
            events_list = getattr(batch_data, "events", None)
            
            if events_list is not None:
                for event in events_list:
                    if getattr(event, "time", 0) > current_time and getattr(event, "active", False):
                        future_events.append({
                            "title": getattr(event, "title", ""),
                            "description": getattr(event, "description", ""),
                            "time": datetime.fromtimestamp(event.time / 1000, timezone.utc) if event.time else None,
                            "time_ms": event.time,
                            "event_type": getattr(event, "event_type", ""),
                            "day_event": getattr(event, "day_event", False),
                            "active": getattr(event, "active", False)
                        })
                
                future_events.sort(key=lambda x: x.get("time_ms", 0))
                sensor_data.state = len(future_events)
                custom_attributes["events"] = future_events

        elif sensor_type == SensorKinds.status:
            sensor_data.state = getattr(batch_data, "status", None)
            
            # Додаємо сирий JSON як атрибути, якщо він є
            raw_dict = getattr(batch_data, "raw_data", None)
            if isinstance(raw_dict, dict):
                # Відфільтровуємо важкі списки, щоб не забивати базу Home Assistant
                filtered_dict = {k: v for k, v in raw_dict.items() if k not in ["readings", "events", "notes"]} 
                custom_attributes.update(filtered_dict)

        elif sensor_type == SensorKinds.batch_no:
            sensor_data.state = getattr(batch_data, "batch_no", None)
        
        elif sensor_type == SensorKinds.batch_name:
            sensor_data.state = getattr(batch_data, "batch_name", None)
        
        elif sensor_type == SensorKinds.recipe_name:
            print("-----------getattr---------------------------")
            print(getattr(batch_data, "recipe_name", None))
            sensor_data.state = getattr(batch_data, "recipe_name", None)

        elif sensor_type == SensorKinds.brew_date:
            brew_date_ts = getattr(batch_data, "brew_date", None)
            if brew_date_ts:
                # Brewfather віддає час у мілісекундах
                sensor_data.state = datetime.fromtimestamp(brew_date_ts / 1000, timezone.utc)

        elif sensor_type == SensorKinds.measured_og:
            sensor_data.state = getattr(batch_data, "measured_og", None)

        elif sensor_type == SensorKinds.measured_fg:
            sensor_data.state = getattr(batch_data, "measured_fg", None)

        elif sensor_type == SensorKinds.measured_abv:
            sensor_data.state = getattr(batch_data, "measured_abv", None)

        sensor_data.extra_state_attributes = custom_attributes

        # Received a datetime processing
        if sensor_data.state is not None and device_class == SensorDeviceClass.TIMESTAMP:
            try:
                value = cast(datetime, sensor_data.state)
                if value.tzinfo is None:
                    raise ValueError(f"Invalid datetime: {entity_id} missing timezone information")
                if value.tzinfo != timezone.utc:
                    value = value.astimezone(timezone.utc)
                sensor_data.state = value.isoformat(timespec="seconds")
            except (AttributeError, TypeError) as err:
                pass
            
        return sensor_data

class SensorKinds(enum.Enum):
    fermenting_name = 1
    fermenting_current_temperature = 2
    fermenting_next_temperature = 3
    fermenting_next_date = 4
    fermenting_last_reading = 6
    all_batch_info = 7
    fermenting_start_date = 8
    batch_notes = 9
    events = 10
    brewer = 11
    status = 12
    batch_no = 13
    batch_name = 14
    recipe_name = 15
    measured_abv = 16
    measured_og = 17
    measured_fg = 18
    brew_date = 19