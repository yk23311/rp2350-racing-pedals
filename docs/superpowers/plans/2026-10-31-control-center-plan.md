# Control Center Implementation Plan

> **For agentic workers:** Execute independent core and GUI tasks in parallel with fixed interfaces below; root integrates firmware, verifies and reviews each deliverable. Use test-driven-development and executing-plans for implementation.

**Goal:** Modern desktop control center with real board telemetry, pedal/gamepad curves, button-to-gamepad/keyboard mapping, automatic serial discovery and persistent board-side settings.

**Architecture:** PySide6 desktop with a pyserial worker, pure Python display/curve models, bounded CDC requests. Pure C control profile transforms Host input before MAX pedal merge; unified versioned dual-slot storage preserves old calibration through migration. GUI is never an input mapper.

**Tech Stack:** Existing Pico SDK 2.2.0/TinyUSB/Pico-PIO-USB 0.7.2, C11; Python3.11, PySide6/Qt, pyserial.

## Global Constraints

- Existing uncommitted bridge fixes are user work: preserve them and reuse the current checkout.
- Keep native XInput+keyboard+CDC identity and MAX merge. No Steam/PC virtual input, mouse, macros, automatic flash or hardware changes.
- All extended replies fit 768 bytes and commands fit 127 characters. Do not add logs to default CDC stream.
- Board handles curves/remaps; offline GUI uses explicitly labelled demo data only.
- Keep legacy Tk GUI accessible. New Qt app is the default launcher after verification.

## Task 1: Control profile, transformations, protocol and storage

Files: new `include/control_profile.h`, `src/core/control_profile.c`, `src/core/control_console.c`, tests; modify core CMake list, console and storage. Fixed interfaces:

```c
typedef struct { uint16_t deadzone,gamma; uint8_t invert; } control_stick_t;
typedef struct { uint16_t deadzone,gamma; } control_trigger_t;
typedef struct { uint8_t kind,target; } control_binding_t;
typedef struct { control_stick_t sticks[2]; control_trigger_t triggers[2]; control_binding_t bindings[14]; } control_profile_t;
void control_defaults(control_profile_t *);
bool control_profile_valid(const control_profile_t *);
control_profile_t *control_current(void); /* lazily defaulted singleton */
void control_transform(const control_profile_t *,const xinput_pad_t *,xinput_pad_t *,uint8_t keyboard[8]);
bool control_console(pedal_t *,const char *,char out[CONSOLE_RESPONSE_SIZE]);
```

Button source/target indices 0..13 map to XInput bits `[0,1,2,3,4,5,6,7,8,9,12,13,14,15]`. Binding kind0=gamepad target index; kind1=keyboard HID usage (incl modifiersE0..E7); kind2=disabled target0. No transform side effects, mappings use original snapshot/set union. >6 keys sends HID ErrorRollOver, modifiers separate.

Commands/replies: `PROFILE` -> `OK {"sticks":[{"deadzone":0,"gamma":100,"invert":0},...],"triggers":[{"deadzone":0,"gamma":100},...],"bindings":[[kind,target],...]}`. `STICK i deadzone gamma invert`, `TRIGGER i deadzone gamma`, `BIND i kind target`; atomic validation and `pedal_reset` on successful mutation. Invalid command returns existing ERR style. Default axes identity, buttons pass through. GUI-only preset preview never mutates firmware.

- [x] Write/run failing tests for curve boundaries/radial direction, mappings/duplicates/modifiers/rollover and protocol bounds.
- [x] Implement minimal pure C functions and additive console routing; run targeted tests.
- [x] Unified HOST-only record supports old40-byte PDL1 migration and new profile+pedal record with CRC, sequence, two slots. `storage_load/save` signature unchanged, singleton profile included. Preserve baseline nonHOST behavior and reserve same8KiB.
- [x] Test new record corruption/power interruption, migration and combined persistence; run existing suite.

## Task 2: Qt widgets and desktop screens

Files: `tools/control_center.py`, `tools/control_widgets.py`, Qt tests. GUI consumes root-owned `tools/control_session.py`:

`Session(QObject)` signals `ports_changed(list)`, `snapshot(dict)`, `connected_changed(bool,str)`, `message(str,bool)`; methods `start()`, `connect_port(str)`, `disconnect_port()`, `submit(list[str])`, `close()`. Signal snapshot keys `pedal` legacy GET dict, `telemetry` optional dict, `profile` optional dict, `capabilities` dict. On connect/apply snapshot includes profile/config; polling must not overwrite unsent edits. telemetry raw/processed/output gamepads are `[buttons,LT,RT,LX,LY,RX,RY]`, state0..4, age, reports, timeouts, keys[8], blocked, keyboard_rollover; GUI labels no telemetry unsupported when absent.

- [x] Qt offscreen tests for percentage bounds, painted controls, dirty editing vs incoming polling, window layout and action command generation.
- [x] Implement dark scalable dashboard, pedals page with curves/live cursor and calibration, sticks/triggers page with radial views, fourteen button mapping rows and global Apply/Revert/SAVE state.
- [x] UI input ranges reflect contract; firmware replies refresh applied model without erasing unsent previews. Disconnect/stale values are grey with explicit labels. Demo mode is explicit.

## Task 3: Root integration, telemetry, worker and delivery

Files: `firmware/usb.c`, `main.c`, `include/bridge.h`, `src/core/bridge.c`, `tools/control_session.py`, Python models/tests, launchers, build manifest, docs.

- [x] Extend bridge report construction to apply control profile before MAX; keyboard mapping is gated by same neutral/armed/mode/Host conditions.
- [x] Add firmware commands `CAPS` and `TELEMETRY` routed through main bounded console. CAPS advertises control_center1, profile1, telemetry1, bridge1 and version; TELEMETRY returns raw/processed/current output/keyboard plus Host freshness. Old firmware ERR capabilities degrades to pedal-only GUI.
- [x] Save gating also checks physical Host buttons/triggers, not only remapped target; latest input cannot bypass SAVE by disabling a button.
- [x] Add session worker tests: identity-only serial discovery, one request at a time, 20Hz bounded polling, no command replay after reconnect, stale/unsupported state. Install pinned PySide6 dependency in .venv, preserve Tk fallback.
- [x] Run full C/Python tests and Qt screenshot visual inspection; build hostUF2 and verify manifest/hash/config boundary. Update version to0.4.0-control-center consistently.
- [x] Write stage report and HANDOFF with exact tested/pending hardware facts and upgrade/downgrade instructions. Do not claim real input/Flash/FH6 verified from demo or mocks.

## Acceptance

PC core and worker tests green, Qt screenshots show full controls at1280×800 and scaled/smaller windows, .venv launcher check passes, host firmware builds. Hardware remains user-flash gate: raw-vs-output correctness, simultaneous steering/pedals, keyboard release/faults, persistence, GUI closed operation, hotplug and game acceptance.
