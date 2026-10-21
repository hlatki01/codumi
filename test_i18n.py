"""Translation coverage and Windows display-language selection."""
import ctypes
from string import Formatter
import unittest
from unittest.mock import patch

from i18n import CATALOGS, Translator, normalize_language, windows_language
from pet import PETS
from sessions import STATES


class LanguageTests(unittest.TestCase):
    def test_regional_variants_and_fallback(self):
        for code,expected in [("pt-BR","pt"),("pt_PT","pt"),("en-GB","en"),
                              ("es-MX","es"),("fr-CA","fr"),("de-DE","de"),
                              ("it-IT","it"),("ja-JP","en"),("", "en"),(None,"en")]:
            self.assertEqual(normalize_language(code),expected)

    def test_catalogs_cover_every_control_state_and_pet(self):
        reference=CATALOGS["en"]
        for language,catalog in CATALOGS.items():
            with self.subTest(language=language):
                self.assertEqual(set(reference),set(catalog))
                for key,text in catalog.items():
                    self.assertTrue(text.strip(),key)
                    placeholders=lambda value:{field for _,field,_,_ in Formatter().parse(value) if field}
                    self.assertEqual(placeholders(reference[key]),placeholders(text),key)
                for state in STATES:
                    self.assertIn("state."+state,catalog)
                for pet_id in PETS:
                    self.assertIn("pet."+pet_id,catalog)

    def test_translates_events_but_preserves_user_content(self):
        english=Translator("en-US")
        self.assertEqual(english.event(CATALOGS["pt"]["event.complete"]),"Turn completed")
        self.assertEqual(english.event("shell_command"),"shell_command")
        self.assertEqual(english.warning(CATALOGS["pt"]["session_unavailable"]),
                         CATALOGS["en"]["session_unavailable"])
        self.assertEqual(english("counts",active=2,resting=4),"Active: 2 · Resting: 4")

    def test_uses_windows_display_language_api(self):
        with patch("i18n.sys.platform","win32"), patch.object(
            ctypes.windll.kernel32,"GetUserDefaultUILanguage",return_value=0x0416):
            self.assertEqual(windows_language(),"pt-BR")
            self.assertEqual(Translator().language,"pt")
        with patch("i18n.sys.platform","win32"), patch.object(
            ctypes.windll.kernel32,"GetUserDefaultUILanguage",return_value=0xffff):
            self.assertEqual(Translator().language,"en")


if __name__=="__main__":
    unittest.main()
