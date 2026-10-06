from typing import List, Dict, Any, Optional

class CrowdDetector:
    def check_crowd_threshold(
        self,
        current_count: int,
        threshold: int
    ) -> bool:
        """
        Returns True if detected person count exceeds configured threshold.
        """
        if threshold <= 0:
            return False
        return current_count > threshold
