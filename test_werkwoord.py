import unittest
from pathlib import Path
from werkwoord import Werkwoord, WerkwoordFout
HERE = Path(__file__).parent

class InterpreterTests(unittest.TestCase):
    def run_file(self, file):
        return Werkwoord().run((HERE / file).read_text())

    def test_countdown(self):
        self.assertEqual(self.run_file('aftellen.ww'), ['3', '2', '1', '0'])

    def test_fibonacci(self):
        self.assertEqual(self.run_file('fibonacci.ww'), ['0', '1', '1', '2', '3'])

    def test_lazy_memoized(self):
        self.assertEqual(self.run_file('toekomst.ww'), ['5', '24', '24'])

    def test_one_shot_zodra(self):
        self.assertEqual(self.run_file('reactief.ww'), ['2'])

    def test_assertion(self):
        with self.assertRaisesRegex(WerkwoordFout, 'Assertie mislukt'):
            Werkwoord().run('tellen = 0\nbetekent tellen:\n  tellen = 1\ntel!, omdat tellen boven nul ligt')

    def test_past_read_only(self):
        with self.assertRaisesRegex(WerkwoordFout, 'alleen-lezen'):
            Werkwoord().run('lopen = 3\nliep = 4')

    def test_later_listener_requires_change(self):
        self.assertEqual(Werkwoord().run('tellen = 0\nschrijf!, zodra tellen nul is\ntellen = 1\ntellen = 0'), ['0'])

    # ---------- v0.2: regel 4 ----------

    def test_alias_shares_cell_and_history(self):
        self.assertEqual(Werkwoord().run(
            'lopen = 5\nde rennen = lopen\nrennen = 9\nschrijven(lopen, liep, rende)'), ['9 5 5'])

    def test_snapshot_has_own_history(self):
        self.assertEqual(Werkwoord().run(
            'lopen = 5\nhet springen = lopen\nlopen = 8\nspringen = 6\n'
            'schrijven(springen, sprong, lopen, liep)\nschrijven(des springens)'), ['6 5 8 5', '[5, 6]'])

    def test_article_cannot_rebind(self):
        with self.assertRaisesRegex(WerkwoordFout, 'W004'):
            Werkwoord().run('lopen = 5\nde rennen = lopen\nhet rennen = lopen')

    def test_alias_shares_effect(self):
        self.assertEqual(Werkwoord().run(
            'lopen = 1\nbetekent lopen:\n    lopen = lopen + 1\nde rennen = lopen\nren!\nschrijven(lopen)'), ['2'])

    def test_lidwoorden_file(self):
        self.assertEqual(self.run_file('lidwoorden.ww'), ['9 5 5', '6 5', '[5, 9]', '[5, 6, 9]'])

    # ---------- v0.2: regel 5 ----------

    def test_reciprocal_with_reregistration_terminates(self):
        self.assertEqual(self.run_file('gesprek.ww'), ['2 1'])

    def test_mutual_repetition_is_one_turn_per_gesprek(self):
        src = ('pingen = 0\npongen = 0\n'
               'pongen herhaalt zich, zodra pingen veranderd is:\n    pongen = pongen + 1\n'
               'pingen herhaalt zich, zodra pongen veranderd is:\n    pingen = pingen + 1\n'
               'pingen = 1\nschrijven(pingen, pongen)\n'
               'pingen = 10\nschrijven(pingen, pongen)')
        self.assertEqual(Werkwoord().run(src), ['2 1', '11 2'])

    def test_listener_fires_once_per_gesprek(self):
        src = ('vragen = 0\ntellen = 0\nbetekent vragen:\n    vragen = vragen + 1\n    vragen = vragen + 1\n'
               'tellen herhaalt zich, zodra vragen veranderd is:\n    tellen = tellen + 1\n'
               'vraag!\nvraag!\nvraag!\nschrijven(vragen, tellen)')
        self.assertEqual(Werkwoord().run(src), ['6 3'])

    def test_change_is_an_event_not_a_state(self):
        # v0.1 printte hier '1' bij de toewijzing aan lopen: een oude verandering gold nog als nieuw.
        src = 'tellen = 0\ntellen = 1\nschrijf!, zodra tellen verandert is\nlopen = 5\ntellen = 2'
        self.assertEqual(Werkwoord().run(src), ['2'])

    def test_elkaar_rejects_foreign_listener(self):
        with self.assertRaisesRegex(WerkwoordFout, 'W010'):
            Werkwoord().run('vragen = 0\nantwoorden = 0\nlopen = 0\n'
                            'vragen en antwoorden beïnvloeden elkaar:\n    loop!, zodra lopen veranderd is')

    # ---------- v0.2: ontwerpvraag zal + zodra ----------

    def test_forcing_zal_is_an_event(self):
        src = ('lopen = 4\nzal verdubbelen = lopen * 2\nbetekent lopen:\n    schrijven(verdubbelen)\n'
               'schrijf!, zodra verdubbelen veranderd is\nloop!')
        self.assertEqual(Werkwoord().run(src), ['8', '8'])

    def test_bijzin_never_forces_the_future(self):
        src = ('lopen = 4\nzal verdubbelen = lopen * 2\nschrijf!, zodra verdubbelen boven 10 ligt\n'
               'lopen = 8\nschrijven("nog lui")\nschrijven(verdubbelen)')
        self.assertEqual(Werkwoord().run(src), ['nog lui', '16', '16'])

if __name__ == '__main__':
    unittest.main()
