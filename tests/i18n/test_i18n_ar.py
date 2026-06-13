# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: The ocitysmap contributors

import unittest
from ocitysmap.i18n import i18n_ar_generic


class ArabicTest(unittest.TestCase):
    def setUp(self):
        self.r = i18n_ar_generic('ar_MA.UTF-8', '')

    def test_user_readable_street(self):
        cases = [
            ('شارع الحسن',      'حسن (شارع ال)'),
            ('ميدان الشهداء',   'شهداء (ميدان ال)'),
        ]
        for src, expected in cases:
            with self.subTest(src=src):
                self.assertEqual(expected, self.r.user_readable_street(src))

    def test_isrtl(self):
        self.assertTrue(self.r.isrtl())


if __name__ == '__main__':
    unittest.main()
