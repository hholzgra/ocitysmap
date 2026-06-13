# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: The ocitysmap contributors

import unittest
from ocitysmap.i18n import i18n_de_generic


class GermanTest(unittest.TestCase):
    def setUp(self):
        self.r = i18n_de_generic('de_DE.UTF-8', '')

    def test_user_readable_street(self):
        # German has no active appellations — only strips/normalises whitespace
        cases = [
            ('Hauptstraße',              'Hauptstraße'),
            ('  Bahnhofstraße  ',        'Bahnhofstraße'),
            ('Platz  der  Republik',     'Platz der Republik'),
            ('',                         ''),
        ]
        for src, expected in cases:
            with self.subTest(src=src):
                self.assertEqual(expected, self.r.user_readable_street(src))

    def test_upper_unaccent_string(self):
        self.assertEqual('AOUE', self.r.upper_unaccent_string('äöüé'))

    def test_first_letter_equal(self):
        self.assertTrue(self.r.first_letter_equal('ä', 'a'))
        self.assertFalse(self.r.first_letter_equal('a', 'b'))


if __name__ == '__main__':
    unittest.main()
