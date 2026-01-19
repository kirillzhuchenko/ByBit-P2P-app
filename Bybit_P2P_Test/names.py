import unicodedata
from difflib import SequenceMatcher

# Install required packages:
# pip install unidecode transliterate pykakasi

try:
    from unidecode import unidecode

    UNIDECODE_AVAILABLE = True
except ImportError:
    UNIDECODE_AVAILABLE = False
    print("Warning: Install 'unidecode' for better results")
    print("pip install unidecode")

try:
    from transliterate import translit

    TRANSLITERATE_AVAILABLE = True
except ImportError:
    TRANSLITERATE_AVAILABLE = False
    print("Warning: Install 'transliterate' for Russian support")
    print("pip install transliterate")

try:
    import pykakasi

    PYKAKASI_AVAILABLE = True
    kakasi = pykakasi.kakasi()
except ImportError:
    PYKAKASI_AVAILABLE = False
    print("Warning: Install 'pykakasi' for better Japanese support")
    print("pip install pykakasi")


def normalize_spanish(name):
    """Normalize Spanish accented characters"""
    replacements = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
        'ñ': 'n', 'Ñ': 'N',
        'ü': 'u', 'Ü': 'U',
        '¿': '', '¡': ''
    }

    for old, new in replacements.items():
        name = name.replace(old, new)

    return name


def transliterate_russian(name):
    """Convert Russian Cyrillic to Latin"""
    if TRANSLITERATE_AVAILABLE:
        try:
            return translit(name, 'ru', reversed=True)
        except:
            pass

    # Manual Cyrillic to Latin mapping as fallback
    cyrillic_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
        # Ukrainian-specific (lowercase)
        'є': 'ye', 'і': 'i', 'ї': 'yi', 'ґ': 'g',

        'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'E',
        'Ж': 'Zh', 'З': 'Z', 'И': 'I', 'Й': 'Y', 'К': 'K', 'Л': 'L', 'М': 'M',
        'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
        'Ф': 'F', 'Х': 'H', 'Ц': 'Ts', 'Ч': 'Ch', 'Ш': 'Sh', 'Щ': 'Shch',
        'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'Yu', 'Я': 'Ya',
        # Ukrainian-specific (uppercase)
        'Є': 'Ye', 'І': 'I', 'Ї': 'Yi', 'Ґ': 'G',
    }

    result = []
    for char in name:
        result.append(cyrillic_map.get(char, char))

    return ''.join(result)


def transliterate_arabic(name):
    """Convert Arabic to Latin"""
    if UNIDECODE_AVAILABLE:
        return unidecode(name)

    # Basic Arabic to Latin mapping
    arabic_map = {
        'ا': 'a', 'أ': 'a', 'إ': 'i', 'آ': 'a',
        'ب': 'b', 'ت': 't', 'ث': 'th', 'ج': 'j',
        'ح': 'h', 'خ': 'kh', 'د': 'd', 'ذ': 'dh',
        'ر': 'r', 'ز': 'z', 'س': 's', 'ش': 'sh',
        'ص': 's', 'ض': 'd', 'ط': 't', 'ظ': 'z',
        'ع': 'a', 'غ': 'gh', 'ف': 'f', 'ق': 'q',
        'ك': 'k', 'ل': 'l', 'م': 'm', 'ن': 'n',
        'ه': 'h', 'و': 'w', 'ي': 'y', 'ى': 'a',
        'ة': 'h', 'ؤ': 'u', 'ئ': 'i'
    }

    result = []
    for char in name:
        if char in arabic_map:
            result.append(arabic_map[char])
        elif not ('\u064B' <= char <= '\u065F'):  # Skip diacritics
            result.append(char)

    return ''.join(result)


def transliterate_korean(name):
    """Convert Korean to Latin (Romanization)"""
    if UNIDECODE_AVAILABLE:
        return unidecode(name)

    # Simplified Hangul romanization (basic mapping)
    # For production, consider using a proper library
    result = []
    for char in name:
        if '\uAC00' <= char <= '\uD7A3':  # Hangul syllables
            # This is a simplified approach
            code = ord(char) - 0xAC00
            initial = code // 588
            medial = (code % 588) // 28
            final = code % 28

            initials = ['g', 'kk', 'n', 'd', 'tt', 'r', 'm', 'b', 'pp',
                        's', 'ss', '', 'j', 'jj', 'ch', 'k', 't', 'p', 'h']
            medials = ['a', 'ae', 'ya', 'yae', 'eo', 'e', 'yeo', 'ye', 'o',
                       'wa', 'wae', 'oe', 'yo', 'u', 'wo', 'we', 'wi', 'yu',
                       'eu', 'ui', 'i']
            finals = ['', 'g', 'kk', 'gs', 'n', 'nj', 'nh', 'd', 'l', 'lg',
                      'lm', 'lb', 'ls', 'lt', 'lp', 'lh', 'm', 'b', 'bs',
                      's', 'ss', 'ng', 'j', 'ch', 'k', 't', 'p', 'h']

            romanized = initials[initial] + medials[medial] + finals[final]
            result.append(romanized)
        else:
            result.append(char)

    return ''.join(result)


def transliterate_japanese(name):
    """Convert Japanese (Hiragana/Katakana/Kanji) to Latin (Romaji)"""
    if PYKAKASI_AVAILABLE:
        try:
            result = kakasi.convert(name)
            return ''.join([item['hepburn'] for item in result])
        except:
            pass

    if UNIDECODE_AVAILABLE:
        return unidecode(name)

    # Basic Hiragana/Katakana mapping as fallback
    kana_map = {
        # Hiragana
        'あ': 'a', 'い': 'i', 'う': 'u', 'え': 'e', 'お': 'o',
        'か': 'ka', 'き': 'ki', 'く': 'ku', 'け': 'ke', 'こ': 'ko',
        'さ': 'sa', 'し': 'shi', 'す': 'su', 'せ': 'se', 'そ': 'so',
        'た': 'ta', 'ち': 'chi', 'つ': 'tsu', 'て': 'te', 'と': 'to',
        'な': 'na', 'に': 'ni', 'ぬ': 'nu', 'ね': 'ne', 'の': 'no',
        'は': 'ha', 'ひ': 'hi', 'ふ': 'fu', 'へ': 'he', 'ほ': 'ho',
        'ま': 'ma', 'み': 'mi', 'む': 'mu', 'め': 'me', 'も': 'mo',
        'や': 'ya', 'ゆ': 'yu', 'よ': 'yo',
        'ら': 'ra', 'り': 'ri', 'る': 'ru', 'れ': 're', 'ろ': 'ro',
        'わ': 'wa', 'を': 'wo', 'ん': 'n',
        # Katakana
        'ア': 'a', 'イ': 'i', 'ウ': 'u', 'エ': 'e', 'オ': 'o',
        'カ': 'ka', 'キ': 'ki', 'ク': 'ku', 'ケ': 'ke', 'コ': 'ko',
        'サ': 'sa', 'シ': 'shi', 'ス': 'su', 'セ': 'se', 'ソ': 'so',
        'タ': 'ta', 'チ': 'chi', 'ツ': 'tsu', 'テ': 'te', 'ト': 'to',
        'ナ': 'na', 'ニ': 'ni', 'ヌ': 'nu', 'ネ': 'ne', 'ノ': 'no',
        'ハ': 'ha', 'ヒ': 'hi', 'フ': 'fu', 'ヘ': 'he', 'ホ': 'ho',
        'マ': 'ma', 'ミ': 'mi', 'ム': 'mu', 'メ': 'me', 'モ': 'mo',
        'ヤ': 'ya', 'ユ': 'yu', 'ヨ': 'yo',
        'ラ': 'ra', 'リ': 'ri', 'ル': 'ru', 'レ': 're', 'ロ': 'ro',
        'ワ': 'wa', 'ヲ': 'wo', 'ン': 'n'
    }

    result = []
    for char in name:
        result.append(kana_map.get(char, char))

    return ''.join(result)


def detect_script(text):
    """Detect which script the text primarily uses"""
    for char in text:
        if '\u0400' <= char <= '\u04FF':
            return 'russian'
        elif '\u0600' <= char <= '\u06FF':
            return 'arabic'
        elif '\uAC00' <= char <= '\uD7A3':
            return 'korean'
        elif ('\u3040' <= char <= '\u309F') or ('\u30A0' <= char <= '\u30FF') or ('\u4E00' <= char <= '\u9FFF'):
            return 'japanese'
    return 'latin'


def normalize_name(name):
    """Basic normalization: lowercase, strip whitespace"""
    name = name.lower().strip()
    name = ' '.join(name.split())
    return name


def prepare_name_for_matching(name):
    """
    Full pipeline: detect script, transliterate, and normalize
    Handles Russian, Arabic, Korean, Japanese, and Spanish
    """
    # First, normalize Spanish characters
    name = normalize_spanish(name)

    # Detect script and transliterate
    script = detect_script(name)

    if script == 'russian':
        name = transliterate_russian(name)
    elif script == 'arabic':
        name = transliterate_arabic(name)
    elif script == 'korean':
        name = transliterate_korean(name)
    elif script == 'japanese':
        name = transliterate_japanese(name)

    # Final normalization
    name = normalize_name(name)

    # Remove non-alphanumeric except spaces
    name = ''.join(c if c.isalnum() or c.isspace() else ' ' for c in name)
    name = ' '.join(name.split())

    return name


def calculate_similarity(name1, name2):
    """Calculate similarity ratio between two names (0-1)"""
    return SequenceMatcher(None, name1, name2).ratio()


def names_match(name1, name2, threshold=0.85):
    """
    Check if two names match across Russian, Arabic, Korean, Japanese, and Spanish

    Args:
        name1: First name
        name2: Second name
        threshold: Similarity threshold (0-1), default 0.85

    Returns:
        tuple: (match_result, similarity_score, processed_name1, processed_name2)
    """
    # Prepare both names
    processed1 = prepare_name_for_matching(name1)
    processed2 = prepare_name_for_matching(name2)

    # Calculate similarity
    similarity = calculate_similarity(processed1, processed2)

    # Determine if they match
    match = similarity >= threshold

    return match, similarity


# Example usage
if __name__ == "__main__":
    # Test cases for the 5 supported languages
    test_pairs = [
        # Spanish
        ("José García", "Jose Garcia"),
        ("María López", "Maria Lopez"),
        ("Señor González", "Senor Gonzalez"),

        # Russian
        ("Москва", "Moskva"),
        ("Санкт-Петербург", "Sankt-Peterburg"),
        ("Владимир", "Vladimir"),

        # Arabic
        ("القاهرة", "Al-Qahirah"),
        ("محمد", "Muhammad"),
        ("الرياض", "Riyadh"),

        # Korean
        ("서울", "Seoul"),
        ("김민준", "Kim Min-jun"),
        ("부산", "Busan"),

        # Japanese
        ("東京", "Tokyo"),
        ("さくら", "Sakura"),
        ("ヤマダ", "Yamada"),
    ]

    print("Name Matching Results (Russian, Arabic, Korean, Japanese, Spanish)")
    print("=" * 80)

    for name1, name2 in test_pairs:
        match, score, proc1, proc2 = names_match(name1, name2, threshold=0.70)

        print(f"\nOriginal:  '{name1}' vs '{name2}'")
        print(f"Processed: '{proc1}' vs '{proc2}'")
        print(f"Match: {match} (Similarity: {score:.2%})")
        print("-" * 80)