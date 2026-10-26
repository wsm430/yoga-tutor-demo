import math
from typing import Tuple, List

def calculate_angle(a: Tuple[float, float], b: Tuple[float, float], c: Tuple[float, float]) -> float:
    """
    计算由三点a、b、c形成的夹角，b为顶点。
    输入：
        a, b, c: (x, y) 坐标元组
    输出：
        角度（degree）
    """
    # 向量BA和BC
    ba = (a[0] - b[0], a[1] - b[1])
    bc = (c[0] - b[0], c[1] - b[1])
    # 计算向量点积和模长
    dot_product = ba[0] * bc[0] + ba[1] * bc[1]
    norm_ba = math.hypot(ba[0], ba[1])
    norm_bc = math.hypot(bc[0], bc[1])
    if norm_ba == 0 or norm_bc == 0:
        return 0.0
    # 计算夹角（弧度）
    cos_angle = max(min(dot_product / (norm_ba * norm_bc), 1.0), -1.0)
    angle_rad = math.acos(cos_angle)
    # 转为角度
    angle_deg = math.degrees(angle_rad)
    return angle_deg

def calculate_multiple_angles(points: List[Tuple[float, float]], triplets: List[Tuple[int, int, int]]) -> List[float]:
    """
    批量计算多个关节的角度。
    输入：
        points: 关键点坐标列表 [(x, y), ...]
        triplets: 每个三元组为三个点的索引 (a, b, c)
    输出：
        角度列表 [degree, ...]
    """
    angles = []
    for a_idx, b_idx, c_idx in triplets:
        a, b, c = points[a_idx], points[b_idx], points[c_idx]
        angle = calculate_angle(a, b, c)
        angles.append(angle)
    return angles
