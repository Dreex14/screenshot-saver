import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer
from PySide6.QtGui import QColor, QImage

from screenshot_saver import saver
from screenshot_saver.saver import ImageSaver, encode_png, write_numbered_file

_app = QCoreApplication.instance() or QCoreApplication([])


def _image(color: str, width: int = 40, height: int = 30) -> QImage:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor(color))
    return image


class WriteTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_first_file_is_one(self):
        path = write_numbered_file(b"data", self.folder)
        self.assertEqual(path.name, "1.png")
        self.assertEqual(path.read_bytes(), b"data")

    def test_never_overwrites_when_name_appears_meanwhile(self):
        # Simula que otro programa crea 3.png y 4.png entre el cálculo y la escritura.
        (self.folder / "2.png").write_bytes(b"old2")
        with mock.patch.object(saver, "next_number", return_value=3):
            (self.folder / "3.png").write_bytes(b"old3")
            (self.folder / "4.png").write_bytes(b"old4")
            path = write_numbered_file(b"new", self.folder)
        self.assertEqual(path.name, "5.png")
        self.assertEqual((self.folder / "3.png").read_bytes(), b"old3")
        self.assertEqual((self.folder / "4.png").read_bytes(), b"old4")

    def test_missing_folder_raises(self):
        with self.assertRaises(FileNotFoundError):
            write_numbered_file(b"x", self.folder / "no-existe")

    def test_error_messages(self):
        self.assertIn("no existe", saver.describe_error(FileNotFoundError(), "D:\\x"))
        self.assertIn("permiso", saver.describe_error(PermissionError(), "D:\\x"))

    def test_png_keeps_original_resolution(self):
        image = _image("#336699", 1920, 1080)
        data = encode_png(image)
        self.assertTrue(data.startswith(b"\x89PNG"))
        decoded = QImage.fromData(data, "PNG")
        self.assertEqual((decoded.width(), decoded.height()), (1920, 1080))
        self.assertEqual(decoded.pixelColor(5, 5).name(), "#336699")

    def test_fully_transparent_alpha_is_treated_as_opaque(self):
        image = QImage(10, 10, QImage.Format.Format_ARGB32)
        image.fill(QColor(200, 100, 50, 0))
        decoded = QImage.fromData(encode_png(image), "PNG")
        self.assertEqual(decoded.pixelColor(1, 1).alpha(), 255)

    def test_real_alpha_is_kept(self):
        image = QImage(10, 10, QImage.Format.Format_ARGB32)
        image.fill(QColor(200, 100, 50, 0))
        image.setPixelColor(0, 0, QColor(200, 100, 50, 128))
        decoded = QImage.fromData(encode_png(image), "PNG")
        self.assertEqual(decoded.pixelColor(1, 1).alpha(), 0)


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _run_jobs(self, jobs):
        worker = ImageSaver()
        results = []
        worker.job_saved.connect(lambda i, p: results.append(("ok", i, p)))
        worker.job_failed.connect(lambda i, m: results.append(("error", i, m)))
        for image, folder in jobs:
            worker.submit(image, str(folder))
        self.assertTrue(worker.shutdown(10))
        loop = QEventLoop()
        QTimer.singleShot(200, loop.quit)
        loop.exec()  # entrega las señales encoladas desde el hilo de trabajo
        return results

    def test_consecutive_and_identical_images_get_successive_names(self):
        same = _image("#ff0000")
        results = self._run_jobs([(same, self.folder), (same, self.folder), (_image("#00ff00"), self.folder)])
        self.assertEqual([Path(r[2]).name for r in results], ["1.png", "2.png", "3.png"])

    def test_each_job_keeps_its_folder(self):
        other = self.folder / "b"
        other.mkdir()
        results = self._run_jobs([(_image("red"), self.folder), (_image("blue"), other)])
        self.assertEqual(Path(results[0][2]), self.folder / "1.png")
        self.assertEqual(Path(results[1][2]), other / "1.png")

    def test_prefix_is_used_and_kept_per_job(self):
        (self.folder / "Proyecto Final 1.png").write_bytes(b"old")
        worker = ImageSaver()
        results = []
        worker.job_saved.connect(lambda i, p: results.append(Path(p).name))
        worker.submit(_image("red"), str(self.folder), "Proyecto Final")
        worker.submit(_image("red"), str(self.folder), "")
        worker.submit(_image("red"), str(self.folder), "Proyecto Final")
        self.assertTrue(worker.shutdown(10))
        loop = QEventLoop()
        QTimer.singleShot(200, loop.quit)
        loop.exec()
        self.assertEqual(results, ["Proyecto Final 2.png", "1.png", "Proyecto Final 3.png"])
        self.assertEqual((self.folder / "Proyecto Final 1.png").read_bytes(), b"old")

    def test_failure_is_reported(self):
        results = self._run_jobs([(_image("red"), self.folder / "falta")])
        self.assertEqual(results[0][0], "error")

    def test_read_only_folder_is_reported(self):
        # En Windows el atributo de solo lectura no impide crear archivos en
        # carpetas; se usa un archivo con ese nombre para forzar el fallo.
        blocker = self.folder / "1.png"
        blocker.mkdir()
        blocker.chmod(stat.S_IREAD)
        with mock.patch.object(saver, "_MAX_NAME_ATTEMPTS", 1), mock.patch.object(saver, "next_number", return_value=1):
            results = self._run_jobs([(_image("red"), self.folder)])
        self.assertEqual(results[0][0], "error")
        blocker.chmod(stat.S_IWRITE)


if __name__ == "__main__":
    unittest.main()
