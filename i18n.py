"""Windows display-language detection and UI translations, with English fallback."""
import ctypes
import json
import locale
from pathlib import Path
import sys

APP_NAME = "codumi"
CATALOGS = json.loads(Path(__file__).with_name("locales.json").read_text(encoding="utf-8"))
LANGUAGE_NAMES = {"en":"English","pt":"Português","es":"Español","fr":"Français","de":"Deutsch","it":"Italiano"}
EVENT_KEYS = {text:key for key,text in CATALOGS["pt"].items() if key.startswith("event.")}


def windows_language():
    if sys.platform=="win32":
        try:
            api=ctypes.windll.kernel32.GetUserDefaultUILanguage
            api.argtypes=[]
            api.restype=ctypes.c_ushort
            language_id=api()
            name=locale.windows_locale.get(language_id)
            if name:
                return name.replace("_","-")
        except (AttributeError,OSError):
            pass
    return "en"


def normalize_language(language):
    base=language.replace("_","-").split("-")[0].lower() if isinstance(language,str) else "en"
    return base if base in CATALOGS else "en"


class Translator:
    def __init__(self, language=None):
        self.language=normalize_language(windows_language() if language is None else language)

    def __call__(self, key, **values):
        text=CATALOGS[self.language].get(key,CATALOGS["en"][key])
        return text.format(**values)

    def state(self, state):
        return self("state."+state)

    def pet_name(self, pet_id):
        return self("pet."+pet_id)

    def event(self, text):
        key=EVENT_KEYS.get(text)
        return self(key) if key else text

    def warning(self, text):
        return (text.replace(CATALOGS["pt"]["session_unavailable"],self("session_unavailable"))
                    .replace(CATALOGS["pt"]["read_prefix"],self("read_prefix")))
