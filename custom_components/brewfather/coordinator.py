from __future__ import annotations
import logging
from logging import DEBUG
from copy import copy
from datetime import datetime, timezone, timedelta
import math
from typing import Optional
from .connection import Connection
from .models.batch_item import (
    Fermentation,
    BatchItem,
    Step,
    Reading,
    Event
)
from .models.custom_stream_data import custom_stream_data
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, UnitOfTemperature, STATE_UNKNOWN, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .const import (
    DOMAIN,
    MS_IN_DAY,
    CONF_RAMP_TEMP_CORRECTION,
    CONF_MULTI_BATCH,
    CONF_ALL_BATCH_INFO_SENSOR,
    CONF_CUSTOM_STREAM_ENABLED,
    CONF_CUSTOM_STREAM_LOGGING_ID,
    CONF_CUSTOM_STREAM_TEMPERATURE_ENTITY_NAME,
    CONF_CUSTOM_STREAM_GRAVITY_ENTITY_NAME
)

_LOGGER = logging.getLogger(__name__)

def sort_by_actual_time(entity: Fermentation):
    return entity.actual_time

class BrewfatherCoordinatorData:
    batch_id: Optional[str]
    status: Optional[str]          # НОВЕ
    batch_no: Optional[int]        # НОВЕ
    batch_name: Optional[str]
    recipe_name: Optional[str]
    brewer: Optional[str]
    brew_date: Optional[int]       # НОВЕ
    measured_og: Optional[float]   # НОВЕ
    measured_fg: Optional[float]   # НОВЕ
    measured_abv: Optional[float]  # НОВЕ
    raw_data: Optional[dict]       # НОВЕ
    current_step_temperature: Optional[float]
    next_step_date: Optional[datetime.datetime]
    next_step_temperature: Optional[float]
    last_reading: Optional[Reading]
    other_batches: list[BrewfatherCoordinatorData]
    all_batches_data: Optional[list[BatchItem]]
    start_date: Optional[datetime.datetime]
    batch_notes: Optional[str]
    events: Optional[list[Event]]
    raw_data: dict # НОВЕ: Сюди запишемо весь raw JSON для атрибутів

    def __init__(self):
        # set defaults to None
        self.batch_id = None
        self.status = None
        self.batch_no = None
        self.batch_name = None
        self.recipe_name = None
        self.brewer = None
        self.brew_date = None
        self.measured_abv = None
        self.measured_og = None
        self.measured_fg = None
        self.current_step_temperature = None
        self.next_step_date = None
        self.next_step_temperature = None
        self.last_reading = None
        self.other_batches = []
        self.all_batches_data = None
        self.start_date = None
        self.batch_notes = None
        self.events = None
        self.raw_data = {}


class BatchInfo:
    batch: BatchItem
    #readings: list[Reading]
    last_reading: Reading
    
    #def __init__(self, batch: BatchItem, readings: list[Reading]):
    def __init__(self, batch: BatchItem, last_reading: Reading):
        self.batch = batch
        self.last_reading = last_reading

class BrewfatherCoordinator(DataUpdateCoordinator[BrewfatherCoordinatorData]):
    """Class to manage fetching data from the API."""

    def __init__(self, hass: HomeAssistant, entry, update_interval: timedelta):
        self.multi_batch_mode = entry.data.get(CONF_MULTI_BATCH, False)
        self.all_batch_info_sensor = entry.data.get(CONF_ALL_BATCH_INFO_SENSOR, False)
        self.temperature_correction_enabled = entry.data.get(CONF_RAMP_TEMP_CORRECTION, False)
        self.connection = Connection(
            entry.data.get(CONF_USERNAME), 
            entry.data.get(CONF_PASSWORD)
        )
        self.custom_stream_enabled = entry.data.get(CONF_CUSTOM_STREAM_ENABLED, False)
        self.last_update_success_time: Optional[datetime] = None
        if self.custom_stream_enabled:
            self.custom_stream_logging_id = entry.data.get(CONF_CUSTOM_STREAM_LOGGING_ID, None)

            self.custom_stream_temperature_entity_name = entry.data.get(CONF_CUSTOM_STREAM_TEMPERATURE_ENTITY_NAME, None)
            
            self.custom_stream_gravity_entity_name = entry.data.get(CONF_CUSTOM_STREAM_GRAVITY_ENTITY_NAME, None)

        super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=update_interval)

    async def _async_update_data(self) -> BrewfatherCoordinatorData:
        """Update data via library."""
        try:
            _LOGGER.debug("Updating data via library")
            data = await self.update()
            # Update the last successful update time
            self.last_update_success_time = datetime.now(timezone.utc)
            return data
        except Exception as ex:
            _LOGGER.error("Error updating Brewfather data: %s", str(ex))
            raise UpdateFailed(f"Error communicating with Brewfather API: {ex}") from ex

    async def update(self) -> BrewfatherCoordinatorData:
        _LOGGER.debug("Updating data...")
        allBatches = await self.connection.get_batches()

        fermentingBatches:list[BatchInfo] = []
        all_batches_data:list[BatchInfo] = []

        #if custom stream enabled
        if self.custom_stream_enabled:
            stream_data = self.create_custom_stream_data()
            if stream_data is None:
                _LOGGER.debug("No data was found to post to custom stream")
            else:
                _LOGGER.debug("Posting custom stream data")
                success = await self.connection.post_custom_stream(self.custom_stream_logging_id, stream_data)
                if not success:
                    _LOGGER.error("Failed to post custom stream data")

        for batch in allBatches:
            batchData = await self.connection.get_batch(batch.id)
            last_reading = await self.connection.get_last_reading(batch.id)
            fermentingBatches.append(BatchInfo(batchData, last_reading))

            if self.all_batch_info_sensor:
                readings = await self.connection.get_readings(batch.id)
                all_batch_data = copy(batchData)
                all_batch_data.readings = readings

                all_batches_data.append(all_batch_data)
            elif not self.multi_batch_mode:
                break

        if len(fermentingBatches) == 0:
            return None
        
        currentTimeUtc = datetime.now().astimezone()
        main_batch_data: BrewfatherCoordinatorData = None
        #batch_data:list[BrewfatherCoordinatorData] = []
        for fermenting_batch in fermentingBatches:
            batch_data = self.get_batch_data(fermenting_batch, currentTimeUtc)
            
            if main_batch_data is None:
                main_batch_data = batch_data
            else:
                if self.multi_batch_mode:
                    main_batch_data.other_batches.append(batch_data)
                else:
                    break
        
        if self.all_batch_info_sensor:
            main_batch_data.all_batches_data = all_batches_data
            
        return main_batch_data
    
    def get_batch_data(self, currentBatch: BatchInfo, currentTimeUtc: datetime) -> BrewfatherCoordinatorData | None:
        data = BrewfatherCoordinatorData()
        
        # 1. Завжди парсимо базові дані (для будь-якого стану варки)
        data.batch_id = currentBatch.batch.id
        data.status = currentBatch.batch.status
        data.batch_no = currentBatch.batch.batch_no
        data.batch_name = currentBatch.batch.name
        data.recipe_name = currentBatch.batch.recipe.name if currentBatch.batch.recipe else "Unknown"
        data.brewer = currentBatch.batch.brewer
        data.brew_date = currentBatch.batch.brew_date
        data.measured_og = currentBatch.batch.measured_og
        data.measured_fg = currentBatch.batch.measured_fg
        data.measured_abv = currentBatch.batch.measured_abv
        data.raw_data = currentBatch.batch.raw_data
        
        data.last_reading = currentBatch.last_reading
        data.batch_notes = currentBatch.batch.batch_notes
        data.events = currentBatch.batch.events

        # 2. Шукаємо початок ферментації (для логіки температурних кроків)
        fermenting_start: int | None = None
        if currentBatch.batch.notes:
            for note in currentBatch.batch.notes:
                if note.status == "Fermenting":
                    fermenting_start = note.timestamp
                    break

        # Якщо ми ще не на етапі ферментації (Planning, Brewing) — повертаємо базові дані.
        # Раніше тут було `if fermenting_start is None: return None`, що вбивало відображення цих батчів!
        if fermenting_start is None:
            return data
        
        # 3. Логіка температурних кроків (тільки якщо ферментація почалась і є рецепт)
        data.start_date = self.datetime_fromtimestamp(fermenting_start)
        currentStep: Step | None = None
        nextStep: Step | None = None
        prevStep: Step | None = None
        curren_step_is_ramping = False
        current_step_actual_start_time_utc: datetime|None = None

        if currentBatch.batch.recipe is not None and currentBatch.batch.recipe.fermentation is not None and currentBatch.batch.recipe.fermentation.steps is not None:
            _LOGGER.debug("%s (%s) | CurrentTimeUtc: %s", currentBatch.batch.recipe.name, currentBatch.batch.id, currentTimeUtc.strftime("%m/%d/%Y, %H:%M:%S"))
            
            for (index, step) in enumerate[Step](
                sorted(currentBatch.batch.recipe.fermentation.steps, key=lambda x: x.actual_time)
            ):
                step_start_datetime_utc = self.datetime_fromtimestamp_with_fermentingstart(
                    step.actual_time, fermenting_start
                )
                step_end_datetime_utc = self.datetime_fromtimestamp_with_fermentingstart(
                    step.actual_time + step.step_time * MS_IN_DAY, fermenting_start
                )

                actual_start_time_utc = step_start_datetime_utc
                if self.temperature_correction_enabled and step.ramp is not None and step.ramp > 0:
                    actual_start_time_utc = step_start_datetime_utc + timedelta(days = -1 * step.ramp)

                if actual_start_time_utc <= currentTimeUtc:
                    currentStep = step
                    current_step_actual_start_time_utc = actual_start_time_utc
                    if step_start_datetime_utc > currentTimeUtc:
                        curren_step_is_ramping = True
                    if index > 0:
                        prevStep = currentBatch.batch.recipe.fermentation.steps[index - 1]
                elif actual_start_time_utc > currentTimeUtc:
                    nextStep = step
                    break

            if currentStep is not None:
                data.current_step_temperature = currentStep.step_temp
                
                rampingStep = currentStep
                stepBeforeRamp = prevStep
                if self.temperature_correction_enabled and curren_step_is_ramping and stepBeforeRamp is not None and rampingStep.ramp is not None and rampingStep.ramp > 0:
                    number_of_steps = math.floor(rampingStep.step_temp - stepBeforeRamp.step_temp)
                    if number_of_steps > 0:
                        ramp_hours = rampingStep.ramp * 24
                        hours_per_ramp = ramp_hours / number_of_steps

                        time_already_ramping:timedelta = (current_step_actual_start_time_utc - currentTimeUtc)
                        hours_already_ramping  = abs((time_already_ramping.days * 24) + (time_already_ramping.seconds / 3600))
                        current_ramp_step = math.floor(hours_already_ramping / hours_per_ramp)
                        temp_increase = current_ramp_step

                        if current_ramp_step > number_of_steps:
                            _LOGGER.error("Invalid temperature ramping step found!")
                        elif temp_increase > 0:
                            new_temp = round(stepBeforeRamp.step_temp + temp_increase, ndigits=1)
                            data.current_step_temperature = new_temp

            if nextStep is not None:
                data.next_step_temperature = nextStep.step_temp
                data.next_step_date = self.datetime_fromtimestamp_with_fermentingstart(
                    nextStep.actual_time, fermenting_start
                )

        return data

    def datetime_fromtimestamp(self, epoch: int) -> datetime:
        return datetime.fromtimestamp(epoch / 1000, timezone.utc)

    def datetime_fromtimestamp_with_fermentingstart(
        self, epoch: int | None, fermenting_start: int | None
    ) -> datetime:
        datetime_value = self.datetime_fromtimestamp(epoch)

        if fermenting_start is not None:
            fermenting_start_date = datetime.fromtimestamp(fermenting_start / 1000)

            datetime_value += timedelta(
                hours=fermenting_start_date.hour,
                minutes=fermenting_start_date.minute,
                seconds=fermenting_start_date.second,
            )

        return datetime_value

    def get_brewfather_temp_unit(self, ha_unit: str) -> str:
        """Convert Home Assistant temperature unit to Brewfather custom stream unit."""
        if ha_unit == UnitOfTemperature.CELSIUS:
            return "C"
        elif ha_unit == UnitOfTemperature.FAHRENHEIT:
            return "F"
        elif ha_unit == UnitOfTemperature.KELVIN:
            return "K"
        else:
            _LOGGER.warning("Unsupported temperature unit '%s', defaulting to Celsius", ha_unit)
            return "C"  # Default to Celsius

    def create_custom_stream_data(self) -> Optional[custom_stream_data]:
        stream_data = custom_stream_data(name = "HomeAssistant")

        entity = self.hass.states.get(self.custom_stream_temperature_entity_name)
        if entity is None:
            return None
        
        # Get temperature unit from entity
        entity_unit = entity.attributes.get("unit_of_measurement")
        if entity_unit:
            stream_data.temp_unit = self.get_brewfather_temp_unit(entity_unit)
        else:
            stream_data.temp_unit = "C"  # Default to Celsius if no unit specified
        
        try:
            temp_value = entity.state
            
            # Convert to float if possible
            if temp_value is not None and temp_value != STATE_UNKNOWN and temp_value != STATE_UNAVAILABLE:
                stream_data.temp = float(temp_value)
            else:
                return None
        except (ValueError, TypeError) as ex:
            _LOGGER.warning("Unable to convert temperature value '%s' to float: %s", temp_value, str(ex))
            return None

        # Get gravity if configured
        gravity_entity_name = getattr(self, 'custom_stream_gravity_entity_name', None)
        if gravity_entity_name:
            gravity_entity = self.hass.states.get(gravity_entity_name)
            if gravity_entity is not None:
                try:
                    gravity_value = gravity_entity.state
                    if gravity_value is not None and gravity_value != STATE_UNKNOWN and gravity_value != STATE_UNAVAILABLE:
                        stream_data.gravity = float(gravity_value)
                        _LOGGER.debug("Posting gravity data: %s", stream_data.gravity)
                except (ValueError, TypeError) as ex:
                    _LOGGER.warning("Unable to convert gravity value '%s' to float: %s", gravity_value, str(ex))

        return stream_data
