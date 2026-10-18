"""
SteamVibe - Video Game Analytics & DSA Benchmarking Suite
Main Application Entry Point
"""

import os
import sys

# Ensure workspace root is in sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont, QIcon
from PyQt6.QtWidgets import QApplication

from ui.main_window import MainWindow


def main() -> None:
    # High DPI screen support
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("SteamVibe Analytics Suite")
    app.setOrganizationName("CS200 Data Structures & Algorithms")

    # Default typography
    default_font = QFont("Segoe UI", 10)
    app.setFont(default_font)

    # Initialize and show main window
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
