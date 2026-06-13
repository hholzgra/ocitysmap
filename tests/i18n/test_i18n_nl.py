# -*- coding: utf-8 -*-
import unittest
from ocitysmap.i18n import i18n_nl_generic


class DutchTest(unittest.TestCase):
    def setUp(self):
        self.r = i18n_nl_generic('nl_NL.UTF-8', '')

    def test_user_readable_street(self):
        cases = [
            ('Sint Janstraat',           'Janstraat (Sint)'),
            ('Dr. Philipsweg',           'Philipsweg (Dr.)'),
            ('Prins van Oranjestraat',   'Oranjestraat (Prins van)'),
            # no recognised prefix — returned unchanged
            ('Kerkstraat',               'Kerkstraat'),
            ('',                         ''),
        ]
        for src, expected in cases:
            with self.subTest(src=src):
                self.assertEqual(expected, self.r.user_readable_street(src))


if __name__ == '__main__':
    unittest.main()
