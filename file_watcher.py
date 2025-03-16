import time
import os
from pathlib import Path
import logging
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PDFHandler(FileSystemEventHandler):
    def __init__(self, callback, extensions=['.pdf']):
        self.callback = callback
        self.extensions = extensions
        super().__init__()
        
    def on_created(self, event):
        if not event.is_directory:
            file_path = event.src_path
            if self._is_valid_extension(file_path):
                logger.info(f"New file detected: {file_path}")
                # Allow file to be fully written
                time.sleep(2)
                self.callback(file_path)
    
    def _is_valid_extension(self, file_path):
        return any(file_path.lower().endswith(ext) for ext in self.extensions)

class FileWatcher:
    def __init__(self, directory_to_watch, callback):
        self.directory_to_watch = directory_to_watch
        self.callback = callback
        self.observer = Observer()
        
    def start(self):
        """Start watching the directory for new files"""
        logger.info(f"Starting file watcher on directory: {self.directory_to_watch}")
        
        event_handler = PDFHandler(self.callback)
        self.observer.schedule(event_handler, self.directory_to_watch, recursive=False)
        self.observer.start()
        
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def process_existing_files(self, process_all=False):
        """Process existing files in the directory"""
        logger.info(f"Checking for existing files in: {self.directory_to_watch}")
        
        for file_path in Path(self.directory_to_watch).glob("*.pdf"):
            if process_all or self._should_process(file_path):
                logger.info(f"Processing existing file: {file_path}")
                self.callback(str(file_path))
    
    def _should_process(self, file_path):
        """Determine if a file should be processed based on any criteria"""
        # Add any criteria here, for now always returns True
        return True
                
    def stop(self):
        """Stop the file watcher"""
        logger.info("Stopping file watcher")
        self.observer.stop()
        self.observer.join()
