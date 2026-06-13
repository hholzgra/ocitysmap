# -*- coding: utf-8 -*-
import unittest
from ocitysmap.i18n import i18n_fa_generic


class PersianTest(unittest.TestCase):
    def setUp(self):
        self.r = i18n_fa_generic('fa_IR.UTF-8', '')

    def test_user_readable_street(self):
        cases = [
            # بلوار is in APPELLATIONS — match
            ('بلوار کریمخان',    'کریمخان (بلوار )'),
            # خیابان is not in APPELLATIONS — returned unchanged
            ('خیابان ولیعصر',   'خیابان ولیعصر'),
        ]
        for src, expected in cases:
            with self.subTest(src=src):
                self.assertEqual(expected, self.r.user_readable_street(src))

    def test_isrtl(self):
        self.assertTrue(self.r.isrtl())

    def test_number_category_name(self):
        self.assertEqual('۰-۹', self.r.number_category_name())


if __name__ == '__main__':
    unittest.main()
