from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowHandler

from .const import (
    DOMAIN,
    CONF_ENABLE_PLANNING,
    CONF_ENABLE_BREWING,
    CONF_ENABLE_FERMENTING,
    CONF_ENABLE_CONDITIONING,
    CONF_ENABLE_COMPLETED,
    CONF_ENABLE_ARCHIVED,
)

_LOGGER = logging.getLogger(__name__)


class BrewfatherOptionsFlowHandler(FlowHandler):
    """Handle a flow for configuring Brewfather options."""

    config_entry: ConfigEntry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> dict:
        """Manage the options."""
        if user_input is not None:
            return self.async_abort(reason="reconfigure_successful", data=user_input)

        options_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_ENABLE_PLANNING,
                    default=self.config_entry.options.get(CONF_ENABLE_PLANNING, True),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_BREWING,
                    default=self.config_entry.options.get(CONF_ENABLE_BREWING, True),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_FERMENTING,
                    default=self.config_entry.options.get(CONF_ENABLE_FERMENTING, True),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_CONDITIONING,
                    default=self.config_entry.options.get(CONF_ENABLE_CONDITIONING, True),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_COMPLETED,
                    default=self.config_entry.options.get(CONF_ENABLE_COMPLETED, False),
                ): bool,
                vol.Optional(
                    CONF_ENABLE_ARCHIVED,
                    default=self.config_entry.options.get(CONF_ENABLE_ARCHIVED, False),
                ): bool,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            last_step=True,
        )
