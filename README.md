# Template Media Player (UI)

Build your own media player in Home Assistant by **pointing and clicking**.
No YAML files and no templates to write. You pick things from lists and the
integration does the rest.

Based on the idea behind
[EuleMitKeule/template-media-player](https://github.com/EuleMitKeule/template-media-player)
(MIT licensed, credit to the original author for the concept and option names).

## Install
1. Copy the `template_media_player_ui` folder into `<your HA config>/custom_components/`
   (the same folder that has `configuration.yaml`), or add this repository to HACS as a custom repository.
2. Restart Home Assistant.
3. Settings -> Devices & services -> Add integration -> "Template Media Player (UI)".

## Set it up
Settings -> Devices & services -> Template Media Player (UI) -> your player -> gear icon (Configure).
Everything saves as you go. Choose **Save & close** when you're done.

| Menu item | What you do there |
|---|---|
| **Basics** | Pick a device class, icon and an optional base media player. |
| **State** | Pick an entity and say which of its states mean *playing*, *paused*, *off*... |
| **Availability** | Pick an entity; the player is unavailable when it is (or when it's not in the states you choose). |
| **What's playing** / **Player info** | Pick an item (title, artist, volume...) and choose where its value comes from: an entity's state, an entity's attribute (picked from a list), a fixed value, or "yes while an entity is in these states". |
| **Extra attributes** | Add your own attributes the same way. |
| **Buttons** (play, pause, volume...) | Pick a button and choose what happens: pass it to another media player, control a device (switch, button, light, script, scene, remote...) from a list of actions, wait a moment, and chain as many steps as you like. |
| **Sources** / **Sound modes** | Pick names (suggested from your base player) and choose what happens when each one is selected, using the same step builder. |
| **Advanced** | The original template and YAML pages, if you ever want them. Anything set there still shows up in the simple menus. |

A ✓ in a list means that item is already set up.

## Example: one remote-control entity combining a TV and a soundbar
1. **Basics**: Base media player = `media_player.tv`.
2. **Player info -> Volume level**: *Use one attribute of an entity* -> `media_player.soundbar` -> `volume_level`.
3. **Buttons: power and volume -> Set volume**: *Pass it on to another media player* -> `media_player.soundbar`.
4. **Sources -> Add or change a source -> Plex**: *Pass it on to another media player* -> `media_player.tv`, with the name on that player set to `Plex` if it's called something different there.

## How inheritance works
If a **base media player** is set, anything you leave empty is taken from it
(state, attributes, source list) and any button you don't set up is passed on to it.

## Notes / differences from the original
- Built from the original's README + option list; not a line-for-line port.
- Browse/search: instead of scripts, you point at another media player to borrow
  its media browser/search. `browse_media_sources` / `media_source` are not ported.
- Everything else (state, availability, global template, variables, attributes,
  service scripts, source scripts, sound mode scripts, base player) is supported.

## Help
Questions or problems? Open an issue at
<https://github.com/jonathangibson98/template-media-player-ui/issues>.
