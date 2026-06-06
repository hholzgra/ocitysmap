import re, gettext
from . import i18n, _install_language

class i18n_ast_generic(i18n):

    APPELLATIONS = [ # Asturian
                     u"Accesu", u"Autopista", u"Autovia", u"Avenida",
                     u"Baxada", u"Barrancu", u"Barriu", u"Barriada",
                     u"Biblioteca", u"Cai", u"Caleya",
                     u"Calzada", u"Camín", u"Carretera", u"Cuesta",
                     u"Estación", u"Hospital", u"Iglesia", u"Monasteriu",
                     u"Monumentu", u"Muelle", u"Muséu",
                     u"Palaciu", u"Parque", u"Pasadizu", u"Pasaxe",
                     u"Paséu", u"Planta", u"Plaza", u"Polígonu",
                     u"Ronda", u"Travesía", u"Urbanización", u"Via",
                     u"Xardín", u"Xardinos",

                     # Spanish (different from Asturian)
                     u"Acceso", u"Acequia", u"Alameda", u"Alquería",
                     u"Andador", u"Angosta", u"Apartamentos", u"Apeadero",
                     u"Arboleda", u"Arrabal", u"Arroyo", u"Autovía",
                     u"Bajada", u"Balneario", u"Banda",
                     u"Barranco", u"Barranquil", u"Barrio", u"Bloque",
                     u"Brazal", u"Bulevar", u"Calle", u"Calleja",
                     u"Callejón", u"Callejuela", u"Callizo",
                     u"Camino", u"Camping", u"Cantera", u"Cantina",
                     u"Cantón", u"Carrera", u"Carrero", u"Carreterín",
                     u"Carretil", u"Carril", u"Caserío", u"Chalet",
                     u"Cinturón", u"Circunvalación", u"Cobertizo",
                     u"Colonia", u"Complejo", u"Conjunto", u"Convento",
                     u"Cooperativa", u"Corral", u"Corralillo", u"Corredor",
                     u"Cortijo", u"Costanilla", u"Costera", u"Cuadra",
                     u"Dehesa", u"Demarcación", u"Diagonal",
                     u"Diseminado", u"Edificio", u"Empresa", u"Entrada",
                     u"Escalera", u"Escalinata", u"Espalda", u"Estación",
                     u"Estrada", u"Explanada", u"Extramuros", u"Extrarradio",
                     u"Fábrica", u"Galería", u"Glorieta", u"Gran Vía",
                     u"Granja", u"Hipódromo", u"Jardín", u"Ladera",
                     u"Llanura", u"Malecón", u"Mercado", u"Mirador",
                     u"Monasterio", u"Núcleo", u"Palacio",
                     u"Pantano", u"Paraje", u"Particular",
                     u"Partida", u"Pasadizo", u"Pasaje", u"Paseo",
                     u"Paseo marítimo", u"Pasillo", u"Plaza", u"Plazoleta",
                     u"Plazuela", u"Poblado", u"Polígono", u"Polígono industrial",
                     u"Portal", u"Pórtico", u"Portillo", u"Prazuela",
                     u"Prolongación", u"Pueblo", u"Puente", u"Puerta",
                     u"Puerto", u"Punto kilométrico", u"Rampla",
                     u"Residencial", u"Ribera", u"Rincón", u"Rinconada",
                     u"Sanatorio", u"Santuario", u"Sector", u"Sendera",
                     u"Sendero", u"Subida", u"Torrente", u"Tránsito",
                     u"Transversal", u"Trasera", u"Travesía", u"Urbanización",
                     u"Vecindario", u"Vereda", u"Viaducto", u"Viviendas",
                   ]

    DETERMINANTS = [ # Asturian
                     u" de", u" de la", u" del", u" de les", u" d'",
                     u" de los", u" de l'",

                     # Spanish (different from Asturian)
                     u" de las",
                     u""]


    DETERMINANTS = [ u" de", u" de la", u" del", u" de les",
                     u" de los", u" de las", u" d'", u" de l'", u"" ]

    SPACE_REDUCE = re.compile(r"\s+")
    PREFIX_REGEXP = re.compile(r"^(?P<prefix>(%s)(%s)?)\s?\b(?P<name>.+)" %
                                    ("|".join(APPELLATIONS),
                                     "|".join(DETERMINANTS)), re.IGNORECASE
                                                                 | re.UNICODE)

    # for IndexPageGenerator.upper_unaccent_string
    E_ACCENT = re.compile(r"[éèêëẽ]", re.IGNORECASE | re.UNICODE)
    I_ACCENT = re.compile(r"[íìîïĩ]", re.IGNORECASE | re.UNICODE)
    A_ACCENT = re.compile(r"[áàâäã]", re.IGNORECASE | re.UNICODE)
    O_ACCENT = re.compile(r"[óòôöõ]", re.IGNORECASE | re.UNICODE)
    U_ACCENT = re.compile(r"[úùûüũ]", re.IGNORECASE | re.UNICODE)
    N_ACCENT = re.compile(r"[ñ]", re.IGNORECASE | re.UNICODE)
    H_ACCENT = re.compile(r"[ḥ]", re.IGNORECASE | re.UNICODE)
    L_ACCENT = re.compile(r"[ḷ]", re.IGNORECASE | re.UNICODE)

    def __init__(self, language, locale_path):
        self.language = str(language)
        _install_language(language, locale_path)

    def upper_unaccent_string(self, s):
        s = self.E_ACCENT.sub("e", s)
        s = self.I_ACCENT.sub("i", s)
        s = self.A_ACCENT.sub("a", s)
        s = self.O_ACCENT.sub("o", s)
        s = self.U_ACCENT.sub("u", s)
        s = self.N_ACCENT.sub("n", s)
        s = self.H_ACCENT.sub("h", s)
        s = self.L_ACCENT.sub("l", s)
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
        return 'Asturianu (%s)' % self.language
