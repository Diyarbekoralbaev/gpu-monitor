import sys
import subprocess
import platform
import os
import signal
from collections import deque

from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QTabWidget, QVBoxLayout,
    QTableWidget, QTableWidgetItem, QMessageBox, QFileDialog,
    QLabel, QLineEdit, QPushButton, QCheckBox, QHBoxLayout, QGridLayout, QHeaderView, QMenu
)
from PyQt5.QtCore import Qt, QTimer, QUrl
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtMultimedia import QSoundEffect

import pyqtgraph as pg
import pynvml
import numpy as np

try:
    from plyer import notification
except ImportError:
    notification = None

from themes import apply_light_theme, apply_dark_theme
from utils import detect_gpu, get_gpu_name, get_nvidia_stats


class GPU_Monitor_App(QMainWindow):
    def __init__(self, thresholds, sound_alert, sound_file):
        super().__init__()

        # Initialize window properties
        self.setWindowTitle("GPU Monitor")
        self.setGeometry(100, 100, 1400, 900)
        self.setWindowIcon(QIcon('gpu_icon.png'))

        self.thresholds = thresholds
        self.sound_alert = sound_alert
        self.sound_file = sound_file

        self.current_theme = 'Light'  # Default theme
        apply_light_theme(self)

        # Alert states to avoid repetitive notifications
        self.alert_states = {
            'temperature': False,
            'utilization': False,
            'memory_utilization': False,
            'power_draw': False
        }

        # Detect GPU
        self.gpu_type = detect_gpu()
        if self.gpu_type != 'NVIDIA':
            QMessageBox.critical(self, "GPU Detection Error",
                                 "No supported NVIDIA GPU found or NVIDIA drivers not installed.")
            sys.exit(1)

        # Initialize pynvml
        try:
            pynvml.nvmlInit()
        except pynvml.NVMLError as e:
            QMessageBox.critical(self, "pynvml Initialization Error",
                                 f"Failed to initialize pynvml: {e}")
            sys.exit(1)

        self.device_count = pynvml.nvmlDeviceGetCount()

        # Data buffers for graphs
        self.buffer_size = 60
        self.data_buffers = []
        for _ in range(self.device_count):
            buffer = {
                'time': deque(maxlen=self.buffer_size),
                'temperature': deque(maxlen=self.buffer_size),
                'utilization': deque(maxlen=self.buffer_size),
                'memory_utilization': deque(maxlen=self.buffer_size),
                'power_draw': deque(maxlen=self.buffer_size)
            }
            self.data_buffers.append(buffer)

        # Initialize QSoundEffect if sound alerts are enabled
        self.init_sound_effect()

        # Create UI
        self.init_ui()

        # Timer to update stats
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_stats)
        self.timer.start(1000)

    def init_sound_effect(self):
        self.sound_effect = None
        if self.sound_alert:
            if self.sound_file and os.path.isfile(self.sound_file):
                self.sound_effect = QSoundEffect()
                self.sound_effect.setSource(QUrl.fromLocalFile(self.sound_file))
                self.sound_effect.setVolume(0.5)
            else:
                # Try default beep.wav
                default_beep = os.path.join(os.path.dirname(__file__), "beep.wav")
                if os.path.isfile(default_beep):
                    self.sound_effect = QSoundEffect()
                    self.sound_effect.setSource(QUrl.fromLocalFile(default_beep))
                    self.sound_effect.setVolume(0.5)
                else:
                    QMessageBox.warning(
                        self,
                        "Sound File Missing",
                        "Sound alerts are enabled but no valid sound file is selected or beep.wav is missing."
                    )
                    self.sound_alert = False

    def init_ui(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # GPU Stats Tab
        self.stats_tab = QWidget()
        self.tabs.addTab(self.stats_tab, "GPU Stats")
        self.init_stats_tab()

        # GPU Processes Tab
        self.processes_tab = QWidget()
        self.tabs.addTab(self.processes_tab, "GPU Processes")
        self.init_processes_tab()

        # Dashboard Tab
        self.dashboard_tab = QWidget()
        self.tabs.addTab(self.dashboard_tab, "Dashboard")
        self.init_dashboard_tab()

        # Settings Tab
        self.settings_tab = QWidget()
        self.tabs.addTab(self.settings_tab, "Settings")
        self.init_settings_tab()

    def init_stats_tab(self):
        layout = QVBoxLayout()
        title = QLabel("GPU Statistics")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.stats_table = QTableWidget()
        self.stats_table.setColumnCount(9)
        self.stats_table.setHorizontalHeaderLabels([
            "GPU Index", "Name", "Util (%)", "Mem Usage (MB)",
            "Mem Util (%)", "Temp (°C)", "Power (W)",
            "Fan (%)", "Clock (MHz)"
        ])
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.stats_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.stats_table.setAlternatingRowColors(True)
        self.stats_table.setFont(QFont("Arial", 12))

        layout.addWidget(self.stats_table)
        self.stats_tab.setLayout(layout)

    def init_processes_tab(self):
        layout = QVBoxLayout()
        title = QLabel("Active GPU Processes")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        self.process_tabs = QTabWidget()
        for i in range(self.device_count):
            gpu_process_tab = QWidget()
            gpu_layout = QVBoxLayout()

            table = QTableWidget()
            table.setColumnCount(4)
            table.setHorizontalHeaderLabels(["PID", "Type", "Process Name", "GPU Memory Usage (MB)"])
            table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
            table.setEditTriggers(QTableWidget.NoEditTriggers)
            table.setSelectionBehavior(QTableWidget.SelectRows)
            table.setContextMenuPolicy(Qt.CustomContextMenu)
            table.customContextMenuRequested.connect(lambda pos, t=table: self.open_context_menu(pos, t))
            table.setAlternatingRowColors(True)
            table.setFont(QFont("Arial", 12))
            table.horizontalHeaderItem(1).setToolTip("Type of process: Graphics or Compute")

            gpu_layout.addWidget(table)
            gpu_process_tab.setLayout(gpu_layout)
            self.process_tabs.addTab(gpu_process_tab, f"GPU {i} Processes")

        layout.addWidget(self.process_tabs)
        self.processes_tab.setLayout(layout)

    def init_dashboard_tab(self):
        layout = QVBoxLayout()
        title = QLabel("GPU Dashboard")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        grid_layout = QGridLayout()

        for i in range(self.device_count):
            gpu_label = QLabel(f"GPU {i} - {get_gpu_name(i)}")
            gpu_label.setFont(QFont("Arial", 14, QFont.Bold))
            grid_layout.addWidget(gpu_label, i * 4, 0, 1, 2)

            # Temperature Plot
            temp_plot = pg.PlotWidget(title="Temperature (°C)")
            temp_plot.setYRange(0, max(self.thresholds['temperature'] * 1.5, 100))
            temp_plot.showGrid(x=True, y=True)
            temp_curve = temp_plot.plot(pen=pg.mkPen(color='r', width=2))
            grid_layout.addWidget(temp_plot, i * 4 + 1, 0)

            # Utilization Plot
            util_plot = pg.PlotWidget(title="GPU Utilization (%)")
            util_plot.setYRange(0, 100)
            util_plot.showGrid(x=True, y=True)
            util_curve = util_plot.plot(pen=pg.mkPen(color='g', width=2))
            grid_layout.addWidget(util_plot, i * 4 + 1, 1)

            # Memory Utilization Plot
            mem_util_plot = pg.PlotWidget(title="Memory Utilization (%)")
            mem_util_plot.setYRange(0, 100)
            mem_util_plot.showGrid(x=True, y=True)
            mem_util_curve = mem_util_plot.plot(pen=pg.mkPen(color='b', width=2))
            grid_layout.addWidget(mem_util_plot, i * 4 + 2, 0)

            # Power Draw Plot
            power_plot = pg.PlotWidget(title="Power Draw (W)")
            power_plot.setYRange(0, max(self.thresholds['power_draw'] * 1.5, 500))
            power_plot.showGrid(x=True, y=True)
            power_curve = power_plot.plot(pen=pg.mkPen(color='y', width=2))
            grid_layout.addWidget(power_plot, i * 4 + 2, 1)

            # Store plot widgets and curves
            self.data_buffers[i]['temperature_plot'] = temp_plot
            self.data_buffers[i]['temperature_curve'] = temp_curve
            self.data_buffers[i]['utilization_plot'] = util_plot
            self.data_buffers[i]['utilization_curve'] = util_curve
            self.data_buffers[i]['memory_utilization_plot'] = mem_util_plot
            self.data_buffers[i]['memory_utilization_curve'] = mem_util_curve
            self.data_buffers[i]['power_draw_plot'] = power_plot
            self.data_buffers[i]['power_draw_curve'] = power_curve

        layout.addLayout(grid_layout)
        self.dashboard_tab.setLayout(layout)

    def init_settings_tab(self):
        layout = QGridLayout()

        title = QLabel("Settings")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title, 0, 0, 1, 3)

        # Temperature Threshold
        temp_label = QLabel("Temperature Threshold (°C):")
        self.temp_input = QLineEdit(str(self.thresholds['temperature']))
        self.temp_input.setPlaceholderText("e.g., 80")
        layout.addWidget(temp_label, 1, 0)
        layout.addWidget(self.temp_input, 1, 1)

        # Utilization Threshold
        util_label = QLabel("Utilization Threshold (%):")
        self.util_input = QLineEdit(str(self.thresholds['utilization']))
        self.util_input.setPlaceholderText("e.g., 90")
        layout.addWidget(util_label, 2, 0)
        layout.addWidget(self.util_input, 2, 1)

        # Memory Utilization Threshold
        mem_util_label = QLabel("Memory Utilization Threshold (%):")
        self.mem_util_input = QLineEdit(str(self.thresholds['memory_utilization']))
        self.mem_util_input.setPlaceholderText("e.g., 90")
        layout.addWidget(mem_util_label, 3, 0)
        layout.addWidget(self.mem_util_input, 3, 1)

        # Power Draw Threshold
        power_label = QLabel("Power Draw Threshold (W):")
        self.power_input = QLineEdit(str(self.thresholds['power_draw']))
        self.power_input.setPlaceholderText("e.g., 250")
        layout.addWidget(power_label, 4, 0)
        layout.addWidget(self.power_input, 4, 1)

        # Sound Alert Checkbox
        self.sound_checkbox = QCheckBox("Enable Sound Alerts")
        self.sound_checkbox.setChecked(self.sound_alert)
        layout.addWidget(self.sound_checkbox, 5, 0, 1, 2)

        # Sound File Selection
        sound_file_label = QLabel("Sound File:")
        self.sound_file_input = QLineEdit(self.sound_file if self.sound_file else "")
        self.sound_file_input.setPlaceholderText("Path to WAV file")
        self.sound_file_input.setReadOnly(True)
        self.sound_file_input.setStyleSheet("background-color: #f0f0f0;")
        browse_button = QPushButton("Browse")
        browse_button.clicked.connect(self.browse_sound_file)
        layout.addWidget(sound_file_label, 6, 0)
        layout.addWidget(self.sound_file_input, 6, 1)
        layout.addWidget(browse_button, 6, 2)

        # Theme Toggle
        theme_label = QLabel("Theme:")
        self.theme_checkbox = QCheckBox("Dark Mode")
        self.theme_checkbox.setChecked(self.current_theme == 'Dark')
        self.theme_checkbox.stateChanged.connect(self.toggle_theme)
        layout.addWidget(theme_label, 7, 0)
        layout.addWidget(self.theme_checkbox, 7, 1)

        # Save Button
        save_button = QPushButton("Save Settings")
        save_button.clicked.connect(self.save_settings)
        layout.addWidget(save_button, 8, 0, 1, 3)

        layout.setRowStretch(9, 1)
        self.settings_tab.setLayout(layout)

    def browse_sound_file(self):
        options = QFileDialog.Options()
        options |= QFileDialog.ReadOnly
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Sound File",
            "",
            "WAV Files (*.wav);;All Files (*)",
            options=options
        )
        if file_path:
            if file_path.lower().endswith('.wav'):
                self.sound_file_input.setText(file_path)
                QMessageBox.information(self, "File Selected", f"Selected file:\n{file_path}")
                if self.sound_effect:
                    self.sound_effect.setSource(QUrl.fromLocalFile(file_path))
            else:
                QMessageBox.warning(self, "Invalid File", "Please select a valid WAV file.")

    def save_settings(self):
        try:
            temp = float(self.temp_input.text())
            util = float(self.util_input.text())
            mem_util = float(self.mem_util_input.text())
            power = float(self.power_input.text())
            sound = self.sound_checkbox.isChecked()
            sound_file = self.sound_file_input.text() if sound else None

            self.thresholds = {
                'temperature': temp,
                'utilization': util,
                'memory_utilization': mem_util,
                'power_draw': power
            }
            self.sound_alert = sound
            self.sound_file = sound_file

            # Update sound effect
            if self.sound_alert:
                if self.sound_file and os.path.isfile(self.sound_file):
                    if not self.sound_effect:
                        self.sound_effect = QSoundEffect()
                    self.sound_effect.setSource(QUrl.fromLocalFile(self.sound_file))
                    self.sound_effect.setVolume(0.5)
                else:
                    default_beep = os.path.join(os.path.dirname(__file__), "beep.wav")
                    if os.path.isfile(default_beep):
                        if not self.sound_effect:
                            self.sound_effect = QSoundEffect()
                        self.sound_effect.setSource(QUrl.fromLocalFile(default_beep))
                        self.sound_effect.setVolume(0.5)
                    else:
                        QMessageBox.warning(
                            self,
                            "Sound File Missing",
                            "Sound alerts are enabled but no valid sound file is selected or beep.wav is missing."
                        )
                        self.sound_alert = False
                        self.sound_effect = None
            else:
                self.sound_effect = None

            QMessageBox.information(self, "Settings Saved", "Thresholds and settings have been updated.")
        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid numeric values for thresholds.")
        except AttributeError as e:
            QMessageBox.warning(self, "Sound Effect Error", f"An error occurred: {e}")

    def toggle_theme(self):
        if self.theme_checkbox.isChecked():
            apply_dark_theme(self)
            self.current_theme = 'Dark'
        else:
            apply_light_theme(self)
            self.current_theme = 'Light'

    def open_context_menu(self, position, table):
        indexes = table.selectedIndexes()
        if not indexes:
            return

        row = indexes[0].row()
        pid_item = table.item(row, 0)
        if not pid_item:
            return

        pid = pid_item.text()
        process_name_item = table.item(row, 2)
        process_name = process_name_item.text() if process_name_item else "Unknown"

        menu = QMenu()
        kill_action = menu.addAction("Kill Process")
        action = menu.exec_(table.viewport().mapToGlobal(position))

        if action == kill_action:
            self.confirm_and_kill_process(pid, process_name)

    def confirm_and_kill_process(self, pid, process_name):
        reply = QMessageBox.question(
            self, 'Kill Process',
            f"Are you sure you want to kill process '{process_name}' (PID: {pid})?",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                pid_int = int(pid)
                if platform.system() == 'Windows':
                    import ctypes
                    PROCESS_TERMINATE = 1
                    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid_int)
                    if not handle:
                        raise OSError("Could not open process.")
                    result = ctypes.windll.kernel32.TerminateProcess(handle, -1)
                    ctypes.windll.kernel32.CloseHandle(handle)
                    if not result:
                        raise OSError("Failed to terminate process.")
                else:
                    os.kill(pid_int, signal.SIGTERM)
                QMessageBox.information(self, "Process Killed",
                                        f"Process '{process_name}' (PID: {pid}) has been terminated.")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"An error occurred: {e}")

    def send_desktop_notification(self, title, message):
        if notification:
            try:
                notification.notify(
                    title=title,
                    message=message,
                    app_name="GPU Monitor",
                    timeout=5
                )
            except Exception as e:
                print(f"Failed to send notification: {e}")
        else:
            print("Notification not available. Install 'plyer' for notifications.")

    def play_sound_alert(self):
        if self.sound_effect:
            if self.sound_effect.status() != QSoundEffect.Ready:
                # Reset source if needed
                if self.sound_file and os.path.isfile(self.sound_file):
                    self.sound_effect.setSource(QUrl.fromLocalFile(self.sound_file))
                else:
                    default_beep = os.path.join(os.path.dirname(__file__), "beep.wav")
                    if os.path.isfile(default_beep):
                        self.sound_effect.setSource(QUrl.fromLocalFile(default_beep))
                    else:
                        print("No valid sound file found.")
                        return
            self.sound_effect.play()

    def check_alerts(self, stats):
        for stat in stats:
            alerts_triggered = []
            gpu_index = stat.get('gpu_index', 'N/A')

            # Temperature Alert
            temp = stat.get('temperature', 0)
            if temp > self.thresholds['temperature'] and not self.alert_states['temperature']:
                alert = f"GPU {gpu_index} temperature {temp}°C exceeds {self.thresholds['temperature']}°C"
                alerts_triggered.append(alert)
                self.alert_states['temperature'] = True
            elif temp <= self.thresholds['temperature']:
                self.alert_states['temperature'] = False

            # Utilization Alert
            util = stat.get('utilization', 0)
            if util > self.thresholds['utilization'] and not self.alert_states['utilization']:
                alert = f"GPU {gpu_index} utilization {util}% exceeds {self.thresholds['utilization']}%"
                alerts_triggered.append(alert)
                self.alert_states['utilization'] = True
            elif util <= self.thresholds['utilization']:
                self.alert_states['utilization'] = False

            # Memory Utilization Alert
            mem_util = stat.get('memory_utilization', 0)
            if mem_util > self.thresholds['memory_utilization'] and not self.alert_states['memory_utilization']:
                alert = f"GPU {gpu_index} memory utilization {mem_util:.2f}% exceeds {self.thresholds['memory_utilization']}%"
                alerts_triggered.append(alert)
                self.alert_states['memory_utilization'] = True
            elif mem_util <= self.thresholds['memory_utilization']:
                self.alert_states['memory_utilization'] = False

            # Power Draw Alert
            power = stat.get('power_draw', 0)
            if power > self.thresholds['power_draw'] and not self.alert_states['power_draw']:
                alert = f"GPU {gpu_index} power draw {power}W exceeds {self.thresholds['power_draw']}W"
                alerts_triggered.append(alert)
                self.alert_states['power_draw'] = True
            elif power <= self.thresholds['power_draw']:
                self.alert_states['power_draw'] = False

            # Trigger alerts
            for alert in alerts_triggered:
                print(f"ALERT: {alert}")
                self.send_desktop_notification("GPU Monitor Alert", alert)
                if self.sound_alert:
                    self.play_sound_alert()

    def update_stats_table(self, stats):
        self.stats_table.setRowCount(len(stats))
        for row, stat in enumerate(stats):
            self.stats_table.setItem(row, 0, QTableWidgetItem(str(stat.get('gpu_index', 'N/A'))))
            self.stats_table.setItem(row, 1, QTableWidgetItem(stat.get('name', 'N/A')))
            self.stats_table.setItem(row, 2, QTableWidgetItem(str(stat.get('utilization', 'N/A'))))
            mem_usage = f"{stat.get('memory_used', 0):.2f}/{stat.get('memory_total', 0):.2f}"
            self.stats_table.setItem(row, 3, QTableWidgetItem(mem_usage))
            mem_util = f"{stat.get('memory_utilization', 0):.2f}"
            self.stats_table.setItem(row, 4, QTableWidgetItem(mem_util))
            self.stats_table.setItem(row, 5, QTableWidgetItem(str(stat.get('temperature', 'N/A'))))
            power = f"{stat.get('power_draw', 0):.2f}/{stat.get('power_limit', 0):.2f}"
            self.stats_table.setItem(row, 6, QTableWidgetItem(power))
            self.stats_table.setItem(row, 7, QTableWidgetItem(str(stat.get('fan_speed', 'N/A'))))
            self.stats_table.setItem(row, 8, QTableWidgetItem(str(stat.get('clock_speed', 'N/A'))))

    def update_process_tables(self, stats):
        for i, stat in enumerate(stats):
            if i >= self.process_tabs.count():
                continue
            table = self.process_tabs.widget(i).findChild(QTableWidget)
            processes = stat.get('processes', [])
            processes = sorted(processes, key=lambda x: x['used_memory'], reverse=True)
            display_processes = processes[:20]

            table.setRowCount(len(display_processes) if display_processes else 1)
            if display_processes:
                for row, proc in enumerate(display_processes):
                    table.setItem(row, 0, QTableWidgetItem(str(proc.get('pid', 'N/A'))))
                    proc_type = proc.get('type', 'Unknown')
                    proc_type_full = 'Graphics' if proc_type == 'G' else 'Compute' if proc_type == 'C' else 'Unknown'
                    table.setItem(row, 1, QTableWidgetItem(proc_type_full))
                    proc_name = proc.get('name', 'N/A')[:50]
                    table.setItem(row, 2, QTableWidgetItem(proc_name))
                    mem_usage = f"{proc.get('used_memory', 0):.2f}"
                    table.setItem(row, 3, QTableWidgetItem(mem_usage))
            else:
                table.setItem(0, 0, QTableWidgetItem("N/A"))
                table.setItem(0, 1, QTableWidgetItem("N/A"))
                table.setItem(0, 2, QTableWidgetItem("No Processes"))
                table.setItem(0, 3, QTableWidgetItem("0.00"))

    def update_dashboard_graphs(self, stats):
        current_time = len(self.data_buffers[0]['time'])

        for i, stat in enumerate(stats):
            buffer = self.data_buffers[i]
            buffer['time'].append(current_time)
            buffer['temperature'].append(stat.get('temperature', 0))
            buffer['utilization'].append(stat.get('utilization', 0))
            buffer['memory_utilization'].append(stat.get('memory_utilization', 0))
            buffer['power_draw'].append(stat.get('power_draw', 0))

            buffer['temperature_curve'].setData(list(buffer['time']), list(buffer['temperature']))
            buffer['utilization_curve'].setData(list(buffer['time']), list(buffer['utilization']))
            buffer['memory_utilization_curve'].setData(list(buffer['time']), list(buffer['memory_utilization']))
            buffer['power_draw_curve'].setData(list(buffer['time']), list(buffer['power_draw']))

    def update_stats(self):
        try:
            stats = get_nvidia_stats(self.device_count)
            self.update_stats_table(stats)
            self.update_process_tables(stats)
            self.check_alerts(stats)
            self.update_dashboard_graphs(stats)
        except Exception as e:
            print(f"Error updating stats: {e}")

    def closeEvent(self, event):
        reply = QMessageBox.question(self, 'Quit',
                                     "Are you sure you want to quit GPU Monitor?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                pynvml.nvmlShutdown()
            except:
                pass
            event.accept()
        else:
            event.ignore()
