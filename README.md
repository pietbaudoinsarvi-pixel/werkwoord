# WERKWOORD — prototype regels 1–3

Start: `python werkwoord.py aftellen.ww`, `python werkwoord.py fibonacci.ww`, of `python -m unittest -v`.

Ondersteund: werkwoorden als toestandsvariabelen, vorige waarde via verleden tijd, `zal <werkwoord> = <expressie>` als memoized lazy expressie, `betekent <werkwoord>:` effecten, gebiedende wijs, `als`, `tenzij`, `omdat`, en eenmalige `zodra`-listeners op toestandswisselingen. `schrijf!, zodra X ...` print de actuele waarde van X.

Beperkingen: slechts een kleine vervoegingstabel en subset van Nederlandse bijzinnen; geen algemene Nederlandse parser. Regels 4–7, actorisolatie en het volledige gespreksmodel zijn nog niet geïmplementeerd. `zodra` heeft een eenvoudige FIFO-wachtrij en is nog niet equivalent aan de volledige regel-5-semantiek. De stappenlimiet is een veiligheidsgrens en geen semantische garantie van terminatie.
