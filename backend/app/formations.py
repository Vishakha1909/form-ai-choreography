from __future__ import annotations

import math
from scipy.optimize import linear_sum_assignment
from .models import Point, StageConstraints


def _spread(count: int, extent: float, margin: float) -> list[float]:
    usable = max(0.2, extent - 2 * margin)
    if count == 1:
        return [extent / 2]
    return [margin + i * usable / (count - 1) for i in range(count)]


def _perimeter_points(vertices: list[tuple[float, float]], count: int) -> list[tuple[float, float]]:
    """Sample equally spaced slots around a closed polygon."""
    edges = [math.dist(vertices[i], vertices[(i + 1) % len(vertices)]) for i in range(len(vertices))]
    perimeter = sum(edges)
    points = []
    for index in range(count):
        distance = index * perimeter / count
        for edge_index, edge_length in enumerate(edges):
            if distance <= edge_length:
                start = vertices[edge_index]
                end = vertices[(edge_index + 1) % len(vertices)]
                ratio = distance / edge_length if edge_length else 0
                points.append((start[0] + (end[0] - start[0]) * ratio, start[1] + (end[1] - start[1]) * ratio))
                break
            distance -= edge_length
    return points


def generate_positions(kind: str, constraints: StageConstraints) -> dict[str, Point]:
    n, w, d, gap = constraints.dancer_count, constraints.stage_width, constraints.stage_depth, constraints.min_spacing
    ids = [f"D{i + 1}" for i in range(n)]
    margin = max(0.45, gap / 2)
    kind = kind.lower().replace(" ", "_")
    points: list[tuple[float, float]] = []
    if kind == "line":
        points = list(zip(_spread(n, w, margin), [d / 2] * n))
    elif kind == "diagonal":
        xs, ys = _spread(n, w, margin), _spread(n, d, margin)
        points = list(zip(xs, ys))
    elif kind in {"two_rows", "staggered"}:
        front = (n + 1) // 2
        back = n - front
        points = [(x, d * 0.38) for x in _spread(front, w, margin)]
        if back:
            back_xs = _spread(back, w, margin)
            if kind == "staggered" and front > 1:
                step = (w - 2 * margin) / (front - 1)
                back_xs = _spread(back, max(0.2, w - step), margin)
                back_xs = [x + step / 2 for x in back_xs]
            points += [(x, d * 0.64) for x in back_xs]
    elif kind == "two_columns":
        left = (n + 1) // 2
        right = n - left
        points = [(w * 0.38, y) for y in _spread(left, d, margin)]
        points += [(w * 0.62, y) for y in _spread(right, d, margin)] if right else []
    elif kind == "circle":
        radius = min(w, d) * 0.34
        points = [(w / 2 + radius * math.cos(-math.pi / 2 + 2 * math.pi * i / n), d / 2 + radius * math.sin(-math.pi / 2 + 2 * math.pi * i / n)) for i in range(n)]
    elif kind == "semicircle":
        radius = min(w / 2 - margin, d / 2 - margin)
        angles = [math.pi + math.pi * i / (n - 1) for i in range(n)] if n > 1 else [1.5 * math.pi]
        points = [(w / 2 + radius * math.cos(angle), d * 0.68 + radius * math.sin(angle)) for angle in angles]
    elif kind in {"v", "inverted_v"}:
        rows = (n + 1) // 2
        for i in range(n):
            side = -1 if i % 2 == 0 else 1
            rank = (i + 1) // 2
            direction = 1 if kind == "v" else -1
            apex_y = d * (0.25 if kind == "v" else 0.75)
            if i == 0:
                points.append((w / 2, apex_y))
            else:
                points.append((w / 2 + side * rank * min(gap * 0.9, w / (2 * rows + 1)), apex_y + direction * rank * min(gap * 0.75, d / (rows + 2))))
    elif kind == "diamond":
        points = _perimeter_points([(w / 2, margin), (w - margin, d / 2), (w / 2, d - margin), (margin, d / 2)], n)
    elif kind == "box":
        points = _perimeter_points([(margin, margin), (w - margin, margin), (w - margin, d - margin), (margin, d - margin)], n)
    elif kind == "cross":
        points = [(w / 2, d / 2)]
        radius = gap * 1.2
        ring = 1
        while len(points) < n:
            distance = radius * ring
            candidates = [(w / 2 - distance, d / 2), (w / 2 + distance, d / 2), (w / 2, d / 2 - distance), (w / 2, d / 2 + distance)]
            usable = [(x, y) for x, y in candidates if margin <= x <= w - margin and margin <= y <= d - margin]
            points.extend(usable)
            if not usable:
                break
            ring += 1
        if len(points) < n:
            # Keep all dancer IDs present even when the requested spacing is
            # physically impossible; deterministic validation will then give
            # the caller a useful spacing error instead of losing dancers.
            for candidate in _perimeter_points([(margin, margin), (w - margin, margin), (w - margin, d - margin), (margin, d - margin)], n):
                if candidate not in points:
                    points.append(candidate)
                if len(points) == n:
                    break
        points = points[:n]
    else:
        raise ValueError(f"Unknown formation kind: {kind}")
    return {dancer_id: Point(x=round(x, 3), y=round(y, 3)) for dancer_id, (x, y) in zip(ids, points)}


def assign_nearest(previous: dict[str, Point], target: dict[str, Point]) -> dict[str, Point]:
    """Assign target slots to stable dancer IDs with minimum total travel.

    Euclidean minimum-cost matching also eliminates needless path swaps that
    arise when two shape generators enumerate their points differently.
    """
    dancer_ids = sorted(previous)
    slots = list(target.values())
    costs = [[_distance(previous[dancer_id], slot) for slot in slots] for dancer_id in dancer_ids]
    rows, columns = linear_sum_assignment(costs)
    return {dancer_ids[row]: slots[column] for row, column in zip(rows, columns)}


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)

