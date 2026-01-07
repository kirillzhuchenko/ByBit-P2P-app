import unicodedata
from difflib import SequenceMatcher

try:
    from unidecode import unidecode
    from transliterate import translit

    TRANSLITERATE_AVAILABLE = True
except ImportError:
    TRANSLITERATE_AVAILABLE = False


def normalize_name(name):
    """Basic normalization: lowercase, strip whitespace, remove accents"""
    # Convert to lowercase
    name = name.lower().strip()

    # Remove extra whitespace
    name = ' '.join(name.split())

    # Normalize unicode (decompose accented characters)
    name = unicodedata.normalize('NFKD', name)

    return name


def transliterate_name(name, lang_code=None):
    """Convert non-Latin scripts to Latin characters"""
    if not TRANSLITERATE_AVAILABLE:
        return unidecode_fallback(name)

    # Try language-specific transliteration first
    if lang_code:
        try:
            return translit(name, lang_code, reversed=True)
        except:
            pass

    # Auto-detect and transliterate common scripts
    try:
        # Try Russian/Cyrillic
        if any('\u0400' <= c <= '\u04FF' for c in name):
            return translit(name, 'ru', reversed=True)

        # Try Georgian
        if any('\u10A0' <= c <= '\u10FF' for c in name):
            return translit(name, 'ka', reversed=True)

        # Try Greek
        if any('\u0370' <= c <= '\u03FF' for c in name):
            return translit(name, 'el', reversed=True)
    except:
        pass

    # Fallback to unidecode for Arabic and others
    return unidecode(name)


def unidecode_fallback(name):
    """Fallback method using only unidecode"""
    try:
        from unidecode import unidecode
        return unidecode(name)
    except:
        # If unidecode not available, just remove non-ASCII
        return ''.join(c for c in name if ord(c) < 128)


def prepare_name_for_matching(name, lang_code=None):
    """Full pipeline: normalize and transliterate"""
    # First normalize
    name = normalize_name(name)

    # Then transliterate non-Latin scripts
    name = transliterate_name(name, lang_code)

    # Final normalization after transliteration
    name = normalize_name(name)

    # Remove remaining non-alphanumeric except spaces
    name = ''.join(c if c.isalnum() or c.isspace() else ' ' for c in name)
    name = ' '.join(name.split())

    return name


def calculate_similarity(name1, name2):
    """Calculate similarity ratio between two names (0-1)"""
    return SequenceMatcher(None, name1, name2).ratio()


def names_match(name1, name2, threshold=0.85, lang_code1=None, lang_code2=None):
    """
    Check if two names match across different languages/scripts

    Args:
        name1: First name
        name2: Second name
        threshold: Similarity threshold (0-1), default 0.85
        lang_code1: Optional language code for name1 (e.g., 'ru', 'ka', 'ar')
        lang_code2: Optional language code for name2

    Returns:
        tuple: (match_result, similarity_score, processed_name1, processed_name2)
    """
    # Prepare both names
    processed1 = prepare_name_for_matching(name1, lang_code1)
    processed2 = prepare_name_for_matching(name2, lang_code2)

    # Calculate similarity
    similarity = calculate_similarity(processed1, processed2)

    # Determine if they match
    match = similarity >= threshold

    return match, similarity, processed1, processed2


# Example usage
if __name__ == "__main__":
    # Test cases with different scripts
    test_pairs = [
        ("José García", "Jose Garcia"),  # Spanish accents
        ("München", "Munchen"),  # German umlauts
        ("Москва", "Moskva"),  # Russian/Cyrillic
        ("Αθήνα", "Athina"),  # Greek
        ("თბილისი", "Tbilisi"),  # Georgian
        ("القاهرة", "Al-Qahirah"),  # Arabic
        ("北京", "Beijing"),  # Chinese
        ("John Smith", "Jon Smyth"),  # Similar but different
        ("Michael", "Mikhail"),  # Related names
    ]

    print("Name Matching Results:")
    print("=" * 80)

    for name1, name2 in test_pairs:
        match, score, proc1, proc2 = names_match(name1, name2, threshold=0.80)

        print(f"\nOriginal:  '{name1}' vs '{name2}'")
        print(f"Processed: '{proc1}' vs '{proc2}'")
        print(f"Match: {match} (Similarity: {score:.2%})")
        print("-" * 80)