import json
from typing import List, Tuple, Dict, Any, Optional

def point_in_polygon(point: Tuple[int, int], polygon: List[List[int]]) -> bool:
    """
    Ray-casting algorithm to test if a 2D point (x, y) lies strictly inside a polygon.
    """
    x, y = point
    n = len(polygon)
    if n < 3:
        return False
    inside = False
    p1x, p1y = polygon[0]
    for i in range(n + 1):
        p2x, p2y = polygon[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

class ZoneDetector:
    def check_zone_access(
        self,
        bbox: List[int],
        role: Optional[str],
        status: str,
        zone_polygon: List[List[int]],
        allowed_roles: List[str]
    ) -> Optional[str]:
        """
        Determines whether the bottom-center point of bounding box [x1, y1, x2, y2]
        is inside polygon and evaluates role authorization.
        Returns: 'UNAUTHORIZED_ZONE_ACCESS', 'AUTHORIZED_ZONE_ACCESS', or None.
        """
        if not bbox or len(bbox) < 4 or not zone_polygon or len(zone_polygon) < 3:
            return None

        x1, y1, x2, y2 = bbox
        bottom_center = ((x1 + x2) // 2, y2)

        if not point_in_polygon(bottom_center, zone_polygon):
            return None

        # Check authorization
        normalized_role = role.strip().upper() if role else None
        normalized_allowed = {allowed.strip().upper() for allowed in allowed_roles if allowed}
        if status == "VERIFIED" and normalized_role and (normalized_role in normalized_allowed or "ALL" in normalized_allowed):
            return "AUTHORIZED_ZONE_ACCESS"
        else:
            return "UNAUTHORIZED_ZONE_ACCESS"
