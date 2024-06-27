import sys
import os
import shutil
import logging
from pathlib import Path

from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel, 
                             QVBoxLayout, QWidget, QFileDialog, QProgressBar)
                    
from PyQt5.QtCore import QThread, pyqtSignal, QTimer
from multiprocessing import Queue
import time

from forest_elephants_rumble_detection.application.gui.session.session import Session
from forest_elephants_rumble_detection.application.gui.session.storage import Storage
from forest_elephants_rumble_detection.application.gui.session.files import FileManager
from forest_elephants_rumble_detection.application.gui.session.model import Model

# Worker class to handle processing in a separate thread
class Worker(QThread):
    # Signal to update progress (file index, progress percentage)
    progress = pyqtSignal(int, int)  
    finished = pyqtSignal(int, str)  # Signal to indicate processing finished (file index, output path)

    def __init__(self, output_dir, model, queue, file, session, storage):
        super().__init__()
        self.output_dir = output_dir
        self.queue = queue # Queue to communicate progress
        self.file = file
        self.session = session
        self.model = model
        self.storage = storage

    def run(self):
    
        self.model.analyze(file=self.file, output_dir=self.output_dir)
        self.storage.remove_file(self.file)
        self.session.update_annotation_txt(self.file.export())
        self.session.update_summary_df(self.file)
        self.session.save_summary_df()
            
        self.finished.emit(self.file, str(self.output_dir))  # Emit finished signal with output path

# Main window class
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.input_dir = Path()
        self.output_dir = Path()  # Initialize output_dir attribute

    def initUI(self):
        self.setWindowTitle('Audio Data Processor')  # Set window title
        self.setGeometry(100, 100, 400, 300)         # Set window size and position

        layout = QVBoxLayout()  # Create a vertical box layout

        # Label to display the selected file information
        self.file_label = QLabel("No files selected")
        layout.addWidget(self.file_label)

        # Button to select input directory
        self.input_button = QPushButton("Select input Directory")
        self.input_button.clicked.connect(self.select_input_directory)
        layout.addWidget(self.input_button)
        
        # Button to select output directory
        self.output_button = QPushButton("Select Output Directory")
        self.output_button.clicked.connect(self.select_output_directory)
        layout.addWidget(self.output_button)

        # Label to display the selected output directory
        self.input_label = QLabel("No input directory selected")
        layout.addWidget(self.input_label)

        # Label to display the selected output directory
        self.output_label = QLabel("No output directory selected")
        layout.addWidget(self.output_label)

        # Button to start processing files, initially disabled
        self.process_button = QPushButton("Process Files")
        self.process_button.setEnabled(False)
        
        self.process_button.clicked.connect(self.process_files)
        layout.addWidget(self.process_button)

        self.progress_bar = QProgressBar(self)  # List to hold progress bars for each file
        layout.addWidget(self.progress_bar)

        self.time_label = QLabel("Processing Time: 0 seconds")
        layout.addWidget(self.time_label)

        self.message_label = QLabel("")  # Label to display messages
        layout.addWidget(self.message_label)

        # Container widget to hold the layout
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.selected_files = []  # List to hold selected file paths
    
    def select_output_directory(self):
        # Open a directory dialog to select the output directory
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_dir = Path(directory)
            self.output_label.setText(f"Output directory: {directory}")
            self.update_process_button_state()  # Checking that files and output directory are specified

    def parse_wav_files(self, folder):
        for root, dirs, files in os.walk(folder):
            for filename in files:
                if filename.endswith(".wav"):
                    file_path = Path(root) / filename 
                    self.selected_files.append(file_path)

    def select_input_directory(self):
        # Open a directory dialog to select the output directory
        input_directory = QFileDialog.getExistingDirectory(self, "Select input Directory")
        if input_directory:
            self.input_dir = Path(input_directory)
            self.input_label.setText(f"Input directory: {input_directory}")
            self.update_process_button_state()  # Checking that files and output directory are specified
            self.parse_wav_files(input_directory)
            self.file_label.setText(f"Selected {len(self.selected_files)} files")

    def update_process_button_state(self):
        # Enable the process button only if files are selected and output directory is set
        if (self.selected_files or self.input_dir) and self.output_dir:
            self.process_button.setEnabled(True)
        else:
            self.process_button.setEnabled(False)

    def process_files(self):
        self.start_time = time.time()  # Record start time
        self.queue = Queue()
        self.workers = []

        self.total_files = len(self.selected_files)
        self.completed_files = 0
        self.progress_bar.setValue(0)

        session = Session(str(self.input_dir), str(self.output_dir))
        if not session.remaining_input_wav:
            self.message_label.setText("All files already processed")
            return

        model = Model() 

        self.tmp_session_dir = Path(self.output_dir) / "tmp_session"
        self.tmp_session_dir.mkdir(exist_ok=True)

        storage = Storage(app_data_dir=self.tmp_session_dir)
        file_manager = FileManager(model, storage)

        for file in session.remaining_input_wav:
            _ = [file_manager.add_file(str(file)) for file in session.remaining_input_wav]

        # batch_size = 1
        # file_batches = [self.selected_files[i:i + batch_size] for i in range(0, len(self.selected_files), batch_size)]

        for file in file_manager.files:
            worker = Worker(file=file, model=model, output_dir=self.output_dir, session=session, queue=self.queue, storage=storage)

            worker.finished.connect(self.file_finished)
            self.workers.append(worker)
            worker.start()
    
    def file_finished(self):
        self.completed_files += 1
        progress = int((self.completed_files / self.total_files) * 100)
        self.progress_bar.setValue(progress)
        self.output_label.setText(f"Processed {self.completed_files}/{self.total_files} files")
        elapsed_time = time.time() - self.start_time  # Calculate elapsed time
        self.time_label.setText(f"Processing Time: {int(elapsed_time)} seconds")

        if self.completed_files == self.total_files:
            self.process_button.setEnabled(True)
            self.output_label.setText(f"All files processed. Output saved to: {self.output_dir}")
            self.cleanup_tmp_session()

    def cleanup_tmp_session(self):
        if self.tmp_session_dir and self.tmp_session_dir.exists():
            shutil.rmtree(self.tmp_session_dir)
            
if __name__ == "__main__":
    app = QApplication(sys.argv)  # Create a QApplication
    mainWindow = MainWindow()     # Create an instance of MainWindow
    mainWindow.show()             # Show the main window
    sys.exit(app.exec_())         # Run the application's event loop

