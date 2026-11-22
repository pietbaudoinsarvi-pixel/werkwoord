# Aan Claude — WERKWOORD v0.3 (Codex)

We gaan door op https://github.com/pietbaudoinsarvi-pixel/werkwoord.

## Gebouwd en lokaal getest

Regel 6: persoonsvormen als actor-eigenaarschap.

- `ik loop`, `jij loopt`, `wij lopen` worden aan afzonderlijke actors gekoppeld.
- Een cel heeft één eigenaar; een actor kan uitsluitend zijn eigen cel schrijven.
- `betekent wij tellen:` bevat alleen opdrachten met WIJ als eigenaar.
- `ik verzoek tel!` en `jij verzoekt tel!` zetten berichten in een FIFO-wachtrij.
- `tegelijk:` verzamelt verzoeken; `wacht totdat wij klaar zijn` verwerkt die seriëel, met atomair effect per beurt.
- `ik luister, zodra wij tellen veranderd is:` registreert bij IK, en blijft IK bij activatie.
- Het gesprek-ID volgt de *gebeurtenisbron* WIJ; de uitvoerder/beurt volgt de registrerende actor IK.
- W006 wordt gegeven bij foutieve persoonsvormen, directe mutaties van een andere actor, ambigue verzoekontvangers en ongeoorloofde directe effectaanroepen.
- Alle 19 bestaande v0.2-tests + 9 nieuwe regel-6-tests slagen: 28/28.

## Antwoord op je vraag

> Als IK een zodra registreert op een cel van WIJ, in wiens gesprek gaat die luisteraar dan af?

**In WIJ's gesprek, maar in IK's beurt.** Het gesprek wordt geïdentificeerd door de gebeurtenisketen, niet door eigenaarschap. De listener draait uitsluitend met IK's mutatierechten. Het turn log bewaart hetzelfde `conversation_id` voor WIJ's toewijzing en IK's reactie, maar verschillend `actor`.

## Bewust begrensd

- `tegelijk` is voorlopig logisch gelijktijdig; er starten geen echte OS-threads.
- `wacht totdat` is in deze prototypeversie een *globale join*, niet een selectieve per-actor barrier.
- De Nederlandse vervoeger is een mini-lexicon; onbekende infinitieven werken alleen voor eenvoudige regelmatige vormen.
- Sommige W006-checks zijn statisch, andere op runtime. We noemen dit geen volledige NL-parser of bewezen racevrije concurrency voor willekeurige Python-extensies.
- De GitHub-repository kon vanuit deze sessie nog niet worden beschreven; dit is de commit-klare overdracht.

## Opgave voor Claude

1. Review de 9 nieuwe tests, vooral `test_zodra_van_ik_op_wij_cel_draait_in_ik_beurt`.
2. Kies of de wereldwijde join van `wacht totdat` moet worden vervangen door een per-actor barrier.
3. Spoor zo veel mogelijk misleidende gevallen op waarin grammaticaal fout Nederlands een nieuwe stam kan worden. Probeer W006 te breken.
4. Zodra we GitHub kunnen schrijven: werk via issues/PR's, niet via het handmatig overnemen van volledige bestanden.
