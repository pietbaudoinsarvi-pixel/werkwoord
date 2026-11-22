"""WERKWOORD prototype: rules 1-3 (tense, imperative, subordinate clauses).

Usage: python werkwoord.py program.ww
"""
from __future__ import annotations

import argparse
from collections import deque
import ast
from dataclasses import dataclass, field
import re
from pathlib import Path


class WerkwoordFout(Exception):
    pass


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
}


def forms(infinitive: str) -> tuple[str, str]:
    if infinitive in IRREGULAR:
        return IRREGULAR[infinitive]
    if not infinitive.endswith('en'):
        raise WerkwoordFout(f'Geen infinitief: {infinitive}')
    stem = infinitive[:-2]
    # Intended as a tiny lexicon, not a complete Dutch conjugator.
    return stem, stem + ('te' if stem[-1:] in 'tkfschp' else 'de')


@dataclass
class Cell:
    current: object = None
    previous: object = None
    history: list[object] = field(default_factory=list)
    lazy: str | None = None
    calculating: bool = False


class Werkwoord:
    def __init__(self, max_steps=10000):
        self.cells: dict[str, Cell] = {}
        self.effects: dict[str, list[tuple[int, str]]] = {}
        self.commands: dict[str, str] = {}
        self.pasts: dict[str, str] = {}
        self.output: list[str] = []
        self.steps = 0
        self.max_steps = max_steps
        self.listeners: list[tuple[str, str, bool]] = []
        self.events = deque()
        self.processing_events = False

    def register(self, name: str):
        imperative, past = forms(name)
        for mapping, form in ((self.commands, imperative), (self.pasts, past)):
            if form in mapping and mapping[form] != name:
                raise WerkwoordFout(f'Vervoeging {form} is dubbelzinnig')
            mapping[form] = name
        self.cells.setdefault(name, Cell())

    def value(self, name: str):
        if name in self.cells:
            cell = self.cells[name]
            if cell.lazy is not None:
                if cell.calculating:
                    raise WerkwoordFout(f'Circulaire toekomst: zal {name}')
                cell.calculating = True
                try:
                    result = self.eval_expr(cell.lazy)
                finally:
                    cell.calculating = False
                cell.lazy = None
                self.assign(name, result)
            return cell.current
        if name in self.pasts:
            return self.cells[self.pasts[name]].previous
        raise WerkwoordFout(f'Onbekend werkwoord: {name}')

    def assign(self, name: str, val):
        if name not in self.cells:
            self.register(name)
        cell = self.cells[name]
        cell.previous = cell.current
        cell.current = val
        cell.lazy = None
        cell.history.append(val)
        # Rule 3: a listener fires on a false-to-true transition (or a change event).
        retained = []
        for command, condition, before in self.listeners:
            after = self.predicate(condition)
            event = bool(re.fullmatch(r'\w+\s+(?:niet\s+)?verandert\s+is', condition))
            if after and (event or not before):
                self.events.append((command, condition))
            else:
                retained.append((command, condition, after))
        self.listeners = retained
        if not self.processing_events:
            self.processing_events = True
            try:
                while self.events:
                    command, condition = self.events.popleft()
                    self.step()
                    if command == 'schrijf':
                        subject = condition.split()[0]
                        self.output.append(str(self.value(subject)))
                    else:
                        self.imperative(command)
            finally:
                self.processing_events = False

    def eval_expr(self, expr: str):
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

    def predicate(self, condition: str) -> bool:
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
        m = re.fullmatch(r'(\w+)\s+(niet\s+)?verandert\s+is', condition)
        if m:
            subject, neg = m.groups()
            if subject not in self.cells: raise WerkwoordFout(f'Onbekend werkwoord: {subject}')
            cell = self.cells[subject]
            ans = len(cell.history) >= 2 and cell.current != cell.previous
            return not ans if neg else ans
        raise WerkwoordFout(f'Niet ondersteunde bijzin: {condition}')

    def step(self):
        self.steps += 1
        if self.steps > self.max_steps:
            raise WerkwoordFout(f'Uitvoeringslimiet ({self.max_steps}) overschreden')

    def execute(self, line: str):
        self.step()
        if m := re.fullmatch(r'zal\s+(\w+)\s*=\s*(.+)', line):
            name, expr = m.groups()
            self.register(name)
            self.cells[name].lazy = expr
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
            previous = self.predicate(condition)
            self.listeners.append((command, condition, previous))
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
        effect = self.effects.get(name)
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
            if m := re.fullmatch(r'betekent\s+(\w+):', line):
                name = m.group(1)
                self.register(name)
                i += 1
                block = []
                while i < len(lines) and lines[i][0] > indent:
                    block.append(lines[i]); i += 1
                if not block: raise WerkwoordFout(f'Leeg betekent-blok: {name}')
                self.effects[name] = block
                continue
            self.execute(line)
            i += 1
        return self.output


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
