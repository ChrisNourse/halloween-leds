# Software setup and operation

For first-time Wi-Fi provisioning, follow [the README setup steps](../README.md#connect-to-your-wi-fi).

## Open the control desk

Requires Python 3 and desktop Chrome or Edge for Web Serial. Other browsers can control the board over Wi-Fi.

```sh
npm start
```

Open **http://localhost:8000**, choose **Connect USB**, and select the Feather's **data interface**. This firmware exposes one serial control port. Do not leave another terminal connected to it.

The ESP32-S2 has insufficient USB endpoints for two serial interfaces plus the disk. Normal operation exposes the console and control data ports, with the disk hidden so OTA can own the filesystem even with USB attached. The console is usually the first port; select the second port for browser controls. [Adafruit documents the endpoint limit](https://learn.adafruit.com/customizing-usb-devices-in-circuitpython?view=all).

To expose CIRCUITPY for a later USB installation, run `uv run scripts/device.py usb-drive` (add `--port /dev/...` to select the console explicitly). This pauses the show, creates a recovery marker, and resets into console-plus-disk mode. Run `install` once the drive appears, then reset. The installer removes that marker after verification to restore normal operation. Debugging is also available through the Wi-Fi console at `http://BOARD_IP:8080/cp/serial/`.

## Control over Wi-Fi

Open **http://halloween.local** from a phone or computer on the same Wi-Fi network. The board serves the entire site and the controls connect automatically. No Mac server or USB data connection is needed. OTA remains separate at **http://BOARD_IP:8080**, using the address reported by the connected control desk. If mDNS is unavailable, open **http://BOARD_IP** for the lighting controls. Guest isolation, separate subnets and blocked multicast can prevent discovery; direct IP also requires network reachability. See [connection troubleshooting](../README.md#will-halloweenlocal-work-automatically).

The lighting controls are available to devices on your local network while the board is awake. The OTA file service requires the separate device password. Keep the board on your trusted home network.

Wi-Fi requests allow **15 seconds** for a response. One failed status check gets another chance; after two consecutive failures the page disables controls and reconnects automatically, waiting three seconds between attempts. A fixed connection bar appears at the bottom while the connection is delayed or lost, so **Reconnect now** is available without scrolling to the header. It can restart an in-progress connection attempt immediately. A deliberate **Disconnect Wi-Fi** stops automatic retries; the bottom **Connect lights** button remains available. Reconnection reads current board settings and never replays unconfirmed commands.

The controls stay disabled until a real board connection is established. There is no LED simulation or preview panel.

Choose one **Pattern**: embers, cauldron, passing ghost, chase, breathing, or steady. It stays selected until changed, including across power cycles. The former rotating show is removed; old saved `show` selections migrate to embers. **Color** is independent of motion: every pattern uses either your single color or your gradient, with the pattern controlling intensity and movement.

Choose **Gradient** to edit two to six color stops across the full chain, from LED 1 (0%) to LED 16 (100%). Select a numbered stop, then change its color. Drag an intermediate numbered handle directly along the gradient to position it; mouse and touch are supported. The displayed percentage updates while dragging, and one change is saved when you release. Arrow keys move a focused handle by 1%, Shift + arrow by 10%, and Home/End move it to its allowed limits. Escape cancels a drag. Stops cannot cross their neighbors; endpoints stay at 0% and 100%. **Add color stop** inserts a color into the largest gap; intermediate stops can be removed. Each stop except the last has a **Fade midpoint to next stop** slider: it places the equal mix of the two colors earlier or later in that interval. Black stops can create dark regions and fades to black. The gradient strip is a static color editor, not a simulated light show.

**Slow breathing** uses the gradient over time instead of spreading colors along the sticks. All 16 LEDs share one intended color, moving smoothly from the first stop through intermediate stops to the last, then back again. Stop positions and fade midpoints shape those transitions. At 1× speed the full color round trip lasts about 15.7 seconds, with four brightness breaths; speed scales both together. Other patterns retain the spatial gradient.

Breathing keeps fractional RGB values through interpolation, the breathing envelope and scheduled brightness scaling, rounding only when writing to the LEDs. Ordered dithering distributes fractional output over the 16 LEDs and successive frames, reducing strip-wide steps at low brightness. Individual output channels can differ by one PWM count during this process. The breathing loop uses an 8 ms idle interval instead of 20 ms; actual frame rate also includes processing and network work. The physical LEDs still have 8-bit channels, so visual smoothness should be checked on the installed lights.

Pattern, single color, color source and gradient changes save automatically to NVM after each committed change. Brightness supports the full **0–100%** range; there is no 25% cap. Speed, brightness, schedule and blackout can be saved with **Save startup settings**. An automatic pattern/color save also captures those settings as currently selected. Blackout is saved if active when saving, but an automatic timer wake or the next daytime-to-nighttime transition clears it so the next scheduled lighting can run.

The color picker sends live updates on its `input` events, for both single colors and the selected gradient stop. Fast input is coalesced to the latest color, with a 150 ms throttle and one color request queued/in flight at a time. These updates change the physical lights in RAM without writing each movement to flash. Finishing the selection (`change`, or leaving the picker) sends the final color with persistence enabled. Delayed responses preserve the newest picker value. Disconnection drops unfinished color work rather than replaying it after reconnecting.

Speed changes motion without changing the selected pattern or palette. Blackout blanks output while motion time continues. Startup defaults live in [firmware/config.py](../firmware/config.py); valid saved NVM settings override defaults.

### Automatic schedule

Set `LATITUDE`, `LONGITUDE` and `TIMEZONE` in your private `settings.toml`, install it and restart. Coordinates are quoted decimal degrees, with south/west negative. The example and omitted settings default to **San Francisco: 37.7749, -122.4194, America/Los_Angeles**. Change all three values for another location. `TIMEZONE` is an IANA name used only for browser display, including daylight saving time; coordinates determine the UTC solar events. Deriving a timezone from coordinates would require a separate geographic timezone database or service. A partially specified coordinate pair, blank values or invalid coordinates leave manual lighting available without automatic sleep, even if a saved setting enables the schedule. The browser shows a setup message. An invalid timezone produces a display warning without changing the UTC solar calculations.

At high latitudes, dates near polar day or polar night can lack a daily sunrise/sunset cycle. When any date in the five-day calculation window lacks that cycle, the board keeps manual lighting and network controls available, disables automatic dimming and sleep, and retries the schedule each UTC day. The browser reports this fallback. Turning off **Sunset schedule** bypasses solar calculations entirely.

With a daily solar cycle, valid coordinates and **Sunset schedule** enabled:

| Solar time | Behavior |
| --- | --- |
| Sunset | Start lighting at the selected brightness limit |
| Sunset to two hours later | Fade continuously to 50% of that limit |
| Two to four hours after sunset | Continue fading to 25% of that limit |
| Rest of the night | Hold 25% of that limit |
| Sunrise | Black out both sticks and enter daytime deep sleep |
| Next sunset | Wake automatically and run again |

Like the reference Mando code, this has no separate midnight cutoff. At the default 15% limit, the final nighttime output is 3.75% of full output. The website shows the actual scheduled output separately from the selected limit.

Sunrise/sunset are calculated locally from [NOAA's approximate solar equations](https://gml.noaa.gov/grad/solcalc/solareqns.PDF), rather than fetched daily. The calculation matched the sunrise-sunset API used by Mando within about 20 seconds for San Francisco on 2026-10-20; atmospheric and location differences can shift the physical event. Solar scheduling uses UTC and therefore follows seasonal changes without hard-coded local UTC offsets. The browser applies the named timezone for display, including daylight saving time.

The RTC synchronizes using NTP (`time.cloudflare.com`, UDP 123) when Wi-Fi is available, then refreshes every six hours while awake. After a complete power loss it needs time synchronization before automatic lighting starts. A valid RTC lets the schedule continue without Wi-Fi. If the clock remains unknown, automatic output stays off; after the startup grace period the board sleeps ten minutes before retrying. Manual mode can run without a clock.

**Daytime sleep turns off Wi-Fi, the website, OTA and the heartbeat.** Press BOOT to wake the board for access and temporarily run daytime lighting until the next sunrise. A cold boot provides a 60-second access window before daytime sleep. Long sleeps use up to two-hour checkpoints, matching Mando's timer safeguard, and return to sleep during daylight. A USB connection enumerated by a computer keeps the board awake for development and disk installation; a USB wall supply does not. Turn off **Sunset schedule** for manual operation without automatic sleep or dimming; save that setting if it should survive reset.

The board must remain powered for timed wake. Blank pixels and deep sleep reduce consumption but do not physically cut power to the external sticks or boost converter; those can still draw idle current. The schedule is deployed and NTP is verified on hardware; sunrise/sunset sleep and wake transitions remain to be observed.

### Onboard status light

The Feather's own NeoPixel stays dim, independent of the external sticks (maximum channel value 8 out of 255).

| Animation | Board state |
| --- | --- |
| Amber at startup | Application starting |
| Slow amber breathing | Running without a Wi-Fi address |
| Green double heartbeat | Running with Wi-Fi connected |
| Blue double heartbeat | Connected, external output off (blackout, schedule, or clock wait) |
| Off during daytime deep sleep | Waiting for the next sunset; BOOT wakes for access |
| CircuitPython's dim native indicator | App paused for REPL/OTA, or a runtime fault |

The status heartbeat continues when external brightness is zero. Native status output is also dimmed at boot. Its system patterns during OTA/faults are controlled by CircuitPython.

## First USB installation

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) on the computer for the device tool. It handles the host Python version and dependencies. `npm install` is only needed for browser development tests.

1. Install the stable [CircuitPython runtime for this exact board](https://circuitpython.org/board/adafruit_feather_esp32s2/). A factory Arduino sketch will not expose CIRCUITPY. Hold BOOT, tap RESET, release BOOT to enter the ROM bootloader if needed. Back up existing firmware/files before flashing.
2. Copy [settings.example.toml](../settings.example.toml) to a **private location**, fill in the 2.4 GHz Wi-Fi network and a unique OTA password. Keep credentials out of Git. Existing board settings can be preserved by omitting `--settings`.
3. Install the application, substituting the private settings path:

```sh
uv run scripts/device.py inspect
uv run scripts/device.py install --settings /private/path/settings.toml
```

The default drive is `/Volumes/CIRCUITPY`; pass `--volume /path/to/CIRCUITPY` elsewhere. The installer checks `boot_out.txt` for the correct board, backs up replaced files outside the repo, copies the application with `code.py` last, and verifies each file byte for byte. Tap RESET or reconnect afterward: `boot.py` USB descriptor changes need a physical reset.

## OTA application updates

Uses CircuitPython's built-in, authenticated [web workflow](https://docs.circuitpython.org/en/latest/docs/workflows.html#web), on **port 8080**. It starts from `settings.toml` independently of the lighting app. It remains available during manual blackout, but daytime deep sleep turns it off. Press BOOT to wake the board before updating during the day.

The control desk shows the device's OTA address under **Connection & OTA updates** after connecting USB. You can also check it through the Wi-Fi console or temporarily enabled USB console:

```python
import wifi
print(wifi.radio.ipv4_address)
```

Alternatively use your router or CircuitPython mDNS discovery. Use the device-specific hostname returned by discovery; its format varies between runtime versions. Do not assume the shared `circuitpython.local` points to this board if other CircuitPython devices are present.

In normal operation the USB disk is hidden, so OTA works with USB power/data connected. If you are in USB installation mode, finish `install` and reset first. Then run:

```sh
uv run scripts/device.py ota --url http://BOARD_IP:8080
```

On a machine without saved credentials, the updater prompts for the board's OTA password. It checks board identity, backs up every affected file, opens the authenticated web REPL, stops the show, disables autoreload, and remounts normally for writing. USB write protection is preserved. If the disk is visible in installation mode, reset into normal operation before retrying.

The updater uploads the firmware modules and the three website files in `/www`, with `code.py` last. Every upload is downloaded again for an exact readback comparison. On a caught upload failure it restores and verifies the old files, then restarts. If restoration fails, it leaves the application stopped and prints the backup directory. After a process crash or power loss, use USB and that backup to recover. This is **not an atomic dual-image updater**.

After successful verification it requests a full reset. Settings and credentials are not overwritten by OTA. Subsequent updates can omit `--url` because the address/password are saved with owner-only permissions outside Git. Backups use the same private directory. Use OTA only on a trusted LAN; CircuitPython web workflow uses HTTP Basic authentication without TLS. **CircuitPython runtime and bootloader upgrades still require USB.**

## Development and checks

```sh
npm install
npm test
npx playwright install chromium
npm run test:browser
```

Host tests exercise stable pattern selection, shared solid/gradient colors, stop interpolation and fade midpoints, atomic validation, selection persistence and save failures, 100% GRB output through the real entry point, bounded serial parsing, NTP, solar transitions, sleep/wake behavior, and OTA upload/rollback. Browser tests exercise independent pattern/color selection, stop editing and limits, rapid edits with delayed acknowledgments, full-range brightness, schedule/manual overrides, simulated USB acknowledgments, errors, keyboard behavior, and layouts at 375, 768 and 1280 pixels. They do not substitute for checking the physical lights or a live OTA update.

USB messages are newline-delimited JSON on `usb_cdc.data`. Commands are `hello`, `state`, `set` (with a `settings` object), and `save`. Responses echo the request `id`, report `ok`, and return settings or an error. The board reports status telemetry once per second using the existing `frame` event name; pixel arrays are no longer transmitted. Wi-Fi status polls run every two seconds. Commands over 1024 bytes are discarded through the next newline. See [firmware/protocol.py](../firmware/protocol.py).

`set` accepts an optional top-level boolean `persist`, defaulting to `true`. The live color picker uses `false` for temporary updates and `true` when committing the final choice; normal pattern/color autosave remains enabled by default. The same protocol works over USB and Wi-Fi.
