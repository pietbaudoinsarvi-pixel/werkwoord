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

class ActorTests(unittest.TestCase):
    """Regel 6: persoonsvorm, eigenaarschap, verzoeken en ontvangers van zodra."""

    def test_twee_actoren_hogen_gedeelde_cel_racevrij_op(self):
        src = ('wij tellen = 0\n'
               'betekent wij tellen:\n    wij tellen = wij tellen + 1\n'
               'tegelijk:\n    ik verzoek tel!\n    jij verzoekt tel!\n'
               'wacht totdat wij klaar zijn\nschrijven(wij tellen)')
        machine = Werkwoord()
        self.assertEqual(machine.run(src), ['2'])
        self.assertEqual([turn[1] for turn in machine.turn_log], ['wij', 'wij'])

    def test_directe_mutatie_andere_actor_is_w006(self):
        src = ('wij tellen = 0\n'
               'betekent ik lopen:\n    wij tellen = wij tellen + 1\n')
        with self.assertRaisesRegex(WerkwoordFout, 'W006'):
            Werkwoord().run(src)

    def test_slechte_persoonsvorm_is_w006(self):
        with self.assertRaisesRegex(WerkwoordFout, 'W006'):
            Werkwoord().run('ik telt = 0')
        with self.assertRaisesRegex(WerkwoordFout, 'W006'):
            Werkwoord().run('wij tellen = 0\nik verzoekt tel!')

    def test_actor_eigen_cel_is_toegestaan(self):
        src = ('ik loop = 0\nbetekent ik loop:\n    ik loop = ik loop + 1\n'
               'ik loop!\nschrijven(ik loop, ik liep)')
        self.assertEqual(Werkwoord().run(src), ['1 0'])

    def test_zodra_van_ik_op_wij_cel_draait_in_ik_beurt(self):
        src = ('wij tellen = 0\nik loop = 0\n'
               'betekent wij tellen:\n    wij tellen = wij tellen + 1\n'
               'ik luister, zodra wij tellen veranderd is:\n'
               '    ik loop = ik loop + 1\n'
               'ik verzoek tel!\nwacht totdat wij klaar zijn\n'
               'schrijven(wij tellen, ik loop)')
        machine = Werkwoord()
        self.assertEqual(machine.run(src), ['1 1'])
        request, reaction = machine.turn_log
        self.assertEqual((request[1], reaction[1]), ('wij', 'ik'))
        self.assertEqual(request[0], reaction[0], 'beide beurten delen één gesprek')

    def test_luisteraar_erft_geen_wij_schrijfrechten(self):
        src = ('wij tellen = 0\n'
               'ik luister, zodra wij tellen veranderd is:\n'
               '    wij tellen = wij tellen + 1\n'
               'wij tellen = 1')
        with self.assertRaisesRegex(WerkwoordFout, 'W006'):
            Werkwoord().run(src)

    def test_verzoek_vanuit_ik_naar_wij_in_bericht(self):
        src = ('wij tellen = 0\nik loop = 0\n'
               'betekent ik loop:\n    ik verzoek tel!\n'
               'betekent wij tellen:\n    wij tellen = wij tellen + 1\n'
               'ik loop!\nwacht totdat wij klaar zijn\nschrijven(wij tellen)')
        self.assertEqual(Werkwoord().run(src), ['1'])

    def test_ambigue_ontvanger_vraagt_explicitatie(self):
        src = ('ik tel = 0\nwij tellen = 0\n'
               'jij verzoekt tel!')
        with self.assertRaisesRegex(WerkwoordFout, 'W006.*mogelijke ontvangers'):
            Werkwoord().run(src)

    def test_alle_oude_tests_blijven_werken(self):
        # Integrieteitscontrole: alles zonder personen behoudt de oude betekenis.
        self.assertEqual(Werkwoord().run('lopen = 5\nlopen = 8\nschrijven(liep)'), ['5'])
