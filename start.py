import sys
import subprocess
from queue import Queue
import threading
from PySide6.QtWidgets import (QApplication, QMainWindow, QTabWidget, QTextEdit, QSystemTrayIcon, QMenu, QPushButton, QVBoxLayout, QWidget)
from PySide6.QtGui import (QIcon, QAction)
from PySide6.QtCore import (Qt, QTimer)
from qt_material import apply_stylesheet

class GUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.output_queue_server = Queue()
        self.output_queue_client = Queue()
        self.start_script()

    def init_ui(self):
        self.resize(425, 425)
        self.setWindowTitle('CapsWriter-Offline')
        self.setWindowIcon(QIcon("assets/icon.ico"))
        self.create_tabs()
        self.create_clear_buttons()  # Create clear buttons
        self.create_systray_icon()
        self.hide()
        self.tab_server.clear()
        self.tab_client.clear()

    def create_tabs(self):
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)

        self.tab_server = QTextEdit()
        self.tab_client = QTextEdit()

        # Configure the QTextEdit widgets to not show scroll bars
        self.tab_server.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tab_server.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tab_client.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.tab_client.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.tab_widget.addTab(self.tab_server, "Server")
        self.tab_widget.addTab(self.tab_client, "Client")

    def create_clear_buttons(self):
        # Create two buttons
        self.clear_server_button = QPushButton("Clear Server Text", self)
        self.clear_client_button = QPushButton("Clear Client Text", self)
        
        # Connect click events
        self.clear_server_button.clicked.connect(lambda: self.clear_text_box(self.tab_server))
        self.clear_client_button.clicked.connect(lambda: self.clear_text_box(self.tab_client))
        
        # Create a central widget
        central_widget = QWidget()
        
        # Create a vertical layout
        layout = QVBoxLayout()
        
        # Add tab widgets and buttons to the layout
        layout.addWidget(self.tab_widget)
        layout.addWidget(self.clear_server_button)
        layout.addWidget(self.clear_client_button)
        
        # Set the layout as the central widget's layout
        central_widget.setLayout(layout)
        
        # Set the central widget
        self.setCentralWidget(central_widget)

    def clear_text_box(self, text_box):
        # Clear the content of the specified text box
        text_box.clear()
    
    def create_systray_icon(self):
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon("assets/icon.ico"))
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
        # Terminate core_server.py process
        if hasattr(self, 'core_server_process') and self.core_server_process:
            self.core_server_process.terminate()
            self.core_server_process.kill()
        
        # Terminate core_client.py process
        if hasattr(self, 'core_client_process') and self.core_client_process:
            self.core_client_process.terminate()
            self.core_client_process.kill()
        
        # Hide the system tray icon
        self.tray_icon.setVisible(False)
        
        # Quit the application
        QApplication.quit()
        
        # TODO: Quit models The above method can not completely exit the model, rename pythonw.exe to pythonw_CapsWriter.exe and taskkill. It's working but not the best way.
        proc = subprocess.Popen('taskkill /IM pythonw_CapsWriter_Server.exe /IM pythonw_CapsWriter_Client.exe /F', stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True)

    def on_tray_icon_activated(self, reason):
        # Called when the system tray icon is activated
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()  # Show the main window

    def start_script(self):
        # Start core_server.py and redirect output to the server queue
        self.core_server_process = subprocess.Popen(['.\\runtime\\pythonw_CapsWriter_Server.exe', 'core_server.py'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        threading.Thread(target=self.enqueue_output, args=(self.core_server_process.stdout, self.output_queue_server), daemon=True).start()

        # Start core_client.py and redirect output to the client queue
        self.core_client_process = subprocess.Popen(['.\\runtime\\pythonw_CapsWriter_Client.exe', 'core_client.py'], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        threading.Thread(target=self.enqueue_output, args=(self.core_client_process.stdout, self.output_queue_client), daemon=True).start()

        # Update text boxes
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_text_boxes)
        self.update_timer.start(100)


    def enqueue_output(self, out, queue):
        for line in iter(out.readline, b''):
            queue.put(line)

    def update_text_boxes(self):
        # Update server text box
        while not self.output_queue_server.empty():
            line = self.output_queue_server.get()
            self.tab_server.append(line)

        # Update client text box
        while not self.output_queue_client.empty():
            line = self.output_queue_client.get()
            self.tab_client.append(line)

if __name__ == '__main__':
    app = QApplication([])
    apply_stylesheet(app, theme='dark_amber.xml')
    gui = GUI()
    gui.show()
    sys.exit(app.exec())
