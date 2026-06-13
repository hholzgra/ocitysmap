# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: The ocitysmap contributors

import unittest
from ocitysmap.i18n import i18n_ast_generic


class AsturianTest(unittest.TestCase):
    def setUp(self):
        self.r = i18n_ast_generic('ast_ES.UTF-8', '')

    def test_user_readable_street(self):
        cases = [
            ('Cai de la Paz',    'la Paz (Cai de)'),
            ('Avenida del Rey',  'Rey (Avenida del)'),
            ('Plaza Mayor',      'Mayor (Plaza)'),
        ]
        for src, expected in cases:
            with self.subTest(src=src):
                self.assertEqual(expected, self.r.user_readable_street(src))


if __name__ == '__main__':
    unittest.main()
