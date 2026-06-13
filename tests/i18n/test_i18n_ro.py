# -*- coding: utf-8 -*-
import unittest
from ocitysmap.i18n import i18n_ro_generic


class RomanianTest(unittest.TestCase):
    def setUp(self):
        self.r = i18n_ro_generic('ro_RO.UTF-8', '')

    def test_user_readable_street(self):
        # Romanian uses ", " as separator (like Polish)
        cases = [
            ('Strada Unirii',        'Unirii, Strada'),
            ('Bulevardul Eroilor',   'Eroilor, Bulevardul'),
            ('Calea Victoriei',      'Victoriei, Calea'),
            ('Piata Unirii',         'Unirii, Piata'),
        ]
        for src, expected in cases:
            with self.subTest(src=src):
                self.assertEqual(expected, self.r.user_readable_street(src))


if __name__ == '__main__':
    unittest.main()
