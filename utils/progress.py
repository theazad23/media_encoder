import time
from datetime import datetime, timedelta

class ProgressTracker:
    def __init__(self, total_duration: float, filename: str):
        self.total_duration = total_duration
        self.filename = filename
        self.start_time = time.time()
        self.last_update = 0
        
    def update(self, current_time: float) -> str:
        """Update progress and return status string."""
        if time.time() - self.last_update < 1:
            return ""
            
        self.last_update = time.time()
        elapsed = time.time() - self.start_time
        progress = (current_time / self.total_duration) * 100
        
        if progress > 0:
            estimated_total = elapsed / (progress / 100)
            remaining = estimated_total - elapsed
            eta = datetime.now() + timedelta(seconds=remaining)
            
            return (f"\rProcessing {self.filename}: "
                   f"{progress:.1f}% complete | "
                   f"ETA: {eta.strftime('%H:%M:%S')} | "
                   f"Elapsed: {timedelta(seconds=int(elapsed))}")
        return f"\rProcessing {self.filename}: Initializing..."