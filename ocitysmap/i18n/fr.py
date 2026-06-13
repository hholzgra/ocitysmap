# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: The ocitysmap contributors

import re
from . import i18n, _install_language

class i18n_fr_generic(i18n):
    APPELLATIONS = [ "Accès", "Allée", "Allées", "Autoroute", "Avenue",
                     "Avenues", "Barrage",
                     "Boulevard", "Carrefour", "Chaussée", "Chemin",
                     "Chemin rural",
                     "Cheminement", "Cale", "Cales", "Cavée", "Cité",
                     "Clos", "Coin", "Côte", "Cour", "Cours", "Descente",
                     "Degré", "Escalier",
                     "Escaliers", "Esplanade", "Funiculaire",
                     "Giratoire", "Hameau", "Impasse", "Jardin",
                     "Jardins", "Liaison", "Lotissement", "Mail",
                     "Montée", "Môle",
                     "Parc", "Passage", "Passerelle", "Passerelles",
                     "Place", "Placette", "Pont", "Promenade",
                     "Petite Avenue", "Petite Rue", "Quai",
                     "Rampe", "Rang", "Résidence", "Rond-Point",
                     "Route forestière", "Route", "Rue", "Ruelle",
                     "Square", "Sente", "Sentier", "Sentiers", "Terre-Plein",
                     "Télécabine", "Traboule", "Traverse", "Tunnel",
                     "Venelle", "Villa", "Virage"
                    ]
    DETERMINANTS = [ " des", " du", " de la", " de l'",
                     " de", " d'", " aux", ""
                    ]

    SPACE_REDUCE = re.compile(r"\s+")
    PREFIX_REGEXP = re.compile(r"^(?P<prefix>(%s)(%s)?)\s?\b(?P<name>.+)" %
                               ("|".join(APPELLATIONS),
                                "|".join(DETERMINANTS)), re.IGNORECASE
                               | re.UNICODE)

    # for IndexPageGenerator.upper_unaccent_string
    E_ACCENT = re.compile(r"[éèêëẽ]", re.IGNORECASE | re.UNICODE)
    I_ACCENT = re.compile(r"[íìîïĩ]", re.IGNORECASE | re.UNICODE)
    A_ACCENT = re.compile(r"[áàâäãæ]", re.IGNORECASE | re.UNICODE)
    O_ACCENT = re.compile(r"[óòôöõœ]", re.IGNORECASE | re.UNICODE)
    U_ACCENT = re.compile(r"[úùûüũ]", re.IGNORECASE | re.UNICODE)
    Y_ACCENT = re.compile(r"[ÿ]", re.IGNORECASE | re.UNICODE)

    def __init__(self, language, locale_path):
        self.language = str(language)
        _install_language(language, locale_path)

    def upper_unaccent_string(self, s):
        s = self.E_ACCENT.sub("e", s)
        s = self.I_ACCENT.sub("i", s)
        s = self.A_ACCENT.sub("a", s)
        s = self.O_ACCENT.sub("o", s)
        s = self.U_ACCENT.sub("u", s)
        s = self.Y_ACCENT.sub("y", s)
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


    def language_desc(self):
        return 'Français (%s)' % self.language
