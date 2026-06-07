import re
from . import i18n, _install_language

class i18n_be_generic(i18n):
    # Based on code for Russian language:
    STATUS_PARTS = [
        ("вуліца", ["вул"]),
        ("плошча", ["пл"]),
        ("завулак", ["зав", "зав-к"]),
        ("праезд", ["пр-д"]),
        ("шаша", ["ш"]),
        ("бульвар", ["бул", "б-р"]),
        ("тупік", ["туп"]),
        ("набярэжная", ["наб"]),
        ("праспект", ["праспект", "пр-кт", "пр-т"]),
        ("алея", []),
        ("мост", []),
        ("парк", []),
        ("тракт", ["тр-т", "тр"]),
        ("раён", ["р-н"]),
        ("мікрараён", ["мкр-н", "мк-н", "мкр", "мкрн"]),
        ("пасёлак", ["пас"]),
        ("вёска", [ "в"]),
        ("квартал", ["кв-л", "кв"]),
    ]

    # matches one or more spaces
    SPACE_REDUCE = re.compile(r"\s+")
    # mapping from status abbreviations (w/o '.') to full status names
    STATUS_PARTS_ABBREV_MAPPING = dict((f, t) for t, ff in STATUS_PARTS for f in ff)
    # set of full (not abbreviated) status parts
    STATUS_PARTS_FULL = set((x[0] for x in STATUS_PARTS))
    # matches any abbreviated status part with optional '.'
    STATUS_ABBREV_REGEXP = re.compile(r"\b(%s)\.?(?=\W|$)" % "|".join(
        f for t, ff in STATUS_PARTS for f in ff), re.IGNORECASE | re.UNICODE)
    # matches status prefixes at start of name used to move prefixes to the end
    PREFIX_REGEXP = re.compile(
        r"^(?P<num_prefix>\d+-?(і|ы|я))?\s*(?P<prefix>(%s)\.?)?\s*(?P<name>.+)?" %
        ("|".join(f for f,t in STATUS_PARTS)), re.IGNORECASE | re.UNICODE)

    def __init__(self, language, locale_path):
        self.language = str(language)
        _install_language(language, locale_path)

    def upper_unaccent_string(self, s):
        return s.upper()

    def language_code(self):
        return self.language

    @staticmethod
    def _rewrite_street_parts(matches):
        if ( matches.group('num_prefix') is None and
             matches.group('prefix') is not None and
             matches.group('name') in i18n_be_generic.STATUS_PARTS_FULL):
            return matches.group(0)
        elif matches.group('num_prefix') is None and matches.group('prefix') is None:
            return matches.group(0)
        elif matches.group('name') is None:
            return matches.group(0)
        else:
            return ", ".join((matches.group('name'),
                " ". join(s.lower()
                    for s in matches.group('num_prefix', 'prefix')
                    if s is not None)
                ))

    def user_readable_street(self, name):
        name = name.strip()
        name = self.SPACE_REDUCE.sub(" ", name)
        # Normalize abbreviations
        name = self.STATUS_ABBREV_REGEXP.sub(lambda m:
                self.STATUS_PARTS_ABBREV_MAPPING.get(
                    m.group(0).replace('.', ''), m.group(0)),
            name)
        # Move prefixed status parts to the end for sorting
        name = self.PREFIX_REGEXP.sub(self._rewrite_street_parts, name)
        # TODO: move "малая", "большая" after name but before status
        return name

    def first_letter_equal(self, a, b):
        return self.upper_unaccent_string(a) == self.upper_unaccent_string(b)

    def language_desc(self):
        return 'Беларусь (%s)' % self.language
