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

if __name__ == '__main__':
    unittest.main()
