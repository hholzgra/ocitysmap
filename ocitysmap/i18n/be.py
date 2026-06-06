import re, gettext
from . import i18n, _install_language

class i18n_be_generic(i18n):
    # Based on code for Russian language:
    STATUS_PARTS = [
        (u"вуліца", [u"вул"]),
        (u"плошча", [u"пл"]),
        (u"завулак", [u"зав", u"зав-к"]),
        (u"праезд", [u"пр-д"]),
        (u"шаша", [u"ш"]),
        (u"бульвар", [u"бул", u"б-р"]),
        (u"тупік", [u"туп"]),
        (u"набярэжная", [u"наб"]),
        (u"праспект", [u"праспект", u"пр-кт", u"пр-т"]),
        (u"алея", []),
        (u"мост", []),
        (u"парк", []),
        (u"тракт", [u"тр-т", u"тр"]),
        (u"раён", [u"р-н"]),
        (u"мікрараён", [u"мкр-н", u"мк-н", u"мкр", u"мкрн"]),
        (u"пасёлак", [u"пас"]),
        (u"вёска", [ u"в"]),
        (u"квартал", [u"кв-л", u"кв"]),
    ]

    # matches one or more spaces
    SPACE_REDUCE = re.compile(r"\s+")
    # mapping from status abbreviations (w/o '.') to full status names
    STATUS_PARTS_ABBREV_MAPPING = dict((f, t) for t, ff in STATUS_PARTS for f in ff)
    # set of full (not abbreviated) status parts
    STATUS_PARTS_FULL = set((x[0] for x in STATUS_PARTS))
    # matches any abbreviated status part with optional '.'
    STATUS_ABBREV_REGEXP = re.compile(r"\b(%s)\.?(?=\W|$)" % u"|".join(
        f for t, ff in STATUS_PARTS for f in ff), re.IGNORECASE | re.UNICODE)
    # matches status prefixes at start of name used to move prefixes to the end
    PREFIX_REGEXP = re.compile(
        r"^(?P<num_prefix>\d+-?(і|ы|я))?\s*(?P<prefix>(%s)\.?)?\s*(?P<name>.+)?" %
        (u"|".join(f for f,t in STATUS_PARTS)), re.IGNORECASE | re.UNICODE)

    def __init__(self, language, locale_path):
        self.language = str(language)
        _install_language(language, locale_path)

    def upper_unaccent_string(self, s):
        return s.upper()

    def language_code(self):
        return self.language

    @staticmethod
    def _rewrite_street_parts(matches):
        if (matches.group('num_prefix') is None and
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

