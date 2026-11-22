"""v0.3.1 (Claude): regressietests uit de review van regel 6.

Elke test hier was in v0.3 een geaccepteerd programma dat geaccepteerd had moeten worden
geweigerd, of andersom.
"""
import unittest
from werkwoord import Werkwoord, WerkwoordFout


def run(src):
    return Werkwoord().run(src)


class VermomdeVormen(unittest.TestCase):
    def test_infinitief_als_ik_vorm(self):
        with self.assertRaisesRegex(WerkwoordFout, 'W006.*infinitief'):
            run('ik tellen = 5')

    def test_onbekende_infinitief_als_ik_vorm(self):
        with self.assertRaisesRegex(WerkwoordFout, 'W006.*infinitief'):
            run('ik kloppen = 5')

    def test_verleden_tijd_als_nieuwe_stam(self):
        with self.assertRaisesRegex(WerkwoordFout, 'W006.*verleden tijd van tellen'):
            run('ik telde = 5')

    def test_onbekende_verleden_tijd_is_dubbelzinnig(self):
        with self.assertRaisesRegex(WerkwoordFout, 'W006.*dubbelzinnig'):
            run('ik werkte = 5')

    def test_wij_verleden_tijd_als_infinitief(self):
        with self.assertRaisesRegex(WerkwoordFout, 'W006.*verleden tijd van tellen'):
            run('wij telden = 5')

    def test_onbekende_wij_verleden_tijd_is_dubbelzinnig(self):
        with self.assertRaisesRegex(WerkwoordFout, 'W006.*dubbelzinnig'):
            run('wij werkten = 5')

    def test_gewone_onbekende_werkwoorden_blijven_werken(self):
        self.assertEqual(run('ik voel = 1\nik reken = 2\njij werkt = 3\nwij werken = 4\n'
                             'schrijven(ik voel, ik reken, jij werkt, wij werken)'), ['1 2 3 4'])


class Luisteren(unittest.TestCase):
    def test_wij_luister_is_fout(self):
        with self.assertRaisesRegex(WerkwoordFout, 'W006.*wij luisteren'):
            run('wij tellen = 0\nwij luister, zodra wij tellen veranderd is:\n    wij tellen = 9')

    def test_jij_luister_is_fout(self):
        with self.assertRaisesRegex(WerkwoordFout, 'W006.*jij luistert'):
            run('wij tellen = 0\njij springt = 0\njij luister, zodra wij tellen veranderd is:\n    jij springt = 1')

    def test_jij_luistert_werkt(self):
        self.assertEqual(run('wij tellen = 0\njij springt = 0\n'
                             'jij luistert, zodra wij tellen veranderd is:\n    jij springt = 1\n'
                             'wij tellen = 1\nschrijven(jij springt)'), ['1'])


class StatischeControle(unittest.TestCase):
    def test_kale_gebiedende_wijs_naar_ander_effect_in_ongebruikt_effect(self):
        with self.assertRaisesRegex(WerkwoordFout, 'W006.*ik verzoek tel!'):
            run('wij tellen = 0\nbetekent wij tellen:\n    wij tellen = 1\n'
                'betekent ik loop:\n    tel!, als ik loop nul is')


class LezenIsVrij(unittest.TestCase):
    def test_ik_mag_een_zal_van_de_verteller_lezen(self):
        self.assertEqual(run('lopen = 2\nzal groeien = lopen * 2\nik loop = 0\n'
                             'betekent ik loop:\n    ik loop = groeien\nik loop!\nschrijven(ik loop, groeien)'),
                         ['4 4'])


class PerActorBarrier(unittest.TestCase):
    SRC = ('wij tellen = 0\njij springt = 0\n'
           'betekent wij tellen:\n    wij tellen = wij tellen + 1\n'
           'betekent jij springt:\n    jij springt = jij springt + 1\n')

    def test_wachten_op_wij_laat_jij_liggen(self):
        self.assertEqual(run(self.SRC + 'ik verzoek tel!\nik verzoek spring!\n'
                             'wacht totdat wij klaar zijn\nschrijven(wij tellen, jij springt)\n'
                             'wacht totdat jij klaar bent\nschrijven(wij tellen, jij springt)'),
                         ['1 0', '1 1'])

    def test_transitieve_verzoeken_van_wij_worden_wel_afgewacht(self):
        src = ('wij tellen = 0\njij springt = 0\n'
               'betekent wij tellen:\n    wij tellen = wij tellen + 1\n    wij verzoeken spring!\n'
               'betekent jij springt:\n    jij springt = jij springt + 1\n'
               'ik verzoek tel!\nwacht totdat wij klaar zijn\nschrijven(wij tellen, jij springt)')
        self.assertEqual(run(src), ['1 1'])


if __name__ == '__main__':
    unittest.main()
