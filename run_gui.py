"""WordAgent GUI - AI Requirement Traceability System

Usage:
    python run_gui.py
"""

import sys
import os

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

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
