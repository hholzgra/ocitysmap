# -*- coding: utf-8 -*-
import unittest
from ocitysmap.i18n import i18n_tr_generic


class TurkishTest(unittest.TestCase):
    def setUp(self):
        self.r = i18n_tr_generic('tr_TR.UTF-8', '')

    def test_user_readable_street(self):
        cases = [
            # appellation at start matches
            ('Sokak Atatürk',   'Atatürk (Sokak)'),
            # appellation at end — no match, returned unchanged
            ('Atatürk Sokak',   'Atatürk Sokak'),
            ('',                ''),
        ]
        for src, expected in cases:
            with self.subTest(src=src):
                self.assertEqual(expected, self.r.user_readable_street(src))


if __name__ == '__main__':
    unittest.main()
