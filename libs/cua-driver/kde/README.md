# cua-driver on KDE Plasma

This branch fixes cua-driver on KDE Plasma Wayland. Measured on KWin 6.6.6, two
outputs at scale 1.25, layout `us altgr-intl`.

| What | Official 0.38.0 | This branch |
|---|---|---|
| Screenshot of a covered window | Refused | Works |
| `list_windows` positions | Wrong | Match KWin |
| `bring_to_front` | Refused | Works, past focus stealing prevention |
| Desktop screenshot | Not comparable: frames disagree | 317 ms, every output |
| Desktop click at a screenshot pixel | Frames disagree on a scaled output | Exact |
| Desktop typing with AltGr characters | Loses them | Exact |
| Desktop typing with no key on the layout | Silently lost | Refused, nothing typed |
| Typing into an element after an emoji | Loses the last character on Qt | Exact |
| Desktop typing with Caps Lock on or another active layout | Wrong text, reports success | Exact, or refused |
| Raw input aimed at a window, on every tool | Refused | Refused, nothing delivered |

## Install

```sh
git clone --depth 1 -b kde-setup https://github.com/astrovm/cua
cd cua
libs/cua-driver/kde/install.sh              # build in a container, then install
libs/cua-driver/kde/install.sh --uninstall  # back to the official build
```

It needs podman. The official build stays on disk. MCP configs that run
`~/.local/bin/cua-driver` pick this build up when the agent restarts, and they
need `CUA_DRIVER_RS_ENABLE_WAYLAND=1`.

`cua-driver update --apply` replaces this build. Run `install.sh` again after it.

## Check it after any update

```sh
libs/cua-driver/kde/acceptance/run.sh        # 18 checks on the real desktop
libs/cua-driver/kde/acceptance/run.sh speed  # latency through MCP
```

## Known limits

- Raw input goes to the focused window. Bring the window to the front, then send
  desktop input. Upstream refuses to bind raw input to a window on KWin because
  focus can change between the check and the input.
- Qt dropdown items can't be picked over accessibility. Click the dropdown, then
  press `Down` and `Return`.

## Testing without your desktop

`acceptance/container/run.sh` runs real KWin, portals and libei in a container, so nothing touches your screen, including the portal's consent dialogs. Point it at a build:

```sh
acceptance/container/run.sh altgr branch path/to/cua-driver XKB_VARIANT=altgr-intl
acceptance/container/run.sh frame branch path/to/cua-driver OUTPUT_SCALE=1.25
acceptance/container/run.sh capture branch path/to/cua-driver NOGRANT=1 GRANT_BIN=/bin-under-test/cua-driver
DISTRO=fedora45 acceptance/container/run.sh text branch path/to/cua-driver
acceptance/container/run.sh monitors branch path/to/cua-driver LAYOUT=two NOGRANT=1 GRANT_BIN=/bin-under-test/cua-driver
acceptance/container/run.sh x11 branch path/to/cua-driver XWAYLAND=1 OUTPUT_SCALE=1.25 XKB_VARIANT=altgr-intl NOGRANT=1 GRANT_BIN=/bin-under-test/cua-driver
CHROME_DIR=/opt/google/chrome acceptance/container/run.sh keys branch path/to/cua-driver XWAYLAND=1 XKB_VARIANT=altgr-intl NOGRANT=1 GRANT_BIN=/bin-under-test/cua-driver
```

`acceptance/container/entry.sh` runs the release installer inside that session and checks what it grants:

```sh
acceptance/container/entry.sh after path/to/cua-driver libs/cua-driver/scripts
acceptance/container/entry.sh update path/to/cua-driver libs/cua-driver/scripts
acceptance/container/entry.sh persist path/to/cua-driver libs/cua-driver/scripts
```

More modes, each on real KWin:

- `rawinput`: all 9 raw input tools aimed at a covered window must refuse.
- `layouts`, `capsfirst`, `long`, `hungx`, `nodisplay`, `texts`, `refusal`, `modlog`: desktop typing. `layouts` takes `XKB_LAYOUTS=de,us`.
- `layout`, with `LAYOUT=cfg KWINCFG=cfg-<name>.json`: output layouts, including offset, rotated and mixed scale.
- `grantprobe`, `savedeny`, `rawplus`, `rawelem`, `menu`, `popup`, `resizerace`, `scaleprobe`, `nativetest`: capture and permissions.
- `switch`, `typeswitch`: `kwin-capture` on a running daemon, and desktop typing while it changes. Any mode takes `KWIN_SWITCH=on` to set it first.
- `textbig`, `gtk3row`, `bridgefull`: accessibility text and `NO_AT_BRIDGE`. `textbig` takes `ONLYBIG=1`, `BIGTEXTS=a|b`, `ROUTE=element|setvalue` and `DELIVERY=foreground`.

`keys` types every symbol one at a time into Qt and Chrome, each on native Wayland and on Xwayland, and reads the text back. Keep it in mind when changing how characters pick keys: `us` also has `$`, `(`, `*` and `+` on media and keypad keys, and X11 apps and Chromium drop some of those.

We test on exactly three systems: the latest Kubuntu LTS (the default, Ubuntu 26.04 LTS packages), the latest Debian stable and the latest Fedora. Move a target when a new release comes out. `DISTRO=debian13` gives KWin 6.3 and `DISTRO=fedora45` gives KWin 6.8. Build the binary on the same distro. KWin 6.8 behaves differently in three ways worth knowing: it announces `kde_output_device_registry_v2` instead of `kde_output_device_v2`, `type_text` arrives through the input method instead of as key presses, and capture worked without the `.desktop` grant.
