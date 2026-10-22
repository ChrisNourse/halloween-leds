# Build guide source

[Open the PDF](../Halloween-LEDs-Build-Guide.pdf).

Edition: **v0.9.0 — experimental**. Hardware qualification is in progress for v1.0.0.

Build-guide presentation inspired by [CURV LAB's WR1 Chassis Build Guide](https://www.curvlab.com/guides/wr1-build). The guide uses a 720 × 405 pt landscape page, numbered operations, dotted parts/quantity labels, and gray/blue CAD illustrations. All assembly illustrations come from this project's CAD; no CURV LAB illustrations or branding are reused.

The DXFs in `assets/` are native SolidCraft view exports of the final saved assembly at `294cd1f`, captured in a separate app instance. Gray and blue geometry were exported separately with the same camera so their coordinates align. The PDF renderer converts their line entities directly to vector paths. Electronics remain simplified CAD envelopes; flexible wiring is described separately.

Install Python dependencies `reportlab` and `ezdxf`, then run:

```sh
python docs/build-guide/build_pdf.py
```

`provenance.json` records source hashes and limitations. The illustrations and four print exports match the final saved handoff. Future geometry changes require affected views and print outputs to be regenerated. Physical qualification is in progress. NeoPixel reference photographs are linked on Adafruit's website rather than reproduced here.

Original guide content is CC BY-SA 4.0; its Python generator is GPL-3.0-only and CAD view exports are CERN-OHL-S-2.0. See [license scope](../../LICENSE.md) and [third-party notices](../../THIRD_PARTY_NOTICES.md) for the embedded Adafruit pinout artwork exception.
