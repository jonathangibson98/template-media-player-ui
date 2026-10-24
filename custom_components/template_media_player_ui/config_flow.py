"""Config flow + options flow: create and edit the media player from the UI."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import selector
from homeassistant.helpers.template import Template

from .const import (
    ATTRIBUTES_MEDIA,
    ATTRIBUTES_PLAYER,
    CONF_ATTRIBUTES,
    CONF_AVAILABILITY,
    CONF_BASE,
    CONF_BROWSE,
    CONF_CUSTOM_ATTRIBUTES,
    CONF_DEVICE_CLASS,
    CONF_GLOBAL_TEMPLATE,
    CONF_ICON,
    CONF_SEARCH,
    CONF_SERVICE_SCRIPTS,
    CONF_SOUND_MODE_SCRIPTS,
    CONF_SOURCE_SCRIPTS,
    CONF_STATE,
    CONF_VARIABLES,
    DOMAIN,
    SERVICES_OTHER,
    SERVICES_PLAYBACK,
    SERVICES_POWER,
)

TEMPLATE = selector.TemplateSelector()
ACTIONS = selector.ActionSelector()
OBJECT = selector.ObjectSelector()
ICON = selector.IconSelector()
MEDIA_PLAYER = selector.EntitySelector(
    selector.EntitySelectorConfig(domain="media_player")
)
DEVICE_CLASS = selector.SelectSelector(
    selector.SelectSelectorConfig(
        options=["tv", "speaker", "receiver"],
        mode=selector.SelectSelectorMode.DROPDOWN,
    )
)

EMPTY = (None, "", [], {})


class TemplateMediaPlayerConfigFlow(ConfigFlow, domain=DOMAIN):
    """Create a new template media player."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return TemplateMediaPlayerOptionsFlow()

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            if user_input.get(CONF_STATE):
                try:
                    Template(user_input[CONF_STATE], self.hass).ensure_valid()
                except TemplateError:
                    errors[CONF_STATE] = "invalid_template"
            if not errors:
                data = dict(user_input)
                name = data.pop(CONF_NAME)
                options = {k: v for k, v in data.items() if v not in EMPTY}
                return self.async_create_entry(title=name, data={}, options=options)

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME): selector.TextSelector(),
                vol.Optional(CONF_DEVICE_CLASS): DEVICE_CLASS,
                vol.Optional(CONF_BASE): MEDIA_PLAYER,
                vol.Optional(CONF_STATE): TEMPLATE,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )


class TemplateMediaPlayerOptionsFlow(OptionsFlow):
    """Edit everything about the player. Each page saves as soon as you submit."""

    def __init__(self) -> None:
        self._options: dict[str, Any] | None = None
        self._pending_name: str | None = None

    # ------------------------------------------------------------- helpers
    def _current(self) -> dict[str, Any]:
        if self._options is None:
            self._options = deepcopy(dict(self.config_entry.options))
        return self._options

    def _save(self) -> None:
        self.hass.config_entries.async_update_entry(
            self.config_entry, options=deepcopy(self._current())
        )

    def _validate(self, user_input: dict[str, Any], kinds: dict[str, str]) -> dict[str, str]:
        errors: dict[str, str] = {}
        for key, kind in kinds.items():
            value = user_input.get(key)
            if value in EMPTY:
                continue
            if kind == "template":
                try:
                    Template(value, self.hass).ensure_valid()
                except TemplateError:
                    errors[key] = "invalid_template"
            elif kind == "actions":
                try:
                    cv.SCRIPT_SCHEMA(value)
                except vol.Invalid:
                    errors[key] = "invalid_actions"
            elif kind == "object":
                if not isinstance(value, dict):
                    errors[key] = "invalid_object"
            elif kind == "templates_dict":
                if not isinstance(value, dict):
                    errors[key] = "invalid_object"
                    continue
                for item in value.values():
                    try:
                        Template(str(item), self.hass).ensure_valid()
                    except TemplateError:
                        errors[key] = "invalid_template"
                        break
        return errors

    async def _group_step(
        self,
        step_id: str,
        fields: dict[str, Any],
        bucket: str | None,
        user_input: dict[str, Any] | None,
        kinds: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """One form page. `bucket` is a nested dict key in options (or None = top level)."""
        opts = self._current()
        current = opts.get(bucket, {}) if bucket else opts
        errors: dict[str, str] = {}

        if user_input is not None:
            errors = self._validate(user_input, kinds or {})
            if not errors:
                new = dict(current)
                for key in fields:
                    value = user_input.get(key)
                    if value in EMPTY:
                        new.pop(key, None)
                    else:
                        new[key] = value
                if bucket:
                    if new:
                        opts[bucket] = new
                    else:
                        opts.pop(bucket, None)
                else:
                    opts.clear()
                    opts.update(new)
                self._save()
                return await self.async_step_init()

        schema = vol.Schema({vol.Optional(k): sel for k, sel in fields.items()})
        suggested = (
            user_input
            if user_input is not None
            else {k: current[k] for k in fields if k in current}
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            errors=errors,
        )

    # ---------------------------------------------------------------- menu
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "general",
                "attributes_media",
                "attributes_player",
                "custom_attributes",
                "services_playback",
                "services_power",
                "services_other",
                "sources",
                "sound_modes",
                "browse_search",
                "finish",
            ],
        )

    async def async_step_finish(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_create_entry(title="", data=deepcopy(self._current()))

    # ------------------------------------------------------------- general
    async def async_step_general(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._group_step(
            "general",
            {
                CONF_DEVICE_CLASS: DEVICE_CLASS,
                CONF_ICON: ICON,
                CONF_BASE: MEDIA_PLAYER,
                CONF_STATE: TEMPLATE,
                CONF_AVAILABILITY: TEMPLATE,
                CONF_GLOBAL_TEMPLATE: TEMPLATE,
                CONF_VARIABLES: OBJECT,
            },
            None,
            user_input,
            {
                CONF_STATE: "template",
                CONF_AVAILABILITY: "template",
                CONF_GLOBAL_TEMPLATE: "template",
                CONF_VARIABLES: "object",
            },
        )

    # ---------------------------------------------------------- attributes
    async def async_step_attributes_media(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._group_step(
            "attributes_media",
            {n: TEMPLATE for n in ATTRIBUTES_MEDIA},
            CONF_ATTRIBUTES,
            user_input,
            {n: "template" for n in ATTRIBUTES_MEDIA},
        )

    async def async_step_attributes_player(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._group_step(
            "attributes_player",
            {n: TEMPLATE for n in ATTRIBUTES_PLAYER},
            CONF_ATTRIBUTES,
            user_input,
            {n: "template" for n in ATTRIBUTES_PLAYER},
        )

    async def async_step_custom_attributes(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._group_step(
            "custom_attributes",
            {CONF_CUSTOM_ATTRIBUTES: OBJECT},
            None,
            user_input,
            {CONF_CUSTOM_ATTRIBUTES: "templates_dict"},
        )

    # ------------------------------------------------------------- actions
    async def async_step_services_playback(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._group_step(
            "services_playback",
            {n: ACTIONS for n in SERVICES_PLAYBACK},
            CONF_SERVICE_SCRIPTS,
            user_input,
            {n: "actions" for n in SERVICES_PLAYBACK},
        )

    async def async_step_services_power(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._group_step(
            "services_power",
            {n: ACTIONS for n in SERVICES_POWER},
            CONF_SERVICE_SCRIPTS,
            user_input,
            {n: "actions" for n in SERVICES_POWER},
        )

    async def async_step_services_other(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._group_step(
            "services_other",
            {n: ACTIONS for n in SERVICES_OTHER},
            CONF_SERVICE_SCRIPTS,
            user_input,
            {n: "actions" for n in SERVICES_OTHER},
        )

    # ------------------------------------------------------ browse / search
    async def async_step_browse_search(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._group_step(
            "browse_search",
            {CONF_BROWSE: MEDIA_PLAYER, CONF_SEARCH: MEDIA_PLAYER},
            None,
            user_input,
        )

    # ------------------------------------- named scripts (sources/sound modes)
    async def _named_menu(self, step_id: str) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id=step_id,
            menu_options=[f"{step_id}_edit", f"{step_id}_remove", "init"],
        )

    async def _named_pick(
        self, step_id: str, conf_key: str, next_step: Any, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        existing = list(self._current().get(conf_key, {}))
        if user_input is not None:
            name = str(user_input.get("name") or "").strip()
            if name:
                self._pending_name = name
                return await next_step()
        if existing:
            sel: Any = selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=existing,
                    custom_value=True,
                    mode=selector.SelectSelectorMode.DROPDOWN,
                )
            )
        else:
            sel = selector.TextSelector()
        return self.async_show_form(
            step_id=step_id, data_schema=vol.Schema({vol.Required("name"): sel})
        )

    async def _named_actions(
        self, step_id: str, conf_key: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        name = self._pending_name or ""
        opts = self._current()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._validate(user_input, {"actions": "actions"})
            if not errors:
                scripts = dict(opts.get(conf_key, {}))
                if user_input.get("actions"):
                    scripts[name] = user_input["actions"]
                else:
                    scripts.pop(name, None)
                if scripts:
                    opts[conf_key] = scripts
                else:
                    opts.pop(conf_key, None)
                self._save()
                return await self.async_step_init()
        schema = vol.Schema({vol.Optional("actions"): ACTIONS})
        suggested = (
            user_input
            if user_input is not None
            else {"actions": opts.get(conf_key, {}).get(name, [])}
        )
        return self.async_show_form(
            step_id=step_id,
            data_schema=self.add_suggested_values_to_schema(schema, suggested),
            description_placeholders={"name": name},
            errors=errors,
        )

    async def _named_remove(
        self, step_id: str, conf_key: str, user_input: dict[str, Any] | None
    ) -> ConfigFlowResult:
        opts = self._current()
        existing = list(opts.get(conf_key, {}))
        if not existing:
            return await self.async_step_init()
        if user_input is not None:
            scripts = dict(opts.get(conf_key, {}))
            for name in user_input.get("names", []):
                scripts.pop(name, None)
            if scripts:
                opts[conf_key] = scripts
            else:
                opts.pop(conf_key, None)
            self._save()
            return await self.async_step_init()
        schema = vol.Schema(
            {
                vol.Required("names"): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=existing,
                        multiple=True,
                        mode=selector.SelectSelectorMode.LIST,
                    )
                )
            }
        )
        return self.async_show_form(step_id=step_id, data_schema=schema)

    # sources
    async def async_step_sources(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._named_menu("sources")

    async def async_step_sources_edit(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._named_pick(
            "sources_edit", CONF_SOURCE_SCRIPTS, self.async_step_sources_actions, user_input
        )

    async def async_step_sources_actions(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._named_actions("sources_actions", CONF_SOURCE_SCRIPTS, user_input)

    async def async_step_sources_remove(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._named_remove("sources_remove", CONF_SOURCE_SCRIPTS, user_input)

    # sound modes
    async def async_step_sound_modes(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._named_menu("sound_modes")

    async def async_step_sound_modes_edit(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._named_pick(
            "sound_modes_edit",
            CONF_SOUND_MODE_SCRIPTS,
            self.async_step_sound_modes_actions,
            user_input,
        )

    async def async_step_sound_modes_actions(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._named_actions(
            "sound_modes_actions", CONF_SOUND_MODE_SCRIPTS, user_input
        )

    async def async_step_sound_modes_remove(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return await self._named_remove(
            "sound_modes_remove", CONF_SOUND_MODE_SCRIPTS, user_input
        )
