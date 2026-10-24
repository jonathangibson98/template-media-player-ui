"""Constants for Template Media Player (UI)."""
from __future__ import annotations

DOMAIN = "template_media_player_ui"

CONF_DEVICE_CLASS = "device_class"
CONF_ICON = "icon"
CONF_BASE = "base_media_player_entity_id"
CONF_BROWSE = "browse_media_entity_id"
CONF_SEARCH = "search_media_entity_id"
CONF_GLOBAL_TEMPLATE = "global_template"
CONF_VARIABLES = "variables"
CONF_STATE = "state"
CONF_AVAILABILITY = "availability"
CONF_ATTRIBUTES = "attributes"
CONF_CUSTOM_ATTRIBUTES = "custom_attributes"
CONF_SERVICE_SCRIPTS = "service_scripts"
CONF_SOURCE_SCRIPTS = "source_scripts"
CONF_SOUND_MODE_SCRIPTS = "sound_mode_scripts"

# Attribute templates, split into two UI pages
ATTRIBUTES_MEDIA = [
    "media_title",
    "media_artist",
    "media_album_name",
    "media_album_artist",
    "media_series_title",
    "media_season",
    "media_episode",
    "media_channel",
    "media_playlist",
    "media_track",
    "media_content_id",
    "media_content_type",
    "media_duration",
    "media_position",
    "media_position_updated_at",
    "media_image_url",
    "media_image_remotely_accessible",
    "entity_picture",
    "app_id",
    "app_name",
    "media_content_rating",
    "media_summary",
]
ATTRIBUTES_PLAYER = [
    "volume_level",
    "is_volume_muted",
    "source",
    "sound_mode",
    "shuffle",
    "repeat",
    "group_members",
]
ALL_ATTRIBUTES = ATTRIBUTES_MEDIA + ATTRIBUTES_PLAYER

# Type coercion for rendered template output
INT_ATTRIBUTES = {"media_duration", "media_position", "media_track"}
FLOAT_ATTRIBUTES = {"volume_level"}
BOOL_ATTRIBUTES = {"is_volume_muted", "shuffle", "media_image_remotely_accessible"}
# These have no native MediaPlayerEntity property, so they show up as plain state attributes
EXTRA_ONLY_ATTRIBUTES = {"media_content_rating", "media_summary"}

# Action (script) pages, split into three UI pages
SERVICES_PLAYBACK = [
    "media_play",
    "media_pause",
    "media_stop",
    "media_play_pause",
    "media_next_track",
    "media_previous_track",
    "media_seek",
]
SERVICES_POWER = [
    "turn_on",
    "turn_off",
    "toggle",
    "volume_up",
    "volume_down",
    "volume_mute",
    "volume_set",
]
SERVICES_OTHER = [
    "repeat_set",
    "shuffle_set",
    "play_media",
    "clear_playlist",
    "join",
    "unjoin",
]
ALL_SERVICES = SERVICES_PLAYBACK + SERVICES_POWER + SERVICES_OTHER
