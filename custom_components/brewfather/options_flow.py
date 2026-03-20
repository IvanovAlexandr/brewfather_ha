from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.schema_config_entry_flow import (
    SchemaConfigFlowHandler,
    SchemaFlowFormStep,
    SchemaFlowMenuStep,
)

from .const import (
    DOMAIN,
    CONF_ENABLE_PLANNING,
    CONF_ENABLE_BREWING,
    CONF_ENABLE_FERMENTING,
    CONF_ENABLE_CONDITIONING,
    CONF_ENABLE_COMPLETED,
    CONF_ENABLE_ARCHIVED,
)

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_ENABLE_PLANNING, default=True): selector.BooleanSelector(),
        vol.Optional(CONF_ENABLE_BREWING, default=True): selector.BooleanSelector(),
        vol.Optional(CONF_ENABLE_FERMENTING, default=True): selector.BooleanSelector(),
        vol.Optional(CONF_ENABLE_CONDITIONING, default=True): selector.BooleanSelector(),
        vol.Optional(CONF_ENABLE_COMPLETED, default=False): selector.BooleanSelector(),
        vol.Optional(CONF_ENABLE_ARCHIVED, default=False): selector.BooleanSelector(),
    }
)


class BrewfatherOptionsFlowHandler(SchemaConfigFlowHandler, domain=DOMAIN):
    """Handle a flow for configuring Brewfather options."""

    config_entry: ConfigEntry

    @callback
    def async_get_options_schema(self) -> vol.Schema:
        """Return a schema for the options flow."""
        return OPTIONS_SCHEMA

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> SchemaFlowFormStep | SchemaFlowMenuStep:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=self.async_get_options_schema(),
            last_step=True,
        )
