import sys
import subprocess
from queue import Queue
import threading
from PySide6.QtWidgets import (QApplication, QMainWindow, QTextEdit, QSystemTrayIcon, QMenu, QPushButton, QVBoxLayout, QWidget)
from PySide6.QtGui import (QIcon, QAction)
from PySide6.QtCore import (Qt, QTimer)
from qt_material import apply_stylesheet

class GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.output_queue_client = Queue()
        self.start_script()

    def init_ui(self):
        self.resize(425, 425)
        self.setWindowTitle('CapsWriter-Offline-Client')
        self.setWindowIcon(QIcon("assets/client-icon.ico"))
        self.create_text_box()
        self.create_clear_button()  # Create clear button
        self.create_systray_icon()
        self.hide()

    def create_text_box(self):
        self.text_box_client = QTextEdit()
        self.text_box_client.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_box_client.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setCentralWidget(self.text_box_client)

    def create_clear_button(self):
        # Create a button
        self.clear_button = QPushButton("Clear Client Text", self)
        
        # Connect click event
        self.clear_button.clicked.connect(lambda: self.clear_text_box())
        
        # Create a vertical layout
        layout = QVBoxLayout()
        
        # Add text box and button to the layout
        layout.addWidget(self.text_box_client)
        layout.addWidget(self.clear_button)
        
        # Create a central widget
        central_widget = QWidget()
        central_widget.setLayout(layout)
        
        # Set the central widget
        self.setCentralWidget(central_widget)

    def clear_text_box(self):
        # Clear the content of the client text box
        self.text_box_client.clear()
    
    def create_systray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("assets/client-icon.ico"))
        show_action = QAction("Show", self)
        quit_action = QAction("Quit", self)
        show_action.triggered.connect(self.show)
        quit_action.triggered.connect(self.quit_app)
        self.tray_icon.activated.connect(self.on_tray_icon_activated)
        tray_menu = QMenu()
        tray_menu.addAction(show_action)
        tray_menu.addAction(quit_action)
        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.show()

    def closeEvent(self, event):
        # Minimize to system tray instead of closing the window when the user clicks the close button
        self.hide()  # Hide the window
        event.ignore()  # Ignore the close event
    
    def quit_app(self):
        # Terminate core_client.py process
        if hasattr(self, 'core_client_process') and self.core_client_process:
            self.core_client_process.terminate()
            self.core_client_process.kill()
        
        # Hide the system tray icon
        self.tray_icon.setVisible(False)
        
        # Quit the application
        QApplication.quit()

        # TODO: Quit models The above method can not completely exit the model, rename pythonw.exe to pythonw_CapsWriter.exe and taskkill. It's working but not the best way.
        proc = subprocess.Popen('taskkill /IM pythonw_CapsWriter_Client.exe /F', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)


    def on_tray_icon_activated(self, reason):
        # Called when the system tray icon is activated
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()  # Show the main window

    def start_script(self):
        # Start core_client.py and redirect output to the client queue
        self.core_client_process = subprocess.Popen(['.\\runtime\\pythonw_CapsWriter_Client.exe', 'core_client.py'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        threading.Thread(target=self.enqueue_output, args=(self.core_client_process.stdout, self.output_queue_client), daemon=True).start()

        # Update text box
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_text_box)
        self.update_timer.start(100)


    def enqueue_output(self, out, queue):
        for line in iter(out.readline, b''):
            queue.put(line)

    def update_text_box(self):
        # Update client text box
        while not self.output_queue_client.empty():
            line = self.output_queue_client.get()
            self.text_box_client.append(line)

if __name__ == '__main__':
    app = QApplication([])
    apply_stylesheet(app, theme='dark_teal.xml')
    gui = GUI()
    gui.show()
    sys.exit(app.exec())
