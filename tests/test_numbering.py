import tempfile
import unittest
from pathlib import Path

from screenshot_saver.numbering import clean_prefix, file_name, next_number, numeric_png_value


def _touch(folder: Path, *names: str) -> None:
    for name in names:
        (folder / name).write_bytes(b"")


class NumberingTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_empty_folder_starts_at_one(self):
        self.assertEqual(next_number(self.folder), 1)

    def test_continues_after_highest(self):
        _touch(self.folder, "1.png", "2.png", "5.png", "8.png")
        self.assertEqual(next_number(self.folder), 9)

    def test_ignores_non_numeric_names(self):
        _touch(
            self.folder,
            "3.png",
            "captura.png",
            "10.jpg",
            "0.png",
            "-4.png",
            "12 .png",
            "1 2.png",
            "７.png",       # dígito Unicode de ancho completo
            "20.png.txt",
        )
        self.assertEqual(next_number(self.folder), 4)

    def test_extension_is_case_insensitive_and_leading_zeros_allowed(self):
        _touch(self.folder, "6.PNG", "007.png")
        self.assertEqual(next_number(self.folder), 8)

    def test_folders_are_independent(self):
        other = self.folder / "otra"
        other.mkdir()
        _touch(self.folder, "1.png", "2.png")
        self.assertEqual(next_number(self.folder), 3)
        self.assertEqual(next_number(other), 1)

    def test_new_name_in_same_folder_starts_at_one(self):
        _touch(self.folder, "1.png", "2.png")
        self.assertEqual(file_name(next_number(self.folder, "Antonio"), "Antonio"), "Antonio 1.png")
        _touch(self.folder, "Antonio 1.png")
        self.assertEqual(next_number(self.folder, "Antonio"), 2)
        self.assertEqual(next_number(self.folder, ""), 3)  # la numeración sin nombre sigue igual

    def test_prefix_has_its_own_numbering(self):
        _touch(
            self.folder,
            "1.png", "2.png", "3.png",
            "Proyecto Final 1.png", "proyecto final 4.PNG",
            "Proyecto Final 2 7.png",   # otro nombre: "Proyecto Final 2"
            "Proyecto Final7.png",      # sin espacio: no cuenta
            "Otro 9.png",
        )
        self.assertEqual(next_number(self.folder, "Proyecto Final"), 5)
        self.assertEqual(next_number(self.folder, "Proyecto Final 2"), 8)
        self.assertEqual(next_number(self.folder, ""), 4)
        self.assertEqual(next_number(self.folder, "Nuevo"), 1)

    def test_prefix_with_regex_characters(self):
        _touch(self.folder, "Informe (v2) [final] 3.png", "Informe xv2x xfinalx 9.png")
        self.assertEqual(next_number(self.folder, "Informe (v2) [final]"), 4)

    def test_file_name_and_cleaning(self):
        self.assertEqual(file_name(1), "1.png")
        self.assertEqual(file_name(12, "Proyecto Final"), "Proyecto Final 12.png")
        self.assertEqual(file_name(3, "  Proyecto   Final  "), "Proyecto Final 3.png")
        self.assertEqual(file_name(2, "a/b:c?"), "abc 2.png")
        self.assertEqual(file_name(5, "   "), "5.png")
        self.assertEqual(clean_prefix("¿Año ñandú?"), "¿Año ñandú")

    def test_numeric_value(self):
        self.assertEqual(numeric_png_value("42.png"), 42)
        self.assertIsNone(numeric_png_value("42.png\n"))
        self.assertIsNone(numeric_png_value("a42.png"))


if __name__ == "__main__":
    unittest.main()
