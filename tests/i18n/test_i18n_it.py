# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: The ocitysmap contributors

import unittest
from ocitysmap.i18n import i18n_it_generic


class ItalianTest(unittest.TestCase):
    def setUp(self):
        self.r = i18n_it_generic('it_IT.UTF-8', '')

    def test_user_readable_street(self):
        cases = [
            ('Via della Rosa',            'Rosa (Via della)'),
            ('Piazza San Marco',          'San Marco (Piazza)'),
            ('Corso Vittorio Emanuele',   'Vittorio Emanuele (Corso)'),
            # no appellation — returned unchanged
            ('Lungotevere',               'Lungotevere'),
        ]
        for src, expected in cases:
            with self.subTest(src=src):
                self.assertEqual(expected, self.r.user_readable_street(src))

    def test_upper_unaccent_string(self):
        self.assertEqual('EIA', self.r.upper_unaccent_string('èîà'))


if __name__ == '__main__':
    unittest.main()
