# Bill of materials

Quantities are for one light. The original build used Amazon stainless screw and dowel assortment packs. Any suitable pack containing the sizes below will do; the Amazon links are searches, not specific required products. The build guide explains where each fastener goes.

| Qty | Part | Purchase / reference | Notes |
| ---: | --- | --- | --- |
| 1 | ESP32-S2 Feather | [Adafruit 5000](https://www.adafruit.com/product/5000) | Exact board used in CAD |
| 2 | 8-pixel RGB NeoPixel stick | [Adafruit 1426](https://www.adafruit.com/product/1426) | RGB, not RGBW |
| 1 | 3.7 V, 2000 mAh LiPo | [Adafruit 2011](https://www.adafruit.com/product/2011) | Verify JST polarity on replacements |
| 1 | TMF002 boost converter | [Teyleten Robot B0B4TB9QNY](https://www.amazon.com/dp/B0B4TB9QNY) | Installed board required desoldering two voltage-selection resistors to change 12 V to 5 V; see below |
| 1 mating set | Detachable LED JST connector / pigtail | **TBD: exact family, contacts and purchase link** | Installed to let the top plate unplug; [harness details pending](docs/wiring.md#removable-top-plate) |
| 6 | M3 × 8 stainless socket-head screw | [Amazon assortment packs](https://www.amazon.com/s?k=stainless+M3+socket+head+screw+assortment) | 4 case + 2 LED frame |
| 6 | M2 × 8 stainless button-head screw | [Amazon assortment packs](https://www.amazon.com/s?k=stainless+M2+button+head+screw+assortment) | 4 LED + 2 Feather; check heads clear the recesses |
| 6 | M3 heat-set insert | [Ruthex RX-M3×5.7](https://www.ruthex.de/products/ruthex-gewindeeinsatz-m3-100-stuck-rx-m3x5-7-messing-gewindebuchsen) | 4 base + 2 faceplate; do not substitute shorter Voron inserts |
| 6 | M2 heat-set insert | [Ruthex RX-M2×4](https://www.ruthex.de/collections/gewindeeinsatze/products/ruthex-gewindeeinsatz-m2-70-stuck-rx-m2x4-messing-gewindebuchsen) | 4 LED retainer + 2 base |
| 2 | 2 × 6 mm stainless dowel | [Amazon assortment packs](https://www.amazon.com/s?k=stainless+2mm+dowel+pin+assortment) | Feather PCB location |
| As needed | PETG, flexible insulated wire, solder, heat-shrink | Use materials appropriate to your printer and measured circuit load | Cut wire to the actual route with service slack |
| 1 | 1 mm soft nonconductive battery pad | Cut to fit without obstructing lead routing | Do not compress the pouch |
| 1 | USB-C data cable | Match the actual recessed connector opening | Charge and program the board |

Use the listed screw lengths and head styles, and check that the heads fit the printed recesses. No particular screw or dowel brand is required.

## Boost converter: required modification

The installed TMF002 arrived configured for **12 V**. The builder **desoldered two voltage-selection resistors to change it to 5 V**. This is part of preparing the listed module, not just a meter check. With USB and battery disconnected, identify the selection components using instructions for your exact board revision before removing them. Their reference designators and positions have not been documented here. Do not remove arbitrary resistors. Follow the [wiring and first-power checks](docs/wiring.md) before connecting the LEDs.

### TPS61023 candidate: untested

The builder has a TPS61023-based converter that may work, but it has **not been tested in this project**. Its exact board model, output setting, dimensions and usable output current are not yet documented. Specifications for another TPS61023 breakout should not be assumed to apply to this board.

The TMF002 remains the documented build component. Before substituting the TPS61023 board, verify its output voltage, mounting and lid clearance, and test output stability and temperature with all sixteen LEDs at the intended brightness across the battery discharge range. The current CAD models a 22 × 11 × 3.6 mm converter; any replacement needs a fit check.

## Printed and editable parts

Print one of each enclosure part. The four STLs were regenerated from the final saved CAD and checked for watertightness and print orientation. Physical assembly verification remains pending.

| Qty | Part | Editable model | Printable output |
| ---: | --- | --- | --- |
| 1 | Base | [SolidCraft](mechanical/cad/base.solidcraft) | [STL](mechanical/exports/stl/base.stl) |
| 1 | Faceplate | [SolidCraft](mechanical/cad/faceplate.solidcraft) | [STL](mechanical/exports/stl/faceplate.stl) |
| 1 | LED retainer | [SolidCraft](mechanical/cad/led-retainer.solidcraft) | [STL](mechanical/exports/stl/led-retainer.stl) |
| 1 | Feather retainer | [SolidCraft](mechanical/cad/feather-retainer.solidcraft) | [STL](mechanical/exports/stl/feather-retainer.stl) |

Keep the [linked assembly](mechanical/cad/enclosure.solidcraft), sibling parts and [hardware sources](mechanical/cad/hardware/) together for editing.

## Recommended electrical additions

The recorded installed enclosure contains no separate level shifter or bulk capacitor. For robust 5 V signaling, [Adafruit recommends](https://learn.adafruit.com/adafruit-neopixel-uberguide/best-practices) an appropriate logic level shifter, a 300–500 Ω data resistor and a 500–1000 µF supply capacitor. These parts require an insulated mounting arrangement and a new clearance check.

| Qty | Part | Purchase / specification |
| ---: | --- | --- |
| 1 | 74AHCT125 | [Adafruit 1787](https://www.adafruit.com/product/1787); verify package and pinout |
| 1 | 300–500 Ω resistor | 330 Ω or 470 Ω series data resistor |
| 1 | 500–1000 µF capacitor | At least 6.3 V rating; observe polarity |
| 1 | 0.1 µF ceramic capacitor | Local level-shifter bypass; [TI datasheet](https://www.ti.com/lit/ds/symlink/sn74ahct125.pdf) |
