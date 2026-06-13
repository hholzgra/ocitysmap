# -*- coding: utf-8 -*-
import unittest
from ocitysmap.i18n import i18n_pt_br_generic


class BrazilianPortugueseTest(unittest.TestCase):
    def setUp(self):
        self.r = i18n_pt_br_generic('pt_BR.UTF-8', '')

    def test_user_readable_street(self):
        cases = [
            ('Rua das Flores',        'Flores (Rua das)'),
            ('Avenida do Brasil',     'Brasil (Avenida do)'),
            ('Praça da República',    'República (Praça da)'),
            ('Estrada Velha',         'Velha (Estrada)'),
        ]
        for src, expected in cases:
            with self.subTest(src=src):
                self.assertEqual(expected, self.r.user_readable_street(src))


if __name__ == '__main__':
    unittest.main()
