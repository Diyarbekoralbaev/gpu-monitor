def apply_dark_theme(window):
    dark_stylesheet = """
        QWidget {
            background-color: #2b2b2b;
            color: #f0f0f0;
            font-family: Arial;
            font-size: 12px;
        }
        QTableWidget {
            background-color: #3c3f41;
            gridline-color: #555555;
        }
        QHeaderView::section {
            background-color: #45484a;
            padding: 4px;
            border: 1px solid #6c6c6c;
        }
        QLineEdit, QSpinBox, QDoubleSpinBox {
            background-color: #3c3f41;
            border: 1px solid #555555;
            padding: 2px;
        }
        QPushButton {
            background-color: #5c5c5c;
            border: 1px solid #3a3a3a;
            padding: 5px;
            border-radius: 3px;
        }
        QPushButton:hover {
            background-color: #6c6c6c;
        }
        QCheckBox {
            spacing: 5px;
        }
        QMenu {
            background-color: #2b2b2b;
            color: #f0f0f0;
        }
        QMessageBox {
            background-color: #2b2b2b;
            color: #f0f0f0;
        }
        pg.PlotWidget {
            background-color: #3c3f41;
        }
    """
    window.setStyleSheet(dark_stylesheet)


def apply_light_theme(window):
    light_stylesheet = """
        QWidget {
            background-color: #ffffff;
            color: #000000;
            font-family: Arial;
            font-size: 12px;
        }
        QTableWidget {
            background-color: #ffffff;
            gridline-color: #cccccc;
        }
        QHeaderView::section {
            background-color: #f0f0f0;
            padding: 4px;
            border: 1px solid #cccccc;
        }
        QLineEdit, QSpinBox, QDoubleSpinBox {
            background-color: #ffffff;
            border: 1px solid #cccccc;
            padding: 2px;
        }
        QPushButton {
            background-color: #e0e0e0;
            border: 1px solid #b0b0b0;
            padding: 5px;
            border-radius: 3px;
        }
        QPushButton:hover {
            background-color: #d0d0d0;
        }
        QCheckBox {
            spacing: 5px;
        }
        QMenu {
            background-color: #ffffff;
            color: #000000;
        }
        QMessageBox {
            background-color: #ffffff;
            color: #000000;
        }
        pg.PlotWidget {
            background-color: #ffffff;
        }
    """
    window.setStyleSheet(light_stylesheet)
