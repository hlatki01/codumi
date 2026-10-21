"""Catalog checks keep every selectable native sprite valid and distinct."""
import re
import unittest
from pet import PETS, pet_palette


class PetCatalogTests(unittest.TestCase):
    def test_ten_distinct_silhouettes_and_names(self):
        self.assertEqual(len(PETS),10)
        self.assertEqual(len({spec[0] for spec in PETS.values()}),10)
        self.assertEqual(len({spec[3] for spec in PETS.values()}),10)

    def test_every_sprite_fits_avatar_and_uses_known_colors(self):
        for pet_id,(_,_,_,pixels) in PETS.items():
            with self.subTest(pet=pet_id):
                self.assertTrue(1<=len(pixels)<=16)
                self.assertTrue(all(len(row)==16 for row in pixels))
                self.assertTrue(set("".join(pixels))<=set(" .bae"))
                self.assertIn("e","".join(pixels))
                for state in ("working","sleeping","error"):
                    for provider in ("Claude","Codex"):
                        palette=pet_palette(pet_id,state,provider)
                        self.assertTrue(all(re.fullmatch(r"#[0-9a-fA-F]{6}",color) for color in palette.values()))


if __name__=="__main__":
    unittest.main()
