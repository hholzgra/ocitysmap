# -*- coding: utf-8 -*-
import unittest
from ocitysmap.i18n import i18n_ca_generic


class CatalanTest(unittest.TestCase):
    def setUp(self):
        self.r = i18n_ca_generic('ca_ES.UTF-8', '')

    def test_user_readable_street(self):
        cases = [
            ('Carrer de la Pau',      'Pau (Carrer de la)'),
            ('Avinguda del Portal',   'Portal (Avinguda del)'),
            ('Passeig de Gràcia',     'Gràcia (Passeig de)'),
            ('Plaça Catalunya',       'Catalunya (Plaça)'),
        ]
        for src, expected in cases:
            with self.subTest(src=src):
                self.assertEqual(expected, self.r.user_readable_street(src))

    def test_upper_unaccent_string(self):
        self.assertEqual('AOENC', self.r.upper_unaccent_string('àöéñç'))


if __name__ == '__main__':
    unittest.main()
