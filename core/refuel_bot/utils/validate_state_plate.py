import re

# Разрешённые кириллические буквы в российских номерах
RU_PLATE_LETTERS = "АВЕКМНОРСТУХ"


# Компилируем маски
PLATE_PATTERNS = [
    re.compile(rf"^[{RU_PLATE_LETTERS}]{{2}}\d{{5}}$"),  # АА12345
    re.compile(
        rf"^[{RU_PLATE_LETTERS}]\d{{3}}[{RU_PLATE_LETTERS}]{{2}}\d{{2}}$"
    ),  # А123ВС45
    re.compile(
        rf"^[{RU_PLATE_LETTERS}]\d{{3}}[{RU_PLATE_LETTERS}]{{2}}\d{{3}}$"
    ),  # А123ВС456
]

# Маппинг латиницы -> кириллица для визуально совпадающих букв
LAT2CYR = str.maketrans(
    {
        "A": "А",
        "B": "В",
        "E": "Е",
        "K": "К",
        "M": "М",
        "H": "Н",
        "O": "О",
        "P": "Р",
        "C": "С",
        "T": "Т",
        "Y": "У",
        "X": "Х",
    }
)


def normalize_plate_input(s: str) -> str:
    """
    Убирает пробелы/дефисы, приводит к верхнему регистру и заменяет латиницу на кириллицу.
    """
    s = (s or "").strip().upper().replace(" ", "").replace("-", "")
    return s.translate(LAT2CYR)


def is_valid_plate(plate: str) -> bool:
    return any(p.fullmatch(plate) for p in PLATE_PATTERNS)
