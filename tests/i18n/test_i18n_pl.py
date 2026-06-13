# -*- coding: utf-8 -*-
import unittest
from ocitysmap.i18n import i18n_pl_generic


class PolishTest(unittest.TestCase):
    def setUp(self):
        self.r = i18n_pl_generic('pl_PL.UTF-8', '')

    def test_user_readable_street(self):
        # Polish uses ", " as separator (not " ()")
        cases = [
            ('Aleja Solidarności',   'Solidarności, Aleja'),
            ('Dr. Jana Pawła',       'Jana Pawła, Dr.'),
            # no appellation — returned unchanged
            ('ulica Kwiatowa',       'ulica Kwiatowa'),
            ('',                     ''),
        ]
        for src, expected in cases:
            with self.subTest(src=src):
                self.assertEqual(expected, self.r.user_readable_street(src))


if __name__ == '__main__':
    unittest.main()
