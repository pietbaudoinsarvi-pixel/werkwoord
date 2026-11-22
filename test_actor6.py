"""Acceptatietests voor regel 6: persoon = actor en eigenaar.

Een `zodra` die door IK is geregistreerd op een WIJ-cel draait
in het gesprek dat de wijziging van WIJ opende, maar met de
schrijfrechten van IK. Een actorwissel geeft geen nieuwe eigendom.
"""
import unittest
from werkwoord import Werkwoord, WerkwoordFout


class ActorRule6Tests(unittest.TestCase):
    def test_two_concurrent_requests_are_atomic(self):
        source = '''wij tellen = 0
betekent wij tellen:
    wij tellen = wij tellen + 1
tegelijk:
    ik verzoek tel!
    jij verzoekt tel!
wacht totdat wij klaar zijn
schrijven(wij tellen)'''
        self.assertEqual(Werkwoord().run(source), ['2'])

    def test_listener_on_foreign_cell_runs_as_registrant(self):
        source = '''wij tellen = 0
ik voel = 0
ik luister, zodra wij tellen veranderd is:
    ik voel = ik voel + 1
wij tellen = 1
schrijven(ik voel, wij tellen)'''
        machine = Werkwoord()
        self.assertEqual(machine.run(source), ['1 1'])
        self.assertTrue(any(actor == 'ik' and action.startswith('zodra')
                            for _, actor, action in machine.turn_log))

    def test_listener_cannot_steal_foreign_ownership(self):
        source = '''wij tellen = 0
ik luister, zodra wij tellen veranderd is:
    wij tellen = 7
wij tellen = 1'''
        with self.assertRaisesRegex(WerkwoordFout, 'W006'):
            Werkwoord().run(source)

    def test_foreign_write_rejected_in_unused_effect(self):
        source = '''wij tellen = 0
betekent ik voel:
    wij tellen = wij tellen + 1'''
        with self.assertRaisesRegex(WerkwoordFout, 'W006'):
            Werkwoord().run(source)

    def test_personal_cells_and_pasts_are_distinct(self):
        source = '''ik tel = 1
ik tel = 2
jij telt = 10
wij tellen = 100
schrijven(ik tel, ik telde, jij telt, wij tellen)'''
        self.assertEqual(Werkwoord().run(source), ['2 1 10 100'])

    def test_wrong_conjugation_at_barrier_rejected(self):
        with self.assertRaisesRegex(WerkwoordFout, 'W006'):
            Werkwoord().run('wacht totdat jij klaar zijn')

    def test_wrong_conjugation_for_request_rejected(self):
        with self.assertRaisesRegex(WerkwoordFout, 'W006'):
            Werkwoord().run('wij tellen = 0\nik verzoekt tel!')


if __name__ == '__main__':
    unittest.main()
