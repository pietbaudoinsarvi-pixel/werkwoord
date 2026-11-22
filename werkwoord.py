"""WERKWOORD prototype v0.2: regels 1-5.

v0.1 (Codex): tijden, gebiedende wijs, bijzinnen, eenmalige zodra.
v0.2 (Claude): lidwoorden en naamvallen (regel 4), gesprekken, elkaar en zich (regel 5).

Usage: python werkwoord.py program.ww
"""
from __future__ import annotations

import argparse
from collections import deque
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


EVENT = re.compile(r'(\w+)\s+(?:niet\s+)?veranderd\s+is|(\w+)\s+(?:niet\s+)?verandert\s+is')


@dataclass(eq=False)
class Listener:
    id: int
    condition: str
    action: object            # str (gebiedende wijs) of list[(indent, regel)] (blok)
    before: bool = False
    repeat: bool = False      # regel 5d: 'herhaalt zich'

    @property
    def is_event(self) -> bool:
        return bool(EVENT.fullmatch(self.condition))


class Werkwoord:
    def __init__(self, max_steps=10000):
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
            self.cells.setdefault(name, Cell())
        return self.cells[name]

    def cell_of(self, name: str) -> Cell:
        if name in self.cells:
            return self.cells[name]
        if name in self.pasts:
            return self.cells[self.pasts[name]]
        raise WerkwoordFout(f'Onbekend werkwoord: {name}')

    def value(self, name: str):
        if name.startswith('__des__'):                       # regel 4: genitief
            return list(self.cell_of(name[7:]).history)
        if name in self.cells:
            cell = self.cells[name]
            if cell.lazy is not None:
                if self.pure:                                # een bijzin forceert nooit
                    raise _NogNiet()
                if cell.calculating:
                    raise WerkwoordFout(f'Circulaire toekomst: zal {name}')
                cell.calculating = True
                try:
                    result = self.eval_expr(cell.lazy)
                finally:
                    cell.calculating = False
                cell.lazy = None
                self.assign(name, result)                    # forceren is een echte toewijzing
            return cell.current
        if name in self.pasts:
            return self.cells[self.pasts[name]].previous
        raise WerkwoordFout(f'Onbekend werkwoord: {name}')

    def assign(self, name: str, val):
        if name not in self.cells:
            self.register(name)
        self.assign_cell(self.cells[name], val)

    def assign_cell(self, cell: Cell, val):
        old = cell.current
        cell.previous = cell.current
        cell.current = val
        cell.lazy = None
        cell.history.append(val)
        self.in_gesprek = True                               # regel 5a: een gesprek opent
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

    def listen(self, condition: str, action, repeat=False):
        listener = Listener(next(self.ids), condition, action, repeat=repeat)
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
            self.perform(listener)
            if listener.repeat:                              # regel 5d: zich herhalen, met een nieuw ID
                self.listen(listener.condition, listener.action, repeat=True)
        self.in_gesprek = False
        self.fired.clear()
        parked, self.parked = self.parked, []
        for listener in parked:
            self.activate(listener)

    def perform(self, listener: Listener):
        if isinstance(listener.action, list):
            for _, line in listener.action:
                self.execute(line)
        elif listener.action == 'schrijf':
            subject = listener.condition.split()[0]
            self.output.append(str(self.value(subject)))
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

    def eval_expr(self, expr: str):
        expr = self.articles(expr)
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
        m = re.fullmatch(r'(\w+)\s+(niet\s+)?(onder|boven)\s+(nul|\-?\d+)\s+ligt', condition)
        if m:
            subject, neg, op, number = m.groups()
            rhs = 0 if number == 'nul' else int(number)
            ans = self.value(subject) < rhs if op == 'onder' else self.value(subject) > rhs
            return not ans if neg else ans
        m = re.fullmatch(r'(\w+)\s+(niet\s+)?(nul|\-?\d+)\s+is', condition)
        if m:
            subject, neg, number = m.groups()
            rhs = 0 if number == 'nul' else int(number)
            ans = self.value(subject) == rhs
            return not ans if neg else ans
        m = re.fullmatch(r'(\w+)\s+(niet\s+)?(?:veranderd|verandert)\s+is', condition)
        if m:
            # v0.2: een gebeurtenis, geen toestand. Alleen waar tijdens de toewijzing aan deze cel.
            subject, neg = m.groups()
            cell = self.cell_of(subject)
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
        if m := re.fullmatch(r'zal\s+(\w+)\s*=\s*(.+)', line):
            name, expr = m.groups()
            self.register(name)
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

    def imperative(self, word: str):
        if word not in self.commands:
            raise WerkwoordFout(f'Onbekende gebiedende wijs: {word}!')
        name = self.commands[word]
        effect = self.cells[name].effect
        if effect is None:
            self.output.append(str(self.value(name)))
            return
        for _, line in effect:
            self.execute(line)

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

    def block(self, head: str, block):
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
