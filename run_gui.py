"""WordAgent GUI - AI Requirement Traceability System

Usage:
    python run_gui.py
"""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Fix Qt platform plugin discovery on Windows
import PySide6
pyside6_dir = os.path.dirname(PySide6.__file__)
plugin_path = os.path.join(pyside6_dir, "plugins", "platforms")
if os.path.isdir(plugin_path):
    os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = plugin_path

from PySide6.QtWidgets import QApplication
from app.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("WordAgent")
    app.setOrganizationName("WordAgent")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
