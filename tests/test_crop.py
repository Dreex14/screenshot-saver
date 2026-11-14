import unittest

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QImage
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from screenshot_saver.ui.crop_dialog import (
    HANDLES,
    CropCanvas,
    CropDialog,
    move_edges,
    resize_edges,
    span_edges,
)

_app = QApplication.instance() or QApplication([])


class GeometryTests(unittest.TestCase):
    def test_resize_corner(self):
        self.assertEqual(resize_edges((0, 0, 100, 80), HANDLES["tl"], 10, 5, 100, 80, 4), (10, 5, 100, 80))
        self.assertEqual(resize_edges((0, 0, 100, 80), HANDLES["br"], -30, -20, 100, 80, 4), (0, 0, 70, 60))

    def test_resize_stays_inside_image(self):
        self.assertEqual(resize_edges((10, 10, 50, 50), HANDLES["tl"], -99, -99, 100, 80, 4), (0, 0, 50, 50))
        self.assertEqual(resize_edges((10, 10, 50, 50), HANDLES["br"], 999, 999, 100, 80, 4), (10, 10, 100, 80))

    def test_resize_respects_minimum_size(self):
        self.assertEqual(resize_edges((10, 10, 50, 50), HANDLES["l"], 100, 0, 100, 80, 4), (46, 10, 50, 50))
        self.assertEqual(resize_edges((10, 10, 50, 50), HANDLES["b"], 0, -100, 100, 80, 4), (10, 10, 50, 14))

    def test_edge_handle_moves_only_one_side(self):
        self.assertEqual(resize_edges((10, 10, 50, 50), HANDLES["r"], 7, 30, 100, 80, 4), (10, 10, 57, 50))

    def test_move_is_clamped(self):
        self.assertEqual(move_edges((10, 10, 50, 50), 5, 5, 100, 80), (15, 15, 55, 55))
        self.assertEqual(move_edges((10, 10, 50, 50), 999, -999, 100, 80), (60, 0, 100, 40))

    def test_span_any_direction(self):
        self.assertEqual(span_edges(80, 70, 20, 10, 100, 80), (20, 10, 80, 70))
        self.assertEqual(span_edges(-5, -5, 500, 500, 100, 80), (0, 0, 100, 80))


def _test_image() -> QImage:
    # 1000 × 600: cuadrante superior izquierdo rojo, resto azul.
    image = QImage(1000, 600, QImage.Format.Format_RGB32)
    image.fill(QColor("blue"))
    for y in range(300):
        for x in range(0, 500, 50):
            image.setPixelColor(x, y, QColor("red"))
    red = QImage(500, 300, QImage.Format.Format_RGB32)
    red.fill(QColor("red"))
    from PySide6.QtGui import QPainter
    painter = QPainter(image)
    painter.drawImage(0, 0, red)
    painter.end()
    return image


class CanvasMouseTests(unittest.TestCase):
    """Lienzo de 532 × 332: imagen de 1000 × 600 a escala 0,5 en (16, 16)."""

    def setUp(self):
        self.canvas = CropCanvas(_test_image())
        self.canvas.resize(532, 332)
        self.canvas.show()
        QApplication.processEvents()

    def tearDown(self):
        self.canvas.close()

    def drag(self, start, end):
        QTest.mousePress(self.canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(*start))
        QTest.mouseMove(self.canvas, QPoint(*end))
        QTest.mouseRelease(self.canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(*end))

    def test_starts_with_whole_image(self):
        self.assertEqual(self.canvas.selection(), QRect(0, 0, 1000, 600))

    def test_drag_corner_then_move(self):
        self.drag((16, 16), (116, 66))
        self.assertEqual(self.canvas.selection(), QRect(200, 100, 800, 500))
        self.drag((300, 200), (250, 175))
        self.assertEqual(self.canvas.selection(), QRect(100, 50, 800, 500))

    def test_drag_edge(self):
        self.drag((516, 166), (416, 300))  # borde derecho: solo cambia el ancho
        self.assertEqual(self.canvas.selection(), QRect(0, 0, 800, 600))

    def test_new_selection_outside_and_click_keeps_previous(self):
        self.drag((16, 16), (266, 166))     # recorte = cuadrante superior izquierdo
        self.assertEqual(self.canvas.selection(), QRect(500, 300, 500, 300))
        self.drag((100, 100), (60, 40))     # nuevo recorte, arrastrado hacia arriba
        self.assertEqual(self.canvas.selection(), QRect(88, 48, 80, 120))
        self.drag((400, 250), (400, 250))   # clic fuera del recorte: se conserva
        self.drag((30, 300), (31, 301))     # clic suelto fuera: se conserva
        self.assertEqual(self.canvas.selection(), QRect(88, 48, 80, 120))

    def test_double_click_inside_accepts(self):
        accepted = []
        self.canvas.accept_requested.connect(lambda: accepted.append(True))
        QTest.mouseDClick(self.canvas, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, QPoint(266, 166))
        self.assertEqual(accepted, [True])


class DialogTests(unittest.TestCase):
    def test_cropped_image_has_original_pixels(self):
        dialog = CropDialog(_test_image())
        dialog._canvas.set_selection((0, 0, 500, 300))
        cropped = dialog.cropped_image()
        self.assertEqual((cropped.width(), cropped.height()), (500, 300))
        self.assertEqual(cropped.pixelColor(499, 299).name(), "#ff0000")
        dialog._canvas.set_selection((500, 300, 1000, 600))
        self.assertEqual(dialog.cropped_image().pixelColor(0, 0).name(), "#0000ff")
        dialog.deleteLater()


if __name__ == "__main__":
    unittest.main()
