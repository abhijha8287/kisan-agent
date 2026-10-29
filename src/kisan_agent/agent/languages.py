from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    name: str
    native_name: str
    speech_code: str  # BCP 47 tag used by the browser's speech recognition


SUPPORTED_LANGUAGES: tuple[Language, ...] = (
    Language("English", "English", "en-IN"),
    Language("Hindi", "हिन्दी", "hi-IN"),
    Language("Marathi", "मराठी", "mr-IN"),
    Language("Bengali", "বাংলা", "bn-IN"),
    Language("Telugu", "తెలుగు", "te-IN"),
    Language("Tamil", "தமிழ்", "ta-IN"),
    Language("Kannada", "ಕನ್ನಡ", "kn-IN"),
    Language("Gujarati", "ગુજરાતી", "gu-IN"),
    Language("Punjabi", "ਪੰਜਾਬੀ", "pa-IN"),
)

LANGUAGE_NAMES = frozenset(language.name for language in SUPPORTED_LANGUAGES)
