# -*- coding: utf-8 -*-
import unittest
from ocitysmap.i18n import i18n_al_generic


class AlbanianTest(unittest.TestCase):
    def setUp(self):
        self.r = i18n_al_generic('sq_AL.UTF-8', '')

    def test_user_readable_street(self):
        cases = [
            ('Rruga e Barrikadave',   'e Barrikadave (Rruga)'),
            # no appellation — returned unchanged
            ('Bulevardi',             'Bulevardi'),
            ('',                      ''),
        ]
        for src, expected in cases:
            with self.subTest(src=src):
                self.assertEqual(expected, self.r.user_readable_street(src))


if __name__ == '__main__':
    unittest.main()
