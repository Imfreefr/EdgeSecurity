"""Motor inicial de risco para aproximação humano-máquina.

IMPORTANTE: a distância usada aqui é baseada em pixels/caixas. Isso é útil para
protótipo, mas NÃO representa distância física em metros. Para uso industrial,
o sistema deve ser calibrado para cada câmera (homografia, zonas físicas,
profundidade/estéreo ou outro método validado) antes de ser usado como barreira
de segurança.
"""

from math import hypot, isfinite


def center(box):
    x1, y1, x2, y2 = box
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def box_gap(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    dx = max(ax1 - bx2, bx1 - ax2, 0)
    dy = max(ay1 - by2, by1 - ay2, 0)
    return hypot(dx, dy)


def assess_risk(detections, frame_width=640):
    if not isinstance(frame_width, (int, float)) or not isfinite(frame_width) or frame_width <= 0:
        raise ValueError("Largura do frame inválida para aproximação visual.")
    reference_scale = 640 / frame_width
    people = [d for d in detections if d.get("class_id") == 0 or
              (d.get("class_id") is None and d.get("class_name") == "human")]
    machines = [d for d in detections if d["class_name"] in {"machine", "forklift"}]
    risks = []

    for person in people:
        for machine in machines:
            gap = box_gap(person["bbox"], machine["bbox"])
            reference_gap = gap * reference_scale
            pc = center(person["bbox"])
            mc = center(machine["bbox"])
            center_distance = hypot(pc[0] - mc[0], pc[1] - mc[1])

            # Image-space heuristic at a 640px reference width, NOT meters.
            if reference_gap <= 0:
                level = "critical"
            elif reference_gap <= 40:
                level = "high"
            elif reference_gap <= 90:
                level = "medium"
            else:
                level = "safe"

            risks.append(
                {
                    "person_track_id": person.get("track_id"),
                    "machine_track_id": machine.get("track_id"),
                    "gap_pixels": round(gap, 1),
                    "gap_reference_pixels": round(reference_gap, 1),
                    "center_distance_pixels": round(center_distance, 1),
                    "level": level,
                }
            )

    priority = {"critical": 4, "high": 3, "medium": 2, "safe": 1}
    overall = max(
        (r["level"] for r in risks), key=lambda x: priority[x], default="safe"
    )
    return {"level": overall, "pairs": risks}
