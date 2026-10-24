"""Template media player entity (configured entirely from the UI)."""
from __future__ import annotations

import ast
import logging
from datetime import datetime
from typing import Any

from homeassistant.components.media_player import (
    MediaPlayerDeviceClass,
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    RepeatMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, TemplateError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import (
    TrackTemplate,
    async_track_state_change_event,
    async_track_template_result,
)
from homeassistant.helpers.script import SCRIPT_MODE_PARALLEL, Script
from homeassistant.helpers.template import Template
from homeassistant.util import dt as dt_util

from .const import (
    ALL_ATTRIBUTES,
    BOOL_ATTRIBUTES,
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
    EXTRA_ONLY_ATTRIBUTES,
    FLOAT_ATTRIBUTES,
    INT_ATTRIBUTES,
)

_LOGGER = logging.getLogger(__name__)

F = MediaPlayerEntityFeature

# Which feature flag each configured action switches on
FEATURE_MAP: dict[str, MediaPlayerEntityFeature] = {
    "turn_on": F.TURN_ON,
    "turn_off": F.TURN_OFF,
    "toggle": F.TURN_ON | F.TURN_OFF,
    "media_play": F.PLAY,
    "media_pause": F.PAUSE,
    "media_stop": F.STOP,
    "media_play_pause": F.PLAY | F.PAUSE,
    "media_next_track": F.NEXT_TRACK,
    "media_previous_track": F.PREVIOUS_TRACK,
    "media_seek": F.SEEK,
    "volume_set": F.VOLUME_SET,
    "volume_mute": F.VOLUME_MUTE,
    "volume_up": F.VOLUME_STEP,
    "volume_down": F.VOLUME_STEP,
    "shuffle_set": F.SHUFFLE_SET,
    "repeat_set": F.REPEAT_SET,
    "play_media": F.PLAY_MEDIA,
    "clear_playlist": F.CLEAR_PLAYLIST,
    "join": F.GROUPING,
    "unjoin": F.GROUPING,
}

NONE_STRINGS = {"", "none", "unknown", "unavailable", "null"}
FALSE_STRINGS = {"false", "off", "no", "0"}

# Attributes that MediaPlayerEntity supports natively through _attr_<name>
ENTITY_ATTRS = [
    a
    for a in ALL_ATTRIBUTES
    if a != "entity_picture" and a not in EXTRA_ONLY_ATTRIBUTES
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Create the media player for this config entry."""
    async_add_entities([TemplateMediaPlayer(hass, entry)])


def _clean(value: Any) -> Any:
    """Turn 'none', 'unknown' and friends into None."""
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return None if stripped.lower() in NONE_STRINGS else stripped
    return value


def _to_list(value: Any) -> list[str] | None:
    if isinstance(value, (list, tuple, set)):
        return [str(v) for v in value]
    text = str(value).strip()
    if text.startswith("["):
        try:
            parsed = ast.literal_eval(text)
            return [str(v) for v in parsed]
        except (ValueError, SyntaxError):
            pass
    return [part.strip() for part in text.split(",") if part.strip()]


def _coerce(name: str, value: Any) -> Any:
    """Convert a rendered value to the type the entity expects."""
    if value is None:
        return None
    try:
        if name in INT_ATTRIBUTES:
            return int(float(value))
        if name in FLOAT_ATTRIBUTES:
            return float(value)
        if name in BOOL_ATTRIBUTES:
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in ("true", "on", "yes", "1")
        if name == "media_position_updated_at":
            if isinstance(value, datetime):
                return value
            return dt_util.parse_datetime(str(value))
        if name == "repeat":
            return RepeatMode(str(value).strip().lower())
        if name == "group_members":
            return _to_list(value)
        return str(value)
    except (ValueError, TypeError):
        _LOGGER.warning("Could not convert %r to a valid value for %s", value, name)
        return None


class TemplateMediaPlayer(MediaPlayerEntity):
    """A media player whose state, attributes and actions come from templates."""

    _attr_should_poll = False
    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self._entry = entry
        self._cfg: dict[str, Any] = dict(entry.options)

        self._attr_unique_id = entry.entry_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)}, name=entry.title
        )
        if icon := self._cfg.get(CONF_ICON):
            self._attr_icon = icon
        if dc := self._cfg.get(CONF_DEVICE_CLASS):
            try:
                self._attr_device_class = MediaPlayerDeviceClass(dc)
            except ValueError:
                _LOGGER.warning("Unknown device class %s", dc)

        self._base: str | None = self._cfg.get(CONF_BASE) or None
        self._browse_target: str | None = self._cfg.get(CONF_BROWSE) or self._base
        self._search_target: str | None = self._cfg.get(CONF_SEARCH) or self._base

        self._variables: dict[str, Any] = {}
        self._state_tpl: Template | None = None
        self._avail_tpl: Template | None = None
        self._attr_tpls: dict[str, Template] = {}
        self._custom_tpls: dict[str, Template] = {}
        self._scripts: dict[str, Script] = {}
        self._source_scripts: dict[str, Script] = {}
        self._sound_scripts: dict[str, Script] = {}
        self._features = MediaPlayerEntityFeature(0)

        self._picture: str | None = None
        self._extra: dict[str, Any] = {}
        self._last_pos: Any = None
        self._last_pos_stamp: datetime | None = None

    # ------------------------------------------------------------------ setup
    async def async_added_to_hass(self) -> None:
        """Build templates + scripts, start tracking, do the first render."""
        self._variables = self._build_variables()
        self._build_templates()
        self._build_scripts()
        self._features = self._compute_features()
        self._start_tracking()
        self._refresh()

    def _build_variables(self) -> dict[str, Any]:
        """Render `variables` once. Later variables can use earlier ones."""
        out: dict[str, Any] = {}
        for key, value in (self._cfg.get(CONF_VARIABLES) or {}).items():
            if isinstance(value, str):
                try:
                    out[key] = Template(value, self.hass).async_render(variables=out)
                except TemplateError as err:
                    _LOGGER.warning("Variable %s failed to render: %s", key, err)
                    out[key] = value
            else:
                out[key] = value
        return out

    def _make_template(self, source: str) -> Template:
        """Prepend the global template, so its {% set %} lines are visible."""
        glob = (self._cfg.get(CONF_GLOBAL_TEMPLATE) or "").strip()
        return Template(f"{glob}\n{source}" if glob else source, self.hass)

    def _build_templates(self) -> None:
        if src := self._cfg.get(CONF_STATE):
            self._state_tpl = self._make_template(src)
        if src := self._cfg.get(CONF_AVAILABILITY):
            self._avail_tpl = self._make_template(src)
        for name, src in (self._cfg.get(CONF_ATTRIBUTES) or {}).items():
            if src:
                self._attr_tpls[name] = self._make_template(src)
        for name, src in (self._cfg.get(CONF_CUSTOM_ATTRIBUTES) or {}).items():
            if isinstance(src, str) and src:
                self._custom_tpls[name] = self._make_template(src)
            else:
                # plain value (number, bool...) - wrap so it renders the same way
                self._custom_tpls[name] = self._make_template(str(src))

    def _make_script(self, label: str, actions: Any) -> Script | None:
        try:
            sequence = cv.SCRIPT_SCHEMA(actions)
        except Exception as err:  # noqa: BLE001
            _LOGGER.error("Invalid actions for %s: %s", label, err)
            return None
        return Script(
            self.hass,
            sequence,
            f"{self._entry.title} {label}",
            DOMAIN,
            script_mode=SCRIPT_MODE_PARALLEL,
            max_runs=10,
        )

    def _build_scripts(self) -> None:
        for key, actions in (self._cfg.get(CONF_SERVICE_SCRIPTS) or {}).items():
            if script := self._make_script(key, actions):
                self._scripts[key] = script
        for key, actions in (self._cfg.get(CONF_SOURCE_SCRIPTS) or {}).items():
            if script := self._make_script(f"source {key}", actions):
                self._source_scripts[key] = script
        for key, actions in (self._cfg.get(CONF_SOUND_MODE_SCRIPTS) or {}).items():
            if script := self._make_script(f"sound mode {key}", actions):
                self._sound_scripts[key] = script

    def _compute_features(self) -> MediaPlayerEntityFeature:
        features = MediaPlayerEntityFeature(0)
        for key in self._scripts:
            features |= FEATURE_MAP.get(key, MediaPlayerEntityFeature(0))
        if self._source_scripts:
            features |= F.SELECT_SOURCE
        if self._sound_scripts:
            features |= F.SELECT_SOUND_MODE
        if self._browse_target:
            features |= F.BROWSE_MEDIA
        if self._search_target and hasattr(F, "SEARCH_MEDIA"):
            features |= F.SEARCH_MEDIA
        return features

    def _start_tracking(self) -> None:
        """Re-render whenever any entity used by a template changes."""
        tracked: list[TrackTemplate] = []

        def add(tpl: Template | None, extra: dict[str, Any] | None = None) -> None:
            if tpl is None or getattr(tpl, "is_static", False):
                return
            tracked.append(TrackTemplate(tpl, {**self._variables, **(extra or {})}))

        add(self._state_tpl)
        add(self._avail_tpl)
        for name, tpl in self._attr_tpls.items():
            add(tpl, {"attribute": name})
        for name, tpl in self._custom_tpls.items():
            add(tpl, {"attribute": name})

        if tracked:
            info = async_track_template_result(
                self.hass, tracked, self._template_updated
            )
            self.async_on_remove(info.async_remove)

        if self._base:
            self.async_on_remove(
                async_track_state_change_event(
                    self.hass, [self._base], self._base_changed
                )
            )

    @callback
    def _template_updated(self, event: Event | None, updates: list) -> None:
        self._refresh()
        self.async_write_ha_state()

    @callback
    def _base_changed(self, event: Event) -> None:
        self._refresh()
        self.async_write_ha_state()

    # --------------------------------------------------------------- rendering
    def _render(self, tpl: Template | None, extra: dict[str, Any] | None = None) -> Any:
        if tpl is None:
            return None
        try:
            result = tpl.async_render(
                variables={**self._variables, **(extra or {})}, parse_result=False
            )
        except TemplateError as err:
            _LOGGER.warning("Template error in %s: %s", self.entity_id, err)
            return None
        return _clean(result)

    @callback
    def _refresh(self) -> None:
        """Re-render every template and push the values onto the entity."""
        base_state = self.hass.states.get(self._base) if self._base else None

        # availability
        if self._avail_tpl is not None:
            avail = self._render(self._avail_tpl)
            self._attr_available = (
                avail is not None and str(avail).lower() not in FALSE_STRINGS
            )
        elif base_state is not None and base_state.state == "unavailable":
            self._attr_available = False
        else:
            self._attr_available = True

        # state
        if self._state_tpl is not None:
            raw_state = self._render(self._state_tpl)
        elif base_state is not None:
            raw_state = _clean(base_state.state)
        else:
            raw_state = "on"
        if raw_state is None:
            self._attr_state = None
        else:
            try:
                self._attr_state = MediaPlayerState(str(raw_state).lower())
            except ValueError:
                _LOGGER.warning(
                    "%s: state template returned %r - must be one of %s",
                    self.entity_id,
                    raw_state,
                    ", ".join(s.value for s in MediaPlayerState),
                )
                self._attr_state = None

        # attributes
        values: dict[str, Any] = {}
        for name in ALL_ATTRIBUTES:
            tpl = self._attr_tpls.get(name)
            if tpl is not None:
                raw = self._render(tpl, {"attribute": name})
            elif base_state is not None:
                raw = _clean(base_state.attributes.get(name))
            else:
                raw = None
            values[name] = _coerce(name, raw)

        # media_position needs a timestamp, otherwise HA ignores it
        if values["media_position"] is not None and values["media_position_updated_at"] is None:
            if values["media_position"] != self._last_pos or self._last_pos_stamp is None:
                self._last_pos_stamp = dt_util.utcnow()
            values["media_position_updated_at"] = self._last_pos_stamp
        self._last_pos = values["media_position"]

        extra: dict[str, Any] = {}
        for name, value in values.items():
            if name in ENTITY_ATTRS:
                setattr(self, f"_attr_{name}", value)
            elif name == "entity_picture":
                self._picture = value
            elif value is not None:
                extra[name] = value

        # source + sound mode lists
        if self._source_scripts:
            self._attr_source_list = list(self._source_scripts)
        elif base_state is not None:
            self._attr_source_list = base_state.attributes.get("source_list")
        else:
            self._attr_source_list = None

        if self._sound_scripts:
            self._attr_sound_mode_list = list(self._sound_scripts)
        elif base_state is not None:
            self._attr_sound_mode_list = base_state.attributes.get("sound_mode_list")
        else:
            self._attr_sound_mode_list = None

        # custom attributes (anything you want)
        for name, tpl in self._custom_tpls.items():
            extra[name] = self._render(tpl, {"attribute": name})
        self._extra = extra

    # -------------------------------------------------------------- properties
    @property
    def supported_features(self) -> MediaPlayerEntityFeature:
        features = self._features
        if self._base:
            base = self.hass.states.get(self._base)
            if base is not None:
                try:
                    features |= MediaPlayerEntityFeature(
                        int(base.attributes.get("supported_features", 0))
                    )
                except (ValueError, TypeError):
                    pass
        return features

    @property
    def entity_picture(self) -> str | None:
        if self._picture:
            return self._picture
        return super().entity_picture

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        return self._extra or None

    # ----------------------------------------------------------------- actions
    async def _forward(self, service: str, data: dict[str, Any]) -> None:
        """Pass a call through to the base media player."""
        await self.hass.services.async_call(
            "media_player",
            service,
            {"entity_id": self._base, **data},
            blocking=True,
            context=self._context,
        )

    async def _dispatch(
        self,
        service: str,
        run_vars: dict[str, Any] | None = None,
        base_data: dict[str, Any] | None = None,
        fallback: Any = None,
    ) -> None:
        """Run your script, else forward to base player, else fall back."""
        script = self._scripts.get(service)
        if script is not None:
            await script.async_run(run_variables=run_vars or {}, context=self._context)
        elif self._base:
            await self._forward(service, base_data or {})
        elif fallback is not None:
            await fallback()
        else:
            _LOGGER.debug("%s: no action configured for %s", self.entity_id, service)

    async def async_turn_on(self) -> None:
        await self._dispatch("turn_on")

    async def async_turn_off(self) -> None:
        await self._dispatch("turn_off")

    async def async_toggle(self) -> None:
        await self._dispatch("toggle", fallback=super().async_toggle)

    async def async_media_play(self) -> None:
        await self._dispatch("media_play")

    async def async_media_pause(self) -> None:
        await self._dispatch("media_pause")

    async def async_media_stop(self) -> None:
        await self._dispatch("media_stop")

    async def async_media_play_pause(self) -> None:
        await self._dispatch("media_play_pause", fallback=super().async_media_play_pause)

    async def async_media_next_track(self) -> None:
        await self._dispatch("media_next_track")

    async def async_media_previous_track(self) -> None:
        await self._dispatch("media_previous_track")

    async def async_media_seek(self, position: float) -> None:
        await self._dispatch(
            "media_seek",
            {"position": position, "seek_position": position},
            {"seek_position": position},
        )

    async def async_set_volume_level(self, volume: float) -> None:
        await self._dispatch(
            "volume_set",
            {"volume": volume, "volume_level": volume},
            {"volume_level": volume},
        )

    async def async_mute_volume(self, mute: bool) -> None:
        await self._dispatch(
            "volume_mute",
            {"mute": mute, "is_volume_muted": mute},
            {"is_volume_muted": mute},
        )

    async def async_volume_up(self) -> None:
        await self._dispatch("volume_up", fallback=super().async_volume_up)

    async def async_volume_down(self) -> None:
        await self._dispatch("volume_down", fallback=super().async_volume_down)

    async def async_set_repeat(self, repeat: RepeatMode) -> None:
        value = str(repeat.value if hasattr(repeat, "value") else repeat)
        await self._dispatch("repeat_set", {"repeat": value}, {"repeat": value})

    async def async_set_shuffle(self, shuffle: bool) -> None:
        await self._dispatch("shuffle_set", {"shuffle": shuffle}, {"shuffle": shuffle})

    async def async_clear_playlist(self) -> None:
        await self._dispatch("clear_playlist")

    async def async_play_media(self, media_type: str, media_id: str, **kwargs: Any) -> None:
        extras = {
            k: v for k, v in kwargs.items() if k in ("announce", "enqueue", "extra")
        }
        await self._dispatch(
            "play_media",
            {"media_type": media_type, "media_id": media_id, **extras},
            {"media_content_type": media_type, "media_content_id": media_id, **extras},
        )

    async def async_join_players(self, group_members: list[str]) -> None:
        await self._dispatch(
            "join", {"group_members": group_members}, {"group_members": group_members}
        )

    async def async_unjoin_player(self) -> None:
        await self._dispatch("unjoin")

    async def async_select_source(self, source: str) -> None:
        script = self._source_scripts.get(source)
        if script is not None:
            await script.async_run(
                run_variables={"source": source}, context=self._context
            )
        elif self._base:
            await self._forward("select_source", {"source": source})

    async def async_select_sound_mode(self, sound_mode: str) -> None:
        script = self._sound_scripts.get(sound_mode)
        if script is not None:
            await script.async_run(
                run_variables={"sound_mode": sound_mode, "source": sound_mode},
                context=self._context,
            )
        elif self._base:
            await self._forward("select_sound_mode", {"sound_mode": sound_mode})

    # ------------------------------------------------------- browse + search
    def _delegate(self, entity_id: str | None) -> MediaPlayerEntity:
        component = self.hass.data.get("media_player")
        entity = component.get_entity(entity_id) if component and entity_id else None
        if entity is None:
            raise HomeAssistantError(f"Media player {entity_id} is not available")
        return entity

    async def async_browse_media(
        self, media_content_type: str | None = None, media_content_id: str | None = None
    ):
        if not self._browse_target:
            return await super().async_browse_media(media_content_type, media_content_id)
        return await self._delegate(self._browse_target).async_browse_media(
            media_content_type, media_content_id
        )

    async def async_search_media(self, query):
        if not self._search_target:
            raise NotImplementedError
        return await self._delegate(self._search_target).async_search_media(query)
