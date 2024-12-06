import sys
import platform
import os
from PyQt5.QtWidgets import QApplication
from gpu_monitor_app import GPU_Monitor_App
from utils import parse_arguments


def main():
    # Parse command-line arguments
    args = parse_arguments()

    # Define threshold values
    thresholds = {
        'temperature': args.temp,
        'utilization': args.util,
        'memory_utilization': args.mem_util,
        'power_draw': args.power
    }

    sound_alert = args.sound
    sound_file = args.sound_file if args.sound else None

    # Enable High DPI scaling for better UI scaling
    from PyQt5.QtCore import Qt
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)

    # Optional: Set DPI Awareness on Windows
    if platform.system() == "Windows":
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)  # PROCESS_SYSTEM_DPI_AWARE
        except Exception:
            pass

    # Set a global font
    from PyQt5.QtGui import QFont
    global_font = QFont("Arial", 12)
    app.setFont(global_font)

    window = GPU_Monitor_App(thresholds, sound_alert, sound_file)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
