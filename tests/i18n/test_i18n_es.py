# -*- coding: utf-8 -*-
import unittest
from ocitysmap.i18n import i18n_es_generic


class SpanishTest(unittest.TestCase):
    def setUp(self):
        self.r = i18n_es_generic('es_ES.UTF-8', '')

    def test_user_readable_street(self):
        cases = [
            ('Calle de la Rosa',      'Rosa (Calle de la)'),
            ('Avenida de los Reyes',  'Reyes (Avenida de los)'),
            ('Paseo del Prado',       'Prado (Paseo del)'),
            # no appellation — returned unchanged
            ('Gran Via',              'Gran Via'),
        ]
        for src, expected in cases:
            with self.subTest(src=src):
                self.assertEqual(expected, self.r.user_readable_street(src))

    def test_upper_unaccent_string(self):
        self.assertEqual('AOEN', self.r.upper_unaccent_string('áöéñ'))


if __name__ == '__main__':
    unittest.main()
