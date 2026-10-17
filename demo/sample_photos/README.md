# Sample shop photos for testing photo proof

Generated test labels (fictional brands). Upload them in the **Shop** tab to a request for a
"65W USB-C PD charger". Expected results with a live Gemini model:

| File | Expected |
| --- | --- |
| `1_charger_65w_correct.jpg` | Photo matches the request (65W, USB-C, PD, CE/FCC read) |
| `2_charger_45w_wrong_wattage.jpg` | Conflict: 45W is below the required 65W |
| `3_fake_brand_appel.jpg` | Conflict: authenticity concern (misspelled brand and text) |
| `4_mixer_grinder_wrong_item.jpg` | Conflict: photo shows a mixer grinder, not a charger |
| `5_cable_not_charger.jpg` | Conflict: photo shows a cable, not a charger |
