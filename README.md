# Template Media Player (UI)

A UI-configurable rewrite of the idea behind
[EuleMitKeule/template-media-player](https://github.com/EuleMitKeule/template-media-player)
(MIT licensed, credit to the original author for the concept and option names).
Create template media players from **Settings -> Devices & services** and edit
them any time with the **Configure** button. No YAML files needed.

## Install
1. Copy the `template_media_player_ui` folder into `<your HA config>/custom_components/`
   (the same folder that has `configuration.yaml`).
2. Restart Home Assistant.
3. Settings -> Devices & services -> Add integration -> "Template Media Player (UI)".

## Edit
Settings -> Devices & services -> Template Media Player (UI) -> your player -> gear icon (Configure).
Pick a section, edit, Submit. It saves and reloads instantly. Hit **Save & close** when done.

## Example: one remote-control entity combining a TV and a soundbar
General page:
- Base media player: `media_player.tv`
- Global template: `{% set soundbar = 'media_player.soundbar' %}`
- Availability: `{{ not is_state('media_player.tv', 'unavailable') }}`

Attributes -> Player page:
- volume_level: `{{ state_attr(soundbar, 'volume_level') }}`

Actions -> Power & volume page, volume_set (paste in the YAML editor):
```yaml
- action: media_player.volume_set
  data:
    entity_id: media_player.soundbar
    volume_level: "{{ volume }}"
```

Sources -> Add -> name `Plex`:
```yaml
- action: media_player.select_source
  data:
    entity_id: media_player.tv
    source: Plex
```

## How inheritance works
If a **base media player** is set, anything you leave empty is taken from it
(state, attributes, source list) and any action you don't define is forwarded to it.

## Notes / differences from the original
- Built from the original's README + option list; not a line-for-line port.
- Browse/search: instead of scripts, you point at another media player to borrow
  its media browser/search. `browse_media_sources` / `media_source` are not ported.
- Everything else (state, availability, global_template, variables, attributes,
  service scripts, source scripts, sound mode scripts, base player) is supported.
