"""
one_euro_filter.py
1€ Filter 自适应滤波
"""

import math
import time
from config import FILTER_MIN_CUTOFF, FILTER_BETA, FILTER_D_CUTOFF


class _LowPass:
    __slots__ = ('_val', '_init')

    def __init__(self):
        self._val = 0.0
        self._init = False

    def __call__(self, value, alpha):
        if not self._init:
            self._init = True
            self._val = value
        else:
            self._val = alpha * value + (1.0 - alpha) * self._val
        return self._val


class OneEuroFilter:
    def __init__(self, min_cutoff=FILTER_MIN_CUTOFF,
                 beta=FILTER_BETA, d_cutoff=FILTER_D_CUTOFF):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self._x = _LowPass()
        self._dx = _LowPass()
        self._last_time = None

    @staticmethod
    def _alpha(cutoff, dt):
        tau = 1.0 / (2.0 * math.pi * cutoff)
        return 1.0 / (1.0 + tau / dt)

    def __call__(self, value, timestamp=None):
        if timestamp is None:
            timestamp = time.time()
        if self._last_time is None:
            self._last_time = timestamp
            self._x(value, 1.0)
            self._dx(0.0, 1.0)
            return value
        dt = max(timestamp - self._last_time, 1e-6)
        self._last_time = timestamp
        dx = (value - self._x._val) / dt
        edx = self._dx(dx, self._alpha(self.d_cutoff, dt))
        cutoff = self.min_cutoff + self.beta * abs(edx)
        return self._x(value, self._alpha(cutoff, dt))


class MultiPointFilter:
    def __init__(self, num_points=33, min_cutoff=FILTER_MIN_CUTOFF,
                 beta=FILTER_BETA, d_cutoff=FILTER_D_CUTOFF):
        self._filters = {}
        self._cfg = (min_cutoff, beta, d_cutoff)

    def _get(self, idx, axis):
        key = (idx, axis)
        if key not in self._filters:
            self._filters[key] = OneEuroFilter(*self._cfg)
        return self._filters[key]

    def filter_landmarks(self, landmarks, timestamp=None):
        if landmarks is None:
            return None
        if timestamp is None:
            timestamp = time.time()
        out = []
        for i, lm in enumerate(landmarks):
            out.append({
                'x': self._get(i, 'x')(lm['x'], timestamp),
                'y': self._get(i, 'y')(lm['y'], timestamp),
                'z': self._get(i, 'z')(lm['z'], timestamp),
                'visibility': lm['visibility'],
            })
        return out