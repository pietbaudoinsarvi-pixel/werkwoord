# WERKWOORD — prototype regels 1–5

Een programmeertaal waarin Nederlandse grammatica het uitvoeringsmodel is. Ontworpen door Claude en Codex, in een gesprek dat een mens heen en weer kopieerde.

Start: `python werkwoord.py aftellen.ww`, of `python -m unittest -v`.

## Regels

| Regel | Grammatica | Betekenis |
|---|---|---|
| 1 | tegenwoordige / verleden / toekomende tijd | huidige toestand / vorige waarde / memoized lazy waarde |
| 2 | gebiedende wijs, `betekent` | effect uitvoeren |
| 3 | `als`, `tenzij`, `omdat`, `zodra` | voorwaarde, ontkenning, assertie, eenmalige luisteraar |
| 4 | `de`, `het`, `des`, `den` | alias (zelfde cel), momentopname (nieuwe cel), geschiedenis, ontvanger |
| 5 | `elkaar`, `zich` | gesprekken: eindige reactieve transacties; herhaling alleen reflexief |

## Semantiek van een gesprek (regel 5)

- Een zin op het hoogste niveau die iets toewijst, opent een gesprek. Luisteraars gaan af in beurten (FIFO), **na** de zin.
- Elke luisteraar heeft een uniek ID en gaat hooguit één keer per gesprek af.
- Een luisteraar die tijdens een gesprek wordt geregistreerd (ook via `herhaalt zich`), wordt pas actief als het gesprek voorbij is.
- Gevolg: reactieve code alleen kan nooit een eindeloos gesprek veroorzaken.

## Beslissingen in v0.2

- `veranderd is` is een **gebeurtenis**: alleen waar tijdens de toewijzing aan die cel. `verandert is` wordt nog geaccepteerd.
- Het forceren van een `zal` is een echte toewijzing en dus een gebeurtenis voor `zodra`.
- Bijzinnen van `zodra` **observeren**: ze forceren nooit een `zal`. Een onberekende toekomst telt daar als onwaar.

## Geschiedenis

- v0.1 (Codex): regels 1–3.
- v0.2 (Claude): regels 4–5, plus twee bugfixes uit v0.1. Een oude verandering gold nog als nieuwe gebeurtenis bij een toewijzing aan een andere cel, en een luisteraar die tijdens een gesprek werd geregistreerd, kon nog in datzelfde gesprek afgaan.

Nog niet geïmplementeerd: regels 6–7 (actoren, mogelijke werelden).

## v0.3 — Persoonsvorm en actoren (regel 6)

De implementatie van v0.3 bouwt op v0.2 voort. Dezelfde 19 tests blijven slagen;
9 nieuwe tests controleren de actor-eigenaarschapregels (28/28).

```werkwoord
wij tellen = 0
betekent wij tellen:
    wij tellen = wij tellen + 1
tegelijk:
    ik verzoek tel!
    jij verzoekt tel!
wacht totdat wij klaar zijn
schrijven(wij tellen)   // 2
```

De requests worden atomair in FIFO-volgorde op de WIJ-actor afgehandeld.
`tegelijk` betekent in dit prototype *logische concurrency*, niet echte OS-threads.
Een `ik luister, zodra wij tellen veranderd is:` blijft eigendom van IK,
maar reageert binnen hetzelfde gesprek als WIJ's verandering.

Run: `python werkwoord.py actoren.ww` en `python werkwoord.py actor_luisteraar.ww`.
Voor verdere implementatiedetails en reviewvragen: `CLAUDE_HANDOFF.md`.
