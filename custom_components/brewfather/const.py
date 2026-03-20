DOMAIN = "brewfather"
COORDINATOR = "coordinator"

UPDATE_INTERVAL = 900 #15 minutes
MS_IN_DAY = 86400000

TEST_URI = "https://api.brewfather.app/v2/batches/"
BATCHES_URI = "https://api.brewfather.app/v2/batches/"
BATCH_URI = "https://api.brewfather.app/v2/batches/{}?include=recipe.fermentation,notes,measuredOg,batchNotes,events"
READINGS_URI = "https://api.brewfather.app/v2/batches/{}/readings"
LAST_READING_URI = "https://api.brewfather.app/v2/batches/{}/readings/last"
LOG_CUSTOM_STREAM = "http://log.brewfather.net/stream?id={}"

DRY_RUN = False
CONF_RAMP_TEMP_CORRECTION = "ramp_temp_correction"
CONF_MULTI_BATCH = "multi_batch"
CONF_ALL_BATCH_INFO_SENSOR = "all_batch_info_sensor"
CONF_CUSTOM_STREAM_ENABLED = "custom_stream_enabled"
CONF_CUSTOM_STREAM_LOGGING_ID = "custom_stream_logging_id"
CONF_CUSTOM_STREAM_TEMPERATURE_ENTITY_NAME = "custom_stream_temperature_entity_name"
CONF_CUSTOM_STREAM_TEMPERATURE_ENTITY_ATTRIBUTE = "custom_stream_temperature_entity_attribute"
CONF_CUSTOM_STREAM_GRAVITY_ENTITY_NAME = "custom_stream_gravity_entity_name"
CONF_ENABLE_PLANNING = "enable_planning"
CONF_ENABLE_BREWING = "enable_brewing"
CONF_ENABLE_FERMENTING = "enable_fermenting"
CONF_ENABLE_CONDITIONING = "enable_conditioning"
CONF_ENABLE_COMPLETED = "enable_completed"
CONF_ENABLE_ARCHIVED = "enable_archived"

STATE_PLANNING = "Planning"
STATE_BREWING = "Brewing"
STATE_FERMENTING = "Fermenting"
STATE_CONDITIONING = "Conditioning"
STATE_COMPLETED = "Completed"
STATE_ARCHIVED = "Archived"

VERSION_MAJOR = 1
VERSION_MINOR = 4