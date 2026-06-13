# -*- coding: utf-8 -*-
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: The ocitysmap contributors

import unittest
from ocitysmap.i18n import i18n_be_generic


class BelarusianTest(unittest.TestCase):
    def setUp(self):
        self.r = i18n_be_generic('be_BY.UTF-8', '')

    def test_user_readable_street(self):
        cases = [
            ('праспект Незалежнасці',        'Незалежнасці, праспект'),
            ('Кастрычніцкая вуліца',         'Кастрычніцкая вуліца'),
            ('вуліца Янкі Купалы',           'Янкі Купалы, вуліца'),
            ('вуліца Раманаўская Слабада',   'Раманаўская Слабада, вуліца'),
            ('Аляксандраўскі сквер',         'Аляксандраўскі сквер'),
            ('Музычны завулак',              'Музычны завулак'),
            ('Парк Цівалі',                  'Цівалі, парк'),
            ('вуліца 60 год БССР',           '60 год БССР, вуліца'),
            ('вул. 8 сакавіка',              '8 сакавіка, вуліца'),
            ('завулак Баўмана',              'Баўмана, завулак'),
            ('плошча 17 Верасня',            '17 Верасня, плошча'),
            ('пл. 17 Верасня',               '17 Верасня, плошча'),
            ('1-і завулак Цімашэнкі',        'Цімашэнкі, 1-і завулак'),
        ]
        for src, expected in cases:
            with self.subTest(src=src):
                self.assertEqual(expected, self.r.user_readable_street(src))


if __name__ == '__main__':
    unittest.main()
