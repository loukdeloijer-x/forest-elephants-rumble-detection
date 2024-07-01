import sys
import os
import shutil
import logging
from pathlib import Path

from PyQt5.QtWidgets import (QApplication, QMainWindow, QPushButton, QLabel, 
                             QVBoxLayout, QWidget, QFileDialog, QProgressBar)
                    
from PyQt5.QtCore import QRunnable, QThread, pyqtSignal, QTimer, QThreadPool, QObject
import time

from forest_elephants_rumble_detection.application.gui.session.session import Session
from forest_elephants_rumble_detection.application.gui.session.storage import Storage
from forest_elephants_rumble_detection.application.gui.session.files import FileManager
from forest_elephants_rumble_detection.application.gui.session.model import Model

class WorkerSignals(QObject):
    '''
    Defines the signals available from a running worker thread.

    Supported signals are:

    progress
        int indicating % progress
    finished
        No data

    '''
    progress = pyqtSignal()
    finished= pyqtSignal()

# Worker class to handle processing in a separate thread
class Worker(QRunnable):

    def __init__(self, output_dir, model, file, session, storage):
        super().__init__()
        self.output_dir = output_dir
        self.file = file
        self.session = session
        self.model = model
        self.storage = storage
        self.signals = WorkerSignals()

    def run(self):
        self.model.analyze(file=self.file, output_dir=self.output_dir)
        self.storage.remove_file(self.file)
        self.session.update_annotation_txt(self.file.export())
        self.session.update_summary_df(self.file)
        self.session.save_summary_df()
            
        self.signals.finished.emit()  # Emit finished signal with output path

# Main window class
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.input_dir = Path()
        self.output_dir = Path()
         # Initialize output_dir attribute

    def initUI(self):
        self.setWindowTitle('Audio Data Processor')  # Set window title
        self.setGeometry(100, 100, 400, 300)         # Set window size and position

        logging.basicConfig(level='INFO')
        layout = QVBoxLayout()  # Create a vertical box layout

        self.threadpool = QThreadPool()
        self.max_threads = self.threadpool.maxThreadCount()

        logging.info(f"Multithreading with maximum {self.max_threads} threads")
  
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
        
        # Label to display the number of active threads
        self.thread_count_label = QLabel(f"Active threads: 0")
        layout.addWidget(self.thread_count_label)

        self.max_threads_label = QLabel(f"max threads (CPU cores): {self.max_threads}")
        layout.addWidget(self.max_threads_label)

        # Container widget to hold the layout
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)
    
    def select_output_directory(self):
        # Open a directory dialog to select the output directory
        directory = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if directory:
            self.output_dir = Path(directory)
            self.output_label.setText(f"Output directory: {directory}")
            self.update_process_button_state()  # Checking that files and output directory are specified

    def wav_count(self, folder):
        self.num_files = sum(1 for root, dirs, files in os.walk(folder) for filename in files if filename.endswith(".wav"))

    def select_input_directory(self):
        # Open a directory dialog to select the output directory
        input_directory = QFileDialog.getExistingDirectory(self, "Select input Directory")
        if input_directory:
            self.input_dir = Path(input_directory)
            self.input_label.setText(f"Input directory: {input_directory}")
            self.update_process_button_state()  # Checking that files and output directory are specified
            self.wav_count(input_directory)
            self.file_label.setText(f"Selected {self.num_files} files")

    def update_process_button_state(self):
        # Enable the process button only if files are selected and output directory is set
        if self.input_dir and self.output_dir:
            self.process_button.setEnabled(True)
        else:
            self.process_button.setEnabled(False)

    def process_files(self):
        self.processing_start_time = time.time()  # Record start time
        self.session = Session(str(self.input_dir), str(self.output_dir)) 
        self.total_files = len(self.session.remaining_input_wav)
        self.completed_files = 0
        self.progress_bar.setValue(0)

        if not self.session.remaining_input_wav:
            self.message_label.setText("All files already processed")
            return

        self.model = Model() 

        self.tmp_session_dir = Path(self.output_dir) / "tmp_session"
        self.tmp_session_dir.mkdir(exist_ok=True)

        self.storage = Storage(app_data_dir=self.tmp_session_dir)
        self.file_manager = FileManager(self.model, self.storage)

        for file in self.session.remaining_input_wav:
            self.file_manager.add_file(str(file))

        self.check_and_launch_workers()


    def check_and_launch_workers(self):
        while self.file_manager.files and self.threadpool.activeThreadCount() < self.max_threads: 
            file = self.file_manager.files.pop(0)
            worker = Worker(file=file, output_dir=self.output_dir, model=self.model, session=self.session, storage=self.storage)
            worker.signals.finished.connect(self.file_finished)

            self.threadpool.start(worker)
            self.thread_count_label.setText(f"Active threads: {self.threadpool.activeThreadCount()}")

    def update_time_and_progress(self):
        self.completed_files += 1
        progress = int((self.completed_files / self.total_files) * 100)
        self.progress_bar.setValue(progress)

        self.output_label.setText(f"Processed {self.completed_files}/{self.total_files} files")
    
        total_elapsed_time = time.time() - self.processing_start_time  # Calculate elapsed time
        self.time_label.setText(f"Processing Time: {int(total_elapsed_time)} seconds")

    
    def file_finished(self):
        self.update_time_and_progress()

        if (not self.file_manager.files) and (self.threadpool.activeThreadCount() < 1):
                self.output_label.setText(f"All files processed. Output saved to: {self.output_dir}")
                self.cleanup_tmp_session()

        self.check_and_launch_workers(self)
        self.thread_count_label.setText(f"Active threads: {self.threadpool.activeThreadCount()}")

    def cleanup_tmp_session(self):
        if self.tmp_session_dir and self.tmp_session_dir.exists():
            shutil.rmtree(self.tmp_session_dir)
            
if __name__ == "__main__":
    app = QApplication(sys.argv)  # Create a QApplication
    mainWindow = MainWindow()     # Create an instance of MainWindow
    mainWindow.show()             # Show the main window
    sys.exit(app.exec_())         # Run the application's event loop

