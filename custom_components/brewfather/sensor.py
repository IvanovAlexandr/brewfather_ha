"""Platform for sensor integration."""
from __future__ import annotations
from datetime import datetime, timezone
import enum
import logging
from typing import cast, Any
from homeassistant.core import callback
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature
from homeassistant.components.sensor import SensorEntity, SensorStateClass, SensorEntityDescription, SensorDeviceClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType
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
        self._attr_unique_id = f"{entry.entry_id}_{entity_description.key}"
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
    """Set up sensors for each active batch."""
    coordinator = hass.data[DOMAIN][entry.entry_id][COORDINATOR]

    shared = coordinator.get_shared_data_for_entities() if hasattr(coordinator, "get_shared_data_for_entities") else getattr(coordinator, "data", {}) or {}
    active_batches = shared.get("active_batches", []) or []

    entities = []
    # Base sensor descriptors or definitions
    try:
        sensor_defs = SENSOR_DEFINITIONS
    except Exception:
        sensor_defs = []

    for batch in active_batches:
        # Determine batch id for unique id
        batch_id = None
        try:
            batch_id = getattr(batch, "id", None) or getattr(batch, "batch_id", None)
        except Exception:
            try:
                batch_id = batch.get("id") or batch.get("batch_id")
            except Exception:
                batch_id = None

        for sdef in sensor_defs:
            unique = f"{DOMAIN}_{sdef['type']}_{batch_id}" if batch_id else f"{DOMAIN}_{sdef['type']}"
            # Create sensor entity with batch context
            entity = BrewfatherBatchSensor(coordinator, sdef, batch, unique)
            entities.append(entity)

    if entities:
        async_add_entities(entities, True)

class BrewfatherBatchSensor:
    """Defines a sensor."""

    def __init__(self, coordinator, definition, batch, unique_id):
        self._coordinator = coordinator
        self._definition = definition
        self._batch = batch
        self._unique_id = unique_id

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def extra_state_attributes(self):
        attrs = {}
        # include batch context so template sensors can show stage/id
        try:
            if hasattr(self._batch, "get_stage_attributes"):
                attrs.update(self._batch.get_stage_attributes())
            elif hasattr(self._batch, "to_dict"):
                attrs["batch"] = self._batch.to_dict()
            else:
                attrs["batch"] = dict(self._batch)
        except Exception:
            attrs["batch"] = self._batch

        # Merge any existing attribute building logic
        # ...existing attribute building code...
        return attrs

    # ...existing code...

class BrewfatherSensor(CoordinatorEntity[BrewfatherCoordinator], SensorEntity):
    """An entity using CoordinatorEntity.

    The CoordinatorEntity class provides:
      should_poll
      async_update
      async_added_to_hass
      available

    """
    """Defines a sensor."""

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        sensorKind: SensorKinds,
        description: SensorEntityDescription,
    ):
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        self._entity_description = description
        self._sensor_type = sensorKind


        # # Set Friendly name when sensor is first created
        self._attr_has_entity_name = True
        self._attr_name = f"{SENSOR_PREFIX} - {self._entity_description.name}"
        self._name = f"{SENSOR_PREFIX} - {self._entity_description.name}"

        # The unique identifier for this sensor within Home Assistant
        # has nothing to do with the entity_id, it is the internal unique_id of the sensor entity registry
        self._attr_unique_id = f"{SENSOR_PREFIX}_{self._entity_description.key}"


        self._attr_icon = self._entity_description.icon
        self._attr_state_class = self._entity_description.state_class
        self._attr_native_unit_of_measurement = self._entity_description.native_unit_of_measurement
        self._attr_device_class = self._entity_description.device_class
        #self._state = None
        self._discovery = False
        self._dev_id = {}

        brewfatherCoordinator: BrewfatherCoordinator = coordinator
        sensor_data = self._refresh_sensor_data(brewfatherCoordinator.data, self._sensor_type, self.device_class, self.entity_id)
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
        """Update Sensor Entity."""
        _LOGGER.debug(" _handle_coordinator_update Updating state of the sensors.")
        #await self.coordinator.async_request_refresh()
        brewfatherCoordinator: BrewfatherCoordinator = self.coordinator
        sensor_data = self._refresh_sensor_data(brewfatherCoordinator.data, self._sensor_type, self.device_class, self.entity_id)
        self._state = sensor_data.state
        self._attr_available = sensor_data.attr_available
        self.async_write_ha_state()

    @staticmethod
    def _refresh_sensor_data(
        data: BrewfatherCoordinatorData,
        sensor_type: str,
        device_class: SensorDeviceClass,
        entity_id: str
    ) -> SensorUpdateData:
        """Get sensor data."""
        sensor_data = SensorUpdateData()
        if data is None:
            return sensor_data
        
        sensor_data.attr_available = True
        custom_attributes:dict[str, Any] = dict()

        if sensor_type == SensorKinds.fermenting_name:
            sensor_data.state = data.brew_name
            custom_attributes["batch_id"] = data.batch_id

            other_batches_data = []
            for other_batch_data in data.other_batches:
                other_batches_data.append({
                    "batch_id": other_batch_data.batch_id,
                    "state": other_batch_data.brew_name
                })
            if len(other_batches_data)  > 0:
                custom_attributes["other_batches"] = other_batches_data

        elif sensor_type == SensorKinds.fermenting_current_temperature:
            sensor_data.state = data.current_step_temperature
            custom_attributes["batch_id"] = data.batch_id

            other_batches_data = []
            for other_batch_data in data.other_batches:
                other_batches_data.append({
                    "batch_id": other_batch_data.batch_id,
                    "state": other_batch_data.current_step_temperature
                })
            if len(other_batches_data)  > 0:
                custom_attributes["other_batches"] = other_batches_data

        elif sensor_type == SensorKinds.fermenting_next_date:
            sensor_data.state = data.next_step_date
            custom_attributes["batch_id"] = data.batch_id

            other_batches_data = []
            for other_batch_data in data.other_batches:
                other_batches_data.append({
                    "batch_id": other_batch_data.batch_id,
                    "state": other_batch_data.next_step_date
                })
            if len(other_batches_data)  > 0:
                custom_attributes["other_batches"] = other_batches_data

        elif sensor_type == SensorKinds.fermenting_next_temperature:
            sensor_data.state = data.next_step_temperature
            custom_attributes["batch_id"] = data.batch_id

            other_batches_data = []
            for other_batch_data in data.other_batches:
                other_batches_data.append({
                    "batch_id": other_batch_data.batch_id,
                    "state": other_batch_data.next_step_temperature
                })
            if len(other_batches_data)  > 0:
                custom_attributes["other_batches"] = other_batches_data

        elif sensor_type == SensorKinds.fermenting_last_reading:
            if data.last_reading is not None:
                sensor_data.state = data.last_reading.sg
                custom_attributes["batch_id"] = data.batch_id

                custom_attributes["angle"] = data.last_reading.angle
                custom_attributes["temp"] = data.last_reading.temp
                custom_attributes["time_ms"] = data.last_reading.time
                custom_attributes["time"] = datetime.fromtimestamp(data.last_reading.time / 1000, timezone.utc)
                
                other_batches_data = []
                for other_batch_data in data.other_batches:
                    other_batches_data.append({
                        "state": other_batch_data.last_reading.sg,
                        "batch_id": other_batch_data.batch_id,
                        "angle": other_batch_data.last_reading.angle,
                        "temp": other_batch_data.last_reading.temp,
                        "time_ms": other_batch_data.last_reading.time,
                        "time": datetime.fromtimestamp(data.last_reading.time / 1000, timezone.utc)
                    })
                    
                if len(other_batches_data)  > 0:
                    custom_attributes["other_batches"] = other_batches_data

        elif sensor_type == SensorKinds.all_batch_info:

            all_batches = []
            for other_batch in data.all_batches_data:
                all_batches.append(other_batch.to_attribute_entry_hassio())
                
            custom_attributes["data"] = all_batches
            sensor_data.state = len(all_batches)

        elif sensor_type == SensorKinds.fermenting_start_date:
            if data.start_date is not None:
                sensor_data.state = data.start_date
                custom_attributes["batch_id"] = data.batch_id
                
                other_batches_data = []
                for other_batch_data in data.other_batches:
                    other_batches_data.append({
                        "batch_id": other_batch_data.batch_id,
                        "state": other_batch_data.start_date
                    })
                if len(other_batches_data)  > 0:
                    custom_attributes["other_batches"] = other_batches_data

        elif sensor_type == SensorKinds.batch_notes:
            if data.batch_notes is not None:
                sensor_data.state = data.batch_notes
                custom_attributes["batch_id"] = data.batch_id
                
                other_batches_data = []
                for other_batch_data in data.other_batches:
                    if other_batch_data.batch_notes is not None:
                        other_batches_data.append({
                            "batch_id": other_batch_data.batch_id,
                            "state": other_batch_data.batch_notes
                        })
                if len(other_batches_data)  > 0:
                    custom_attributes["other_batches"] = other_batches_data

        elif sensor_type == SensorKinds.events:
            # Filter for future events that are active
            current_time = datetime.now(timezone.utc).timestamp() * 1000  # Convert to milliseconds
            future_events = []
            
            if data.events is not None:
                for event in data.events:
                    # Filter: must be in the future AND active must be True
                    if event.time is not None and event.time > current_time and event.active is True:
                        future_events.append({
                            "title": event.title,
                            "description": event.description,
                            "time": datetime.fromtimestamp(event.time / 1000, timezone.utc),
                            "time_ms": event.time,
                            "event_type": event.event_type,
                            "day_event": event.day_event,
                            "active": event.active
                        })
                
                # Sort by time
                future_events.sort(key=lambda x: x["time_ms"])
                
                sensor_data.state = len(future_events)
                custom_attributes["batch_id"] = data.batch_id
                custom_attributes["events"] = future_events
                
                # Add other batches events
                other_batches_data = []
                for other_batch_data in data.other_batches:
                    batch_future_events = []
                    if other_batch_data.events is not None:
                        for event in other_batch_data.events:
                            # Filter: must be in the future AND active must be True
                            if event.time is not None and event.time > current_time and event.active is True:
                                batch_future_events.append({
                                    "title": event.title,
                                    "description": event.description,
                                    "time": datetime.fromtimestamp(event.time / 1000, timezone.utc),
                                    "time_ms": event.time,
                                    "event_type": event.event_type,
                                    "day_event": event.day_event,
                                    "active": event.active
                                })
                        batch_future_events.sort(key=lambda x: x["time_ms"])
                    
                    if len(batch_future_events) > 0:
                        other_batches_data.append({
                            "batch_id": other_batch_data.batch_id,
                            "state": len(batch_future_events),
                            "events": batch_future_events
                        })
                
                if len(other_batches_data)  > 0:
                    custom_attributes["other_batches"] = other_batches_data

        sensor_data.extra_state_attributes = custom_attributes

        # Received a datetime
        if sensor_data.state is not None and device_class == SensorDeviceClass.TIMESTAMP:
            try:
                # We cast the value, to avoid using isinstance, but satisfy
                # typechecking. The errors are guarded in this try.
                value = cast(datetime, sensor_data.state)
                if value.tzinfo is None:
                    raise ValueError(
                        f"Invalid datetime: {entity_id} provides state '{value}', "
                        "which is missing timezone information"
                    )

                if value.tzinfo != timezone.utc:
                    value = value.astimezone(timezone.utc)

                _LOGGER.debug("value %s, %s", value, value.tzinfo)

                #return value.isoformat(timespec="seconds")
                sensor_data.state =value.isoformat(timespec="seconds")
            except (AttributeError, TypeError) as err:
                raise ValueError(
                    f"Invalid datetime: {entity_id} has a timestamp device class"
                    f"but does not provide a datetime state but {type(value)}"
                ) from err
            
        return sensor_data

class SensorKinds(enum.Enum):
    fermenting_name = 1
    fermenting_current_temperature = 2
    fermenting_next_temperature = 3
    fermenting_next_date = 4
    #fermenting_batches = 5
    fermenting_last_reading = 6
    all_batch_info = 7
    fermenting_start_date = 8
    batch_notes = 9
    events = 10
