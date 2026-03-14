# GNOME 50 Build TODOs

## In Progress / Triggered
- [ ] `mutter` (Build 10223926): Re-triggered with `pipewire >= 1.6.0`.
- [ ] `gtk4` (Build 10223927): Needed for `libadwaita`.
- [ ] `pango` (Build 10223946): Re-triggered with `docbook-utils`.
- [ ] `gnome-settings-daemon` (Build 10223948): Re-triggered with `libnotify >= 0.8.7`.
- [ ] `gnome-control-center` (Build 10223949): Re-triggered with `gsettings-desktop-schemas >= 50.alpha`.
- [ ] `gexiv2` (Build 10223965): New dependency for `nautilus`.
- [ ] `gi-docgen` (Build 10223966): Local SRPM to fix `BuildSystem` failure.
- [ ] `xdg-desktop-portal-gnome` (Build 10223967): Re-triggered after `gsettings-desktop-schemas` success.
- [ ] `glycin` (Build 10223790): Still running.

## Pending (Blocked)
- [ ] `gnome-shell`: Waiting for `mutter-devel`.
- [ ] `nautilus`: Waiting for `gexiv2-devel`.
- [ ] `libadwaita`: Waiting for `gtk4 >= 4.21.1`.

## Actions to Take
1. Monitor Build 10223926 (`mutter`). Once succeeded, build `gnome-shell`.
2. Monitor Build 10223965 (`gexiv2`). Once succeeded, build `nautilus`.
3. Monitor Build 10223927 (`gtk4`). Once succeeded, build `libadwaita`.
4. Final check of all session components.
