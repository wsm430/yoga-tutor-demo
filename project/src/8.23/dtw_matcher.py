"""
dtw_matcher.py
改进的 DTW（Dynamic Time Warping）算法
用于动态动作序列与标准模板的时序匹配
参考: Zhang & Li, IEEE Access 2023
"""

import numpy as np
from config import ANGLE_DEFINITIONS, DTW_WINDOW_RATIO


def _frame_to_vector(angle_dict):
    """将单帧角度字典转为固定顺序的向量"""
    keys = sorted(ANGLE_DEFINITIONS.keys())
    return np.array([angle_dict.get(k, 0.0) for k in keys])


def dtw_distance(seq_user, seq_standard, window_ratio=DTW_WINDOW_RATIO):
    """
    带 Sakoe-Chiba 带约束的 DTW 距离

    参数:
        seq_user:     用户角度序列 [{'left_elbow':..., ...}, ...]
        seq_standard: 标准角度序列（同格式）
        window_ratio: 窗口占序列长度的比例
    返回:
        (normalized_distance, warp_path)
    """
    S = np.array([_frame_to_vector(f) for f in seq_user])
    T = np.array([_frame_to_vector(f) for f in seq_standard])
    n, m = len(S), len(T)
    w = max(int(max(n, m) * window_ratio), abs(n - m))

    cost = np.full((n + 1, m + 1), np.inf)
    cost[0, 0] = 0.0

    for i in range(1, n + 1):
        j_start = max(1, i - w)
        j_end = min(m, i + w)
        for j in range(j_start, j_end + 1):
            d = np.linalg.norm(S[i - 1] - T[j - 1])
            cost[i, j] = d + min(cost[i - 1, j],
                                  cost[i, j - 1],
                                  cost[i - 1, j - 1])

    # 回溯路径
    path = []
    i, j = n, m
    while i > 0 and j > 0:
        path.append((i - 1, j - 1))
        candidates = {
            (i - 1, j - 1): cost[i - 1, j - 1],
            (i - 1, j): cost[i - 1, j],
            (i, j - 1): cost[i, j - 1],
        }
        i, j = min(candidates, key=candidates.get)
    path.reverse()

    norm_dist = cost[n, m] / len(path) if path else 0.0
    return float(norm_dist), path


def dtw_score(seq_user, seq_standard, max_dist=50.0):
    """
    将 DTW 距离转换为 0-100 分

    参数:
        max_dist: 映射的最大距离（超过视为 0 分）
    返回:
        score (0-100)
    """
    dist, _ = dtw_distance(seq_user, seq_standard)
    score = max(0.0, 100.0 * (1.0 - dist / max_dist))
    return round(score, 1)


# ==================== 独立测试 ====================
if __name__ == "__main__":
    print("✅ DTW Matcher 测试")

    # 模拟标准序列（10帧）
    std_seq = []
    for i in range(10):
        std_seq.append({k: 90.0 + i * 5.0 for k in ANGLE_DEFINITIONS})

    # 模拟用户序列（12帧，速度稍慢，角度有偏差）
    user_seq = []
    for i in range(12):
        t = i * 10.0 / 12.0
        user_seq.append({k: 90.0 + t * 5.0 + np.random.normal(0, 3)
                         for k in ANGLE_DEFINITIONS})

    dist, path = dtw_distance(user_seq, std_seq)
    score = dtw_score(user_seq, std_seq)
    print(f"  DTW 距离: {dist:.2f}")
    print(f"  DTW 评分: {score}/100")
    print(f"  对齐路径长度: {len(path)}")