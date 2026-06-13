# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: The ocitysmap contributors

import unittest
from ocitysmap.i18n import i18n_fr_generic


class FrenchTest(unittest.TestCase):
    def setUp(self):
        self.r = i18n_fr_generic('fr_FR.UTF-8', '')

    def test_user_readable_street(self):
        cases = [
            ('Rue de la Paix',       'Paix (Rue de la)'),
            ('Avenue des Champs',    'Champs (Avenue des)'),
            ('Allée du Moulin',      'Moulin (Allée du)'),
            ('Place Gambetta',       'Gambetta (Place)'),
            # whitespace normalisation
            ('  Rue  du  Port  ',    'Port (Rue du)'),
            # no appellation — returned unchanged
            ('Les Épinettes',        'Les Épinettes'),
        ]
        for src, expected in cases:
            with self.subTest(src=src):
                self.assertEqual(expected, self.r.user_readable_street(src))

    def test_upper_unaccent_string(self):
        self.assertEqual('EAUO', self.r.upper_unaccent_string('éàüô'))

    def test_first_letter_equal(self):
        self.assertTrue(self.r.first_letter_equal('é', 'e'))
        self.assertTrue(self.r.first_letter_equal('È', 'e'))
        self.assertFalse(self.r.first_letter_equal('a', 'b'))

    def test_isrtl(self):
        self.assertFalse(self.r.isrtl())


if __name__ == '__main__':
    unittest.main()
