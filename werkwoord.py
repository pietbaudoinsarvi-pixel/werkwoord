"""WERKWOORD prototype v0.3: regels 1-6.

v0.1 (Codex): tijden, gebiedende wijs, bijzinnen, eenmalige zodra.
v0.2 (Claude): lidwoorden en naamvallen (regel 4), gesprekken, elkaar en zich (regel 5).
v0.3 (Codex): acteurs, eigenaarschap en verzoekwachtrij (regel 6).

Usage: python werkwoord.py program.ww
"""
from __future__ import annotations

import argparse
from collections import deque
from contextlib import contextmanager
import ast
from dataclasses import dataclass, field
import itertools
import re
from pathlib import Path


class WerkwoordFout(Exception):
    pass


class _NogNiet(Exception):
    """Intern: een bijzin probeerde een onberekende toekomst te lezen."""


# Early small lexicon; unknown verbs receive regular -de/-te and imperative stem
IRREGULAR = {
    'lopen': ('loop', 'liep'),
    'groeien': ('groei', 'groeide'),
    'tellen': ('tel', 'telde'),
    'schrijven': ('schrijf', 'schreef'),
    'antwoorden': ('antwoord', 'antwoordde'),
    'vragen': ('vraag', 'vroeg'),
    'springen': ('spring', 'sprong'),
    'rennen': ('ren', 'rende'),
    'pingen': ('ping', 'pingde'),
    'pongen': ('pong', 'pongde'),
}


def forms(infinitive: str) -> tuple[str, str]:
    if infinitive in IRREGULAR:
        return IRREGULAR[infinitive]
    if not infinitive.endswith('en'):
        raise WerkwoordFout(f'Geen infinitief: {infinitive}')
    stem = infinitive[:-2]
    # Intended as a tiny lexicon, not a complete Dutch conjugator.
    return stem, stem + ('te' if stem[-1:] in 'tkfschp' else 'de')


@dataclass(eq=False)
class Cell:
    """Een toestandscel. Namen verwijzen naar cellen; een alias deelt de cel (regel 4)."""
    current: object = None
    previous: object = None
    history: list[object] = field(default_factory=list)
    lazy: str | None = None
    calculating: bool = False
    effect: list[tuple[int, str]] | None = None
    owner: str | None = None       # None = code uit regels 1-5; anders ik/jij/wij
    verb: str | None = None


SUBJECT = r'((?:ik|jij|wij)\s+\w+|\w+)'
EVENT = re.compile(rf'{SUBJECT}\s+(?:niet\s+)?(?:veranderd|verandert)\s+is')


@dataclass(eq=False)
class Listener:
    id: int
    condition: str
    action: object            # str (gebiedende wijs) of list[(indent, regel)] (blok)
    before: bool = False
    repeat: bool = False      # regel 5d: 'herhaalt zich'
    actor: str | None = None  # registrerende actor, ook bij triggers uit een andere actor

    @property
    def is_event(self) -> bool:
        return bool(EVENT.fullmatch(self.condition))


class Werkwoord:
    def __init__(self, max_steps=10000, purist=False):
        self.cells: dict[str, Cell] = {}
        self.commands: dict[str, str] = {}
        self.pasts: dict[str, str] = {}
        self.output: list[str] = []
        self.steps = 0
        self.max_steps = max_steps
        self.listeners: list[Listener] = []
        self.parked: list[Listener] = []
        self.events: deque[Listener] = deque()
        self.ids = itertools.count(1)
        self.in_gesprek = False
        self.fired: set[int] = set()
        self.pure = False
        self.purist = purist
        self.actor_cells: dict[tuple[str, str], Cell] = {}
        self.actor_forms: dict[tuple[str, str], str] = {}
        self.actor_pasts: dict[tuple[str, str], str] = {}
        self.current_actor: str | None = None
        self.mailbox: deque[tuple[str, Cell]] = deque()  # verzoeken, FIFO
        self.conversation_ids = itertools.count(1)
        self.conversation_id: int | None = None
        self.turn_log: list[tuple[int, str | None, str]] = []

    # ---------- regel 6: persoon / actor ----------

    @staticmethod
    def present(actor: str, name: str) -> str:
        """Kleine, expliciete vervoeger: ik loop, jij loopt, wij lopen."""
        stem, _ = forms(name)
        if actor == 'ik':
            return stem
        if actor == 'jij':
            return stem if stem.endswith('t') else stem + 't'
        if actor == 'wij':
            return name
        raise WerkwoordFout(f'Onbekende persoon: {actor}')

    @staticmethod
    def past_form(actor: str, name: str) -> str:
        _, past = forms(name)
        if actor != 'wij':
            return past
        # Mini-lexicon: zwakke verleden tijd + n; sterke + en.
        return past + ('n' if past.endswith(('de', 'te')) else 'en')

    @contextmanager
    def as_actor(self, actor: str | None):
        previous = self.current_actor
        self.current_actor = actor
        try:
            yield
        finally:
            self.current_actor = previous

    def register_actor(self, actor: str, verb: str) -> Cell:
        key = (actor, verb)
        if key in self.actor_cells:
            return self.actor_cells[key]
        cell = Cell(owner=actor, verb=verb)
        present = self.present(actor, verb)
        past = self.past_form(actor, verb)
        if (actor, present) in self.actor_forms or (actor, past) in self.actor_pasts:
            raise WerkwoordFout(f'W006 dubbelzinnige vervoeging bij {actor} {verb}')
        self.actor_forms[(actor, present)] = verb
        self.actor_pasts[(actor, past)] = verb
        self.actor_cells[key] = cell
        return cell

    def actor_cell(self, actor: str, conjugated: str, create=False) -> Cell:
        name = self.actor_forms.get((actor, conjugated))
        if name is None and create and actor == 'wij' and conjugated.endswith('en'):
            name = conjugated
        if name is None and create and actor in ('ik', 'jij'):
            # Een bekende persoonsvorm van een andere persoon mag niet worden
            # hergeïnterpreteerd als stam van een verzonnen onbekend werkwoord.
            # Zo is "ik telt" fout Nederlands, geen "ik" van "telten".
            for known in IRREGULAR:
                other = 'jij' if actor == 'ik' else 'ik'
                if self.present(other, known) == conjugated and self.present(actor, known) != conjugated:
                    raise WerkwoordFout(f'W006 {actor} {conjugated} is een foutieve persoonsvorm van {known}')
            # Infinitieven worden niet stilzwijgend geraden: onregelmatige vormen
            # moeten al in het lexicon staan; reguliere stammen worden eenduidig gecontroleerd.
            possibilities = [word for word in IRREGULAR if self.present(actor, word) == conjugated]
            if not possibilities:
                possible = conjugated + ('en' if actor == 'ik' else 'en')
                possibilities = [word for word in (possible, conjugated[:-1] + 'en')
                                 if word.endswith('en') and self.present(actor, word) == conjugated]
            if len(set(possibilities)) == 1:
                name = possibilities[0]
        if name is None:
            raise WerkwoordFout(f'W006 geen bekende vervoeging voor {actor} {conjugated}')
        key = (actor, name)
        if key not in self.actor_cells:
            if not create:
                raise WerkwoordFout(f'Onbekende persoonsvorm: {actor} {conjugated}')
            self.register_actor(actor, name)
        return self.actor_cells[key]

    def actor_value(self, actor: str, conjugated: str):
        if (actor, conjugated) in self.actor_pasts:
            verb = self.actor_pasts[(actor, conjugated)]
            return self.actor_cells[(actor, verb)].previous
        return self.value_cell(self.actor_cell(actor, conjugated))

    def resolve_subject(self, subject: str, create=False) -> Cell:
        match = re.fullmatch(r'(ik|jij|wij)\s+(\w+)', subject)
        if match:
            actor, conj = match.groups()
            if create and (actor, conj) in self.actor_pasts:
                raise WerkwoordFout(f'Verleden tijd {actor} {conj} is alleen-lezen')
            return self.actor_cell(actor, conj, create=create)
        if create and subject not in self.cells:
            if self.current_actor is not None:
                raise WerkwoordFout(f'W006 {self.current_actor} moet een expliciete persoonsvorm gebruiken: {subject}')
            return self.register(subject)
        return self.cell_of(subject)

    def ensure_can_write(self, cell: Cell, subject: str):
        if self.current_actor is not None and cell.owner != self.current_actor:
            raise WerkwoordFout(f'W006 {self.current_actor} mag {subject} niet wijzigen; eigenaar is {cell.owner or "onbenoemd"}')

    def assign_subject(self, subject: str, val):
        cell = self.resolve_subject(subject, create=True)
        self.ensure_can_write(cell, subject)
        self.assign_cell(cell, val)

    def target_by_command(self, command: str, recipient: str | None = None) -> Cell:
        # Bij meerdere eigenaars is een ongekwalificeerd verzoek dubbelzinnig.
        candidates = []
        if command in self.commands:
            candidates.append(self.cells[self.commands[command]])
        candidates.extend(cell for (actor, verb), cell in self.actor_cells.items()
                          if self.present(actor, verb) == command or forms(verb)[0] == command)
        candidates = list(dict.fromkeys(candidates))
        if recipient is not None:
            candidates = [cell for cell in candidates if cell.owner == recipient]
        if len(candidates) != 1:
            raise WerkwoordFout(f'W006 verzoek {command}! heeft {len(candidates)} mogelijke ontvangers; specificeer de eigenaar')
        return candidates[0]

    def request(self, sender: str, command: str, recipient: str | None = None):
        if self.current_actor is not None and self.current_actor != sender:
            raise WerkwoordFout(f'W006 {self.current_actor} kan geen verzoek namens {sender} sturen')
        target = self.target_by_command(command, recipient)
        if target.owner is None:
            raise WerkwoordFout(f'W006 {command}! heeft geen actoreigenaar')
        self.mailbox.append((sender, target))

    def wait_for(self, actor: str):
        # v0.3 implementeert een globale join: ook transitieve verzoeken worden afgewacht.
        # Zo kan een actor niet na de barrier nog een ander actor-effect laten uitvoeren.
        while self.mailbox:
            sender, cell = self.mailbox.popleft()
            if self.conversation_id is None:
                self.conversation_id = next(self.conversation_ids)
            self.turn_log.append((self.conversation_id, cell.owner, f'verzoek van {sender}'))
            with self.as_actor(cell.owner):
                self.invoke_effect(cell)
            self.end_sentence()
        # Geen verzoeken meer: alle ontvangers (inclusief 'actor') zijn klaar.

    def strict_condition(self, condition: str):
        if self.purist and re.search(r'\bverandert\s+is\b', condition):
            raise WerkwoordFout('W003 "verandert is" is fout Nederlands; gebruik "veranderd is"')

    # ---------- namen en cellen ----------

    def register(self, name: str, cell: Cell | None = None):
        imperative, past = forms(name)
        for mapping, form in ((self.commands, imperative), (self.pasts, past)):
            if form in mapping and mapping[form] != name:
                raise WerkwoordFout(f'Vervoeging {form} is dubbelzinnig')
            mapping[form] = name
        if cell is not None:
            self.cells[name] = cell
        else:
            self.cells.setdefault(name, Cell(verb=name))
        return self.cells[name]

    def cell_of(self, name: str) -> Cell:
        if re.fullmatch(r'(ik|jij|wij)\s+\w+', name):
            return self.resolve_subject(name)
        if name in self.cells:
            return self.cells[name]
        if name in self.pasts:
            return self.cells[self.pasts[name]]
        raise WerkwoordFout(f'Onbekend werkwoord: {name}')

    def value(self, name: str):
        if name.startswith('__persoon__'):
            actor, conjugation = name[len('__persoon__'):].split('__', 1)
            return self.actor_value(actor, conjugation)
        if name.startswith('__des__'):                       # regel 4: genitief
            return list(self.cell_of(name[7:]).history)
        if name in self.cells:
            return self.value_cell(self.cells[name])
        if name in self.pasts:
            return self.cells[self.pasts[name]].previous
        raise WerkwoordFout(f'Onbekend werkwoord: {name}')

    def value_cell(self, cell: Cell):
        if cell.lazy is not None:
            if self.pure:
                raise _NogNiet()
            if cell.calculating:
                raise WerkwoordFout(f'Circulaire toekomst: zal {cell.verb}')
            cell.calculating = True
            try:
                result = self.eval_expr(cell.lazy)
            finally:
                cell.calculating = False
            # Een lazy forceren is een mutatie, onder de eigenaar van de cel.
            self.ensure_can_write(cell, cell.verb or '?')
            cell.lazy = None
            self.assign_cell(cell, result)
        return cell.current

    def assign(self, name: str, val):
        self.assign_subject(name, val)

    def assign_cell(self, cell: Cell, val):
        old = cell.current
        cell.previous = cell.current
        cell.current = val
        cell.lazy = None
        cell.history.append(val)
        self.in_gesprek = True                               # regel 5a: een gesprek opent
        if self.conversation_id is None:
            self.conversation_id = next(self.conversation_ids)
        self.notify(cell, old, val)

    # ---------- regel 3 + 5: luisteraars en gesprekken ----------

    def notify(self, cell: Cell, old, new):
        retained = []
        for listener in self.listeners:
            after = self.observe(listener.condition, (cell, old, new))
            if after and (listener.is_event or not listener.before):
                self.events.append(listener)                 # eenmalig: verbruikt
            else:
                listener.before = False if listener.is_event else after
                retained.append(listener)
        self.listeners = retained

    def observe(self, condition: str, event=None) -> bool:
        """Bijzin evalueren zonder bijwerkingen: een onberekende zal telt als onwaar."""
        was, self.pure = self.pure, True
        try:
            return self.predicate(condition, event)
        except _NogNiet:
            return False
        finally:
            self.pure = was

    def listen(self, condition: str, action, repeat=False, actor=None):
        self.strict_condition(condition)
        listener = Listener(next(self.ids), condition, action, repeat=repeat,
                            actor=self.current_actor if actor is None else actor)
        if self.in_gesprek:
            self.parked.append(listener)                     # regel 5b: wacht tot het gesprek voorbij is
        else:
            self.activate(listener)
        return listener

    def activate(self, listener: Listener):
        listener.before = False if listener.is_event else self.observe(listener.condition)
        self.listeners.append(listener)

    def end_sentence(self):
        """Na elke zin op het hoogste niveau: het gesprek uitspelen, in beurten (FIFO)."""
        while self.events:
            listener = self.events.popleft()
            if listener.id in self.fired:                    # invariant (Codex): één keer per gesprek
                raise WerkwoordFout(f'Interne fout: luisteraar {listener.id} twee keer in één gesprek')
            self.fired.add(listener.id)
            self.step()
            self.in_gesprek = True
            self.turn_log.append((self.conversation_id or 0, listener.actor, f'zodra #{listener.id}'))
            with self.as_actor(listener.actor):
                self.perform(listener)
                if listener.repeat:                          # regel 5d: zich herhalen, met een nieuw ID
                    self.listen(listener.condition, listener.action, repeat=True, actor=listener.actor)
        self.in_gesprek = False
        self.fired.clear()
        parked, self.parked = self.parked, []
        for listener in parked:
            self.activate(listener)
        self.conversation_id = None

    def perform(self, listener: Listener):
        if isinstance(listener.action, list):
            for _, line in listener.action:
                self.execute(line)
        elif listener.action == 'schrijf':
            match = re.match(SUBJECT + r'\s+', listener.condition)
            if not match:
                raise WerkwoordFout(f'Geen onderwerp in bijzin: {listener.condition}')
            self.output.append(str(self.value_cell(self.resolve_subject(match.group(1)))))
        else:
            self.imperative(listener.action)

    # ---------- uitdrukkingen ----------

    @staticmethod
    def articles(expr: str) -> str:
        """Regel 4 in uitdrukkingen: 'des Xs' -> geschiedenis; 'het X' en 'de X' lezen de waarde."""
        parts = re.split(r'("[^"]*")', expr)
        for i in range(0, len(parts), 2):
            p = re.sub(r'\bdes\s+(\w+?)s\b', r'__des__\1', parts[i])
            parts[i] = re.sub(r'\b(?:het|de)\s+(?=\w)', '', p)
        return ''.join(parts)

    def personal_expressions(self, expr: str) -> str:
        parts = re.split(r'("[^"\\]*(?:\\.[^"\\]*)*")', expr)
        for i in range(0, len(parts), 2):
            def replace_person(m):
                actor, conjugated = m.groups()
                if ((actor, conjugated) not in self.actor_pasts):
                    self.actor_cell(actor, conjugated)  # valideren bij de compiler
                return f'__persoon__{actor}__{conjugated}'
            parts[i] = re.sub(r'\b(ik|jij|wij)\s+(\w+)\b', replace_person, parts[i])
        return ''.join(parts)

    def eval_expr(self, expr: str):
        expr = self.personal_expressions(self.articles(expr))
        try:
            tree = ast.parse(expr, mode='eval')
        except SyntaxError as e:
            raise WerkwoordFout(f'Ongeldige uitdrukking: {expr}') from e

        def walk(node):
            if isinstance(node, ast.Expression): return walk(node.body)
            if isinstance(node, ast.Constant) and type(node.value) in (int, float, str, bool): return node.value
            if isinstance(node, ast.Name): return self.value(node.id)
            if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub): return -walk(node.operand)
            if isinstance(node, ast.BinOp):
                a, b = walk(node.left), walk(node.right)
                if isinstance(node.op, ast.Add): return a + b
                if isinstance(node.op, ast.Sub): return a - b
                if isinstance(node.op, ast.Mult): return a * b
                if isinstance(node.op, ast.Div): return a / b
            raise WerkwoordFout(f'Niet ondersteunde expressie: {expr}')
        return walk(tree)

    def predicate(self, condition: str, event=None) -> bool:
        # A deliberately limited, explicit parser for Dutch subordinate predicates.
        condition = condition.strip()
        m = re.fullmatch(SUBJECT + r'\s+(niet\s+)?(onder|boven)\s+(nul|\-?\d+)\s+ligt', condition)
        if m:
            subject, neg, op, number = m.groups()
            rhs = 0 if number == 'nul' else int(number)
            val = self.value_cell(self.resolve_subject(subject))
            ans = val < rhs if op == 'onder' else val > rhs
            return not ans if neg else ans
        m = re.fullmatch(SUBJECT + r'\s+(niet\s+)?(nul|\-?\d+)\s+is', condition)
        if m:
            subject, neg, number = m.groups()
            rhs = 0 if number == 'nul' else int(number)
            ans = self.value_cell(self.resolve_subject(subject)) == rhs
            return not ans if neg else ans
        self.strict_condition(condition)
        m = re.fullmatch(SUBJECT + r'\s+(niet\s+)?(?:veranderd|verandert)\s+is', condition)
        if m:
            # v0.2: een gebeurtenis, geen toestand. Alleen waar tijdens de toewijzing aan deze cel.
            subject, neg = m.groups()
            cell = self.resolve_subject(subject)
            ans = event is not None and event[0] is cell and event[1] != event[2]
            return not ans if neg else ans
        raise WerkwoordFout(f'Niet ondersteunde bijzin: {condition}')

    def step(self):
        self.steps += 1
        if self.steps > self.max_steps:
            raise WerkwoordFout(f'Uitvoeringslimiet ({self.max_steps}) overschreden')

    # ---------- zinnen ----------

    def execute(self, line: str):
        self.step()
        # Regel 6: berichten en persoonsvormen.
        if m := re.fullmatch(r'wacht totdat (ik|jij|wij) klaar (ben|bent|zijn)', line):
            who, verb = m.groups()
            if dict(ik='ben', jij='bent', wij='zijn')[who] != verb:
                raise WerkwoordFout(f'W006 {who} klaar {verb} is geen correcte persoonsvorm')
            self.wait_for(who)
            return
        if m := re.fullmatch(r'(ik|jij|wij)\s+verzoek(?:t|en)?\s+(?:(ik|jij|wij)\s+)?(\w+)!', line):
            sender, recipient, command = m.groups()
            actual = line.split()[1]
            if actual != dict(ik='verzoek', jij='verzoekt', wij='verzoeken')[sender]:
                raise WerkwoordFout(f'W006 {sender} {actual} is geen correcte persoonsvorm')
            self.request(sender, command, recipient)
            return
        if m := re.fullmatch(r'(ik|jij|wij)\s+(\w+)\s*=\s*(.+)', line):
            actor, conjugated, expr = m.groups()
            self.assign_subject(f'{actor} {conjugated}', self.eval_expr(expr))
            return
        if m := re.fullmatch(r'(ik|jij|wij)\s+(\w+)!', line):
            actor, conjugated = m.groups()
            target = self.actor_cell(actor, conjugated)
            if self.current_actor is not None and self.current_actor != actor:
                raise WerkwoordFout(f'W006 {self.current_actor} kan niet rechtstreeks {actor} laten handelen')
            with self.as_actor(actor):
                self.invoke_effect(target)
            return
        if m := re.fullmatch(r'zal\s+(\w+)\s*=\s*(.+)', line):
            name, expr = m.groups()
            self.register(name)
            self.ensure_can_write(self.cells[name], name)
            self.cells[name].lazy = expr
            return
        if m := re.fullmatch(r'de\s+(\w+)\s*=\s*(\w+)', line):        # regel 4: alias
            new, target = m.groups()
            if new in self.cells:
                raise WerkwoordFout(f'W004 {new} is al gebonden; een lidwoord bindt alleen een nieuwe naam')
            if target not in self.cells:
                raise WerkwoordFout(f'Onbekend werkwoord: {target}')
            self.register(new, self.cells[target])
            return
        if m := re.fullmatch(r'het\s+(\w+)\s*=\s*(.+)', line):        # regel 4: momentopname
            new, expr = m.groups()
            if new in self.cells:
                raise WerkwoordFout(f'W004 {new} is al gebonden; een lidwoord bindt alleen een nieuwe naam')
            val = self.eval_expr(expr)
            cell = self.register(new, Cell())
            self.ensure_can_write(cell, new)
            self.assign_cell(cell, val)
            return
        if m := re.fullmatch(r'geef\s+den\s+(\w+)\s+(.+)', line):      # regel 4: datief
            name, expr = m.groups()
            if name not in self.cells:
                raise WerkwoordFout(f'Onbekende ontvanger: den {name}')
            self.assign(name, self.eval_expr(expr))
            return
        if m := re.fullmatch(r'(\w+)\s*=\s*(.+)', line):
            name, expr = m.groups()
            if name in self.pasts:
                raise WerkwoordFout(f'Verleden tijd {name} is alleen-lezen')
            self.assign(name, self.eval_expr(expr))
            return
        if m := re.fullmatch(r'schrijven\((.*)\)', line):
            args = [x.strip() for x in m.group(1).split(',') if x.strip()]
            self.output.append(' '.join(str(self.eval_expr(x)) for x in args))
            return
        if m := re.fullmatch(r'(\w+)!,\s*zodra\s+(.+)', line):
            command, condition = m.groups()
            self.listen(condition, command)
            return
        if m := re.fullmatch(r'(\w+)!,\s*(als|tenzij|omdat)\s+(.+)', line):
            command, conjunction, condition = m.groups()
            valid = self.predicate(condition)
            if conjunction == 'omdat' and not valid:
                raise WerkwoordFout(f'Assertie mislukt: {condition}')
            if conjunction == 'als' and not valid or conjunction == 'tenzij' and valid:
                return
            self.imperative(command)
            return
        if m := re.fullmatch(r'(\w+)!', line):
            self.imperative(m.group(1))
            return
        raise WerkwoordFout(f'Onbekende instructie: {line}')

    def invoke_effect(self, cell: Cell):
        if cell.effect is None:
            self.output.append(str(self.value_cell(cell)))
            return
        for _, line in cell.effect:
            self.execute(line)

    def imperative(self, word: str):
        if word in self.commands:
            cell = self.cells[self.commands[word]]
        else:
            cell = self.target_by_command(word, self.current_actor)
        if self.current_actor is not None and cell.owner != self.current_actor:
            raise WerkwoordFout(f'W006 {self.current_actor} kan geen {cell.owner or "onbenoemd"}-effect direct uitvoeren; gebruik verzoek')
        # Vanuit buitenaf mag een effect expliciet worden gestart; actor krijgt dan zijn eigen beurt.
        with self.as_actor(cell.owner):
            self.invoke_effect(cell)

    def run(self, source: str) -> list[str]:
        lines: list[tuple[int, str]] = []
        for number, original in enumerate(source.splitlines(), 1):
            stripped = original.split('//', 1)[0].rstrip()
            if not stripped.strip(): continue
            indent = len(stripped) - len(stripped.lstrip())
            lines.append((indent, stripped.strip()))
        i = 0
        while i < len(lines):
            indent, line = lines[i]
            if indent:
                raise WerkwoordFout(f'Onverwachte inspringing bij: {line}')
            if line.endswith(':'):
                i += 1
                block = []
                while i < len(lines) and lines[i][0] > indent:
                    block.append(lines[i]); i += 1
                if not block: raise WerkwoordFout(f'Leeg blok: {line}')
                self.block(line, block)
            else:
                self.execute(line)
                i += 1
            self.end_sentence()
        return self.output

    def validate_actor_effect(self, actor: str, block):
        """Statische W006-controle, ook als het effect nooit wordt uitgevoerd."""
        for _, line in block:
            if m := re.fullmatch(r'(ik|jij|wij)\s+\w+\s*=\s*.+', line):
                target_actor = m.group(1)
                if target_actor != actor:
                    raise WerkwoordFout(f'W006 {actor} mag niet aan {target_actor} toewijzen: {line}')
                continue
            if m := re.fullmatch(r'(?:zal\s+)?(\w+)\s*=\s*.+', line):
                raise WerkwoordFout(f'W006 {actor} moet een expliciete persoonsvorm gebruiken: {line}')
            if m := re.fullmatch(r'geef\s+den\s+(\w+)\s+.+', line):
                cell = self.cell_of(m.group(1))
                self.ensure_actor_can_write(actor, cell, line)
            if m := re.fullmatch(r'(ik|jij|wij)\s+\w+!', line):
                if m.group(1) != actor:
                    raise WerkwoordFout(f'W006 {actor} kan niet rechtstreeks als {m.group(1)} handelen')
            if m := re.fullmatch(r'(ik|jij|wij)\s+verzoek(?:t|en)?\s+.+', line):
                if m.group(1) != actor:
                    raise WerkwoordFout(f'W006 {actor} kan niet namens {m.group(1)} verzoeken')

    def ensure_actor_can_write(self, actor: str, cell: Cell, statement: str):
        if cell.owner != actor:
            raise WerkwoordFout(f'W006 {actor} kan de cel van {cell.owner or "onbenoemd"} niet wijzigen: {statement}')

    def block(self, head: str, block):
        if head == 'tegelijk:':
            for _, line in block:
                if not re.fullmatch(r'(ik|jij|wij)\s+verzoek(?:t|en)?\s+.+', line):
                    raise WerkwoordFout(f'W006 tegelijk staat alleen verzoeken toe: {line}')
            for _, line in block:
                self.execute(line)  # Verzoeken worden geparkeerd tot 'wacht totdat'.
            return
        if m := re.fullmatch(r'betekent\s+(ik|jij|wij)\s+(\w+):', head):
            actor, conjugated = m.groups()
            self.validate_actor_effect(actor, block)
            self.actor_cell(actor, conjugated, create=True).effect = block
            return
        if m := re.fullmatch(r'(ik|jij|wij)\s+luister,\s*zodra\s+(.+):', head):
            actor, condition = m.groups()
            self.validate_actor_effect(actor, block)
            self.listen(condition, block, actor=actor)
            return
        if m := re.fullmatch(r'betekent\s+(\w+):', head):
            self.register(m.group(1)).effect = block
            return
        if m := re.fullmatch(r'(\w+)\s+en\s+(\w+)\s+beïnvloeden\s+elkaar:', head):   # regel 5c
            pair = {self.cell_of(m.group(1)), self.cell_of(m.group(2))}
            for _, line in block:
                z = re.fullmatch(r'\w+!,\s*zodra\s+(\w+)\s.+', line)
                if not z or self.cell_of(z.group(1)) not in pair:
                    raise WerkwoordFout(f'W010 binnen "elkaar" hoort elke zin een zodra over {m.group(1)} of {m.group(2)} te zijn: {line}')
                self.execute(line)
            return
        if m := re.fullmatch(r'(\w+)\s+herhaalt\s+zich,\s*zodra\s+(.+):', head):     # regel 5d
            self.cell_of(m.group(1))
            self.listen(m.group(2), block, repeat=True)
            return
        raise WerkwoordFout(f'Onbekend blok: {head}')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('program', type=Path)
    args = p.parse_args()
    machine = Werkwoord()
    try:
        print('\n'.join(machine.run(args.program.read_text(encoding='utf8'))))
    except WerkwoordFout as e:
        p.error(str(e))

if __name__ == '__main__':
    main()
