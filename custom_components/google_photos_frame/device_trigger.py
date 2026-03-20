"""Device triggers for Google Photos Frame."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN

TRIGGER_TYPE_PHOTO_CHANGED = "photo_changed"

TRIGGER_TYPES = [TRIGGER_TYPE_PHOTO_CHANGED]

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend(
    {
        vol.Required(CONF_TYPE): vol.In(TRIGGER_TYPES),
    }
)


async def async_get_triggers(
    _hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """Return a list of triggers."""
    return [
        {
            CONF_PLATFORM: "device",
            CONF_DOMAIN: DOMAIN,
            CONF_DEVICE_ID: device_id,
            CONF_TYPE: TRIGGER_TYPE_PHOTO_CHANGED,
        }
    ]


@callback
def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action,
    trigger_info: dict,
) -> None:
    """Attach a trigger."""
    trigger_type = config[CONF_TYPE]
    device_id = config[CONF_DEVICE_ID]

    if trigger_type == TRIGGER_TYPE_PHOTO_CHANGED:
        event_config = {
            event_trigger.CONF_EVENT_TYPE: f"{DOMAIN}_photo_changed",
            event_trigger.CONF_EVENT_DATA: {CONF_DEVICE_ID: device_id},
        }
        return event_trigger.async_attach_trigger(
            hass, event_config, action, trigger_info
        )

    return None
