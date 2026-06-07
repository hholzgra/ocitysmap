import re, gettext
from . import i18n, _install_language

class i18n_fa_generic(i18n):
    APPELLATIONS = [ "خ", "خ.", "جاده", "راه", "مسیر", "بلوار",
                     "بزرگراه", "بزرگ راه", "بزرگ‌راه", "آزادراه",
                     "آزاد راه", "اتوبان", "تقاطع", "چهارراه", "چهار راه",
                     "سه راه", "سه‌راه", "سه راهی", "سه‌راهی",
                     "دوراهی", "دو راهی", "میدان", "م.", "م",
                     "کوچه", "ک.", "ک", "کوی", "بن بست", "بن‌بست",
                     "بنبست", "ب.", "ب", "شهید", "شهیدان", "پل",
                     "گذر","خیابان شهیدان", "خیابان شهید",
                     "خ. شهید", "خ شهید", "خ.شهید" , "جاده شهید", "بلوار شهید",
                     "بزرگراه شهید", "بزرگ راه شهید", "بزرگ‌راه شهید",
                     "آزادراه شهید", "آزاد راه شهید", "اتوبان شهید",
                     "تقاطع شهید", "چهارراه شهید", "چهار راه شهید",
                     "سه راه شهید", "سه‌راه شهید", "سه راهی شهید",
                     "سه‌راهی شهید", "دوراهی شهید", "دو راهی شهید",
                     "میدان شهید", "م شهید", "م. شهید", "م.شهید", "کوچه شهید",
                     "ک شهید", "ک. شهید", "کوی شهید", "بن بست شهید",
                     "بن‌بست شهید", "بنبست شهید", "ب. شهید", "ب.شهید", "ب شهید",
                     "پل شهید", "گذر شهید", "ک شهید", "ک. شهید", "ک.شهید"
                    ]

    # DETERMINANT in Persian is Kasreh. Kasreh (ِ ) almost never appear in names but we just pronounce it. There is some cases that its shape changes to " ٔ " (spaces are for displaying the character alone) or " ی" or "‌ی" (ZWNJ+ی). It's rare that these are present on OSM maps. So for now we could ignore them. But after each APPELLATION there MUST be a space, otherwise it's part of the main name (or maybe a typo).
    DETERMINANTS = [ " "
                    ]

    SPACE_REDUCE = re.compile(r"\s+")
    PREFIX_REGEXP = re.compile(r"^(?P<prefix>(%s)(%s)?)\s?\b(?P<name>.+)" %
                                    ("|".join(APPELLATIONS),
                                     "|".join(DETERMINANTS)), re.IGNORECASE
                                                                 | re.UNICODE)

    # for IndexPageGenerator.upper_unaccent_string
    A_ACCENT = re.compile(r"[اأإ]", re.IGNORECASE | re.UNICODE)

    # following line contains diacritics (The usage of these chars is when we want distinguish between similar words that have the same letters with different pronunciation). Their usage is rare.
    # There is also character kashida (ـ). this is not a diacritic, but a character that stretch some letters. (This is also rare)
    O_ACCENT = re.compile(r"[ًٌٍَُِْـ]", re.IGNORECASE | re.UNICODE)
    T_ACCENT = re.compile(r"[تة]", re.IGNORECASE | re.UNICODE)
    Y_ACCENT = re.compile(r"[ئءیىي]", re.IGNORECASE | re.UNICODE)
    V_ACCENT = re.compile(r"[وؤ]", re.IGNORECASE | re.UNICODE)

    def __init__(self, language, locale_path):
        self.language = str(language)
        _install_language(language, locale_path)

    def upper_unaccent_string(self, s):
        s = self.A_ACCENT.sub("ا", s)
        # to ignoring diacritics and kashida (ـ) I put an empty string.
        s = self.O_ACCENT.sub("", s)
        s = self.T_ACCENT.sub("ت", s)
        s = self.Y_ACCENT.sub("ی", s)
        s = self.V_ACCENT.sub("و", s)
        return s.upper()

    def language_code(self):
        return self.language

    def user_readable_street(self, name):
        name = name.strip()
        name = self.SPACE_REDUCE.sub(" ", name)
        name = self.PREFIX_REGEXP.sub(r"\g<name> (\g<prefix>)", name)
        return name

    def first_letter_equal(self, a, b):
        return self.upper_unaccent_string(a) == self.upper_unaccent_string(b)

    def isrtl(self):
        return True

    def number_category_name(self):
        return "۰-۹"

    def language_desc(self):
        return 'فارسی  (%s)' % self.language
