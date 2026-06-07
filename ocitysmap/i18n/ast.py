import re
from . import i18n, _install_language

class i18n_ast_generic(i18n):

    APPELLATIONS = [ # Asturian
                     "Accesu", "Autopista", "Autovia", "Avenida",
                     "Baxada", "Barrancu", "Barriu", "Barriada",
                     "Biblioteca", "Cai", "Caleya",
                     "Calzada", "Camín", "Carretera", "Cuesta",
                     "Estación", "Hospital", "Iglesia", "Monasteriu",
                     "Monumentu", "Muelle", "Muséu",
                     "Palaciu", "Parque", "Pasadizu", "Pasaxe",
                     "Paséu", "Planta", "Plaza", "Polígonu",
                     "Ronda", "Travesía", "Urbanización", "Via",
                     "Xardín", "Xardinos",

                     # Spanish (different from Asturian)
                     "Acceso", "Acequia", "Alameda", "Alquería",
                     "Andador", "Angosta", "Apartamentos", "Apeadero",
                     "Arboleda", "Arrabal", "Arroyo", "Autovía",
                     "Bajada", "Balneario", "Banda",
                     "Barranco", "Barranquil", "Barrio", "Bloque",
                     "Brazal", "Bulevar", "Calle", "Calleja",
                     "Callejón", "Callejuela", "Callizo",
                     "Camino", "Camping", "Cantera", "Cantina",
                     "Cantón", "Carrera", "Carrero", "Carreterín",
                     "Carretil", "Carril", "Caserío", "Chalet",
                     "Cinturón", "Circunvalación", "Cobertizo",
                     "Colonia", "Complejo", "Conjunto", "Convento",
                     "Cooperativa", "Corral", "Corralillo", "Corredor",
                     "Cortijo", "Costanilla", "Costera", "Cuadra",
                     "Dehesa", "Demarcación", "Diagonal",
                     "Diseminado", "Edificio", "Empresa", "Entrada",
                     "Escalera", "Escalinata", "Espalda", "Estación",
                     "Estrada", "Explanada", "Extramuros", "Extrarradio",
                     "Fábrica", "Galería", "Glorieta", "Gran Vía",
                     "Granja", "Hipódromo", "Jardín", "Ladera",
                     "Llanura", "Malecón", "Mercado", "Mirador",
                     "Monasterio", "Núcleo", "Palacio",
                     "Pantano", "Paraje", "Particular",
                     "Partida", "Pasadizo", "Pasaje", "Paseo",
                     "Paseo marítimo", "Pasillo", "Plaza", "Plazoleta",
                     "Plazuela", "Poblado", "Polígono", "Polígono industrial",
                     "Portal", "Pórtico", "Portillo", "Prazuela",
                     "Prolongación", "Pueblo", "Puente", "Puerta",
                     "Puerto", "Punto kilométrico", "Rampla",
                     "Residencial", "Ribera", "Rincón", "Rinconada",
                     "Sanatorio", "Santuario", "Sector", "Sendera",
                     "Sendero", "Subida", "Torrente", "Tránsito",
                     "Transversal", "Trasera", "Travesía", "Urbanización",
                     "Vecindario", "Vereda", "Viaducto", "Viviendas",
                   ]

    DETERMINANTS = [ # Asturian
                     " de", " de la", " del", " de les", " d'",
                     " de los", " de l'",

                     # Spanish (different from Asturian)
                     " de las",
                     ""]


    DETERMINANTS = [ " de", " de la", " del", " de les",
                     " de los", " de las", " d'", " de l'", "" ]

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
