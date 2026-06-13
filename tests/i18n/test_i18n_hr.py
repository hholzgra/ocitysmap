# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: The ocitysmap contributors

import unittest
from ocitysmap.i18n import i18n_hr_HR


class CroatianTest(unittest.TestCase):
    def setUp(self):
        self.r = i18n_hr_HR('hr_HR.UTF-8', '')

    def test_user_readable_street_passthrough(self):
        self.assertEqual('Ulica kralja Tomislava',
                         self.r.user_readable_street('Ulica kralja Tomislava'))

    def test_upper_unaccent_string(self):
        cases = [
            ('ć', 'C'), ('č', 'C'), ('š', 'S'), ('ž', 'Z'),
            ('đ', 'D'), ('lj', 'L'), ('nj', 'N'),
        ]
        for src, expected in cases:
            with self.subTest(src=src):
                self.assertEqual(expected, self.r.upper_unaccent_string(src))

    def test_first_letter_equal(self):
        self.assertTrue(self.r.first_letter_equal('ć', 'č'))
        self.assertTrue(self.r.first_letter_equal('š', 's'))
        self.assertFalse(self.r.first_letter_equal('a', 'b'))


if __name__ == '__main__':
    unittest.main()
