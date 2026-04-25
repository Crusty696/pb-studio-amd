import traceback
import sys
import logging
import threading
from PyQt6.QtCore import QRunnable, QThreadPool, pyqtSlot
from pb_studio.core.worker_signals import WorkerSignals

logger = logging.getLogger(__name__)

class Worker(QRunnable):
    '''
    Worker thread
    Inherits from QRunnable to handle worker thread setup, signals and wrap-up.
    
    :param callback: The function callback to run on this worker thread. Supplied args and
                     kwargs will be passed through to the runner.
    :type callback: function
    :param args: Arguments to pass to the callback function
    :param kwargs: Keywords to pass to the callback function
    '''

    def __init__(self, fn, *args, **kwargs):
        super(Worker, self).__init__()

        # Store constructor arguments (re-used for processing)
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        # BUG-085 FIX: Injiziere Callbacks nur, wenn die Funktion sie akzeptiert
        import inspect
        try:
            sig = inspect.signature(fn)
            if 'progress_callback' in sig.parameters:
                kwargs['progress_callback'] = self.signals.progress
            if 'status_callback' in sig.parameters:
                kwargs['status_callback'] = self.signals.status
        except (ValueError, TypeError):
            # Fallback for built-ins or functions without signature
            pass

    @pyqtSlot()
    def run(self):
        '''
        Initialise the runner function with passed args, kwargs.
        '''
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            self.signals.result.emit(result)  # Return the result of the processing
        finally:
            self.signals.finished.emit()  # Done

class ThreadPoolManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        # BUG-099 FIX: Thread-safe singleton
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(ThreadPoolManager, cls).__new__(cls)
                    cls._instance._init_pool()
        return cls._instance

    def _init_pool(self):
        self.pool = QThreadPool.globalInstance()
        # Constrain max threads if needed (e.g. to avoid CPU choking with ML)
        # self.pool.setMaxThreadCount(4) 
        logger.info(f"ThreadPool initialized. Max threads: {self.pool.maxThreadCount()}")

    def start(self, worker: Worker):
        """Starts a worker."""
        self.pool.start(worker)

    def active_thread_count(self):
        return self.pool.activeThreadCount()
