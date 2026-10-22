# Project status

**v0.9.2 — experimental. Hardware qualification is in progress.**

The firmware, browser controls, editable CAD, four print meshes and illustrated build guide are available for builders who are comfortable testing an unfinished hardware design. Version v1.0.0 is reserved for the qualified build.

## Available and checked

- Browser controls for patterns, gradients, brightness, speed, blackout and solar scheduling, plus USB installation and OTA application updates.
- 58 host tests and 23 browser tests passed, covering runtime behavior, settings, polar-season fallback, HTTP host validation and browser interactions.
- Four print meshes pass digital checks for watertightness, consistent winding and a single connected solid. All fit a 180 × 180 mm bed. See [mesh validation](mechanical/validation/print-meshes.json).
- Editable native CAD, matching print files and a 24-page [build guide](docs/Halloween-LEDs-Build-Guide.pdf). See [mechanical validation](mechanical/validation/mechanical-handoff.json).
- [Reciprocal licenses](LICENSE.md) for software, hardware and original documentation, with [third-party notices and credits](THIRD_PARTY_NOTICES.md).

## Hardware work in progress

These results have not yet been recorded:

- Correct the reported boost input from Feather 3V to BAT and verify the revised wiring.
- Trial the printed assembly, including USB access, connectors and harness routing. Digital mesh checks do not establish physical fit; no fresh slicing run has been recorded.
- Measure current, boost output under load, enclosed temperature, battery cutoff and runtime at stated brightness levels.
- Observe actual sunset/sunrise operation on the installed hardware.
- Complete the connector family, mating parts, numbered harness pinout, wire sizes and routing photographs in the [electrical checklist](docs/wiring.md#electrical-details-to-complete).

The base CAD retains a geometry-reference warning on its floor-root fillet. The TPS61023 boost alternative is an untested candidate. The enclosure has no weatherproof qualification.

## Release history

Version-specific changes are recorded in [GitHub Releases](https://github.com/ChrisNourse/halloween-leds/releases). Each release draft captures this status from its tag so that later updates do not change the recorded limitations of an older release. See [the release process](docs/releasing.md).
