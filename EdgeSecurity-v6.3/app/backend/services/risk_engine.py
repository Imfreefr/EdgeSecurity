"""Motor inicial de risco para aproximação humano-máquina.

IMPORTANTE: a distância usada aqui é baseada em pixels/caixas. Isso é útil para
protótipo, mas NÃO representa distância física em metros. Para uso industrial,
o sistema deve ser calibrado para cada câmera (homografia, zonas físicas,
profundidade/estéreo ou outro método validado) antes de ser usado como barreira
de segurança.
"""
from math import hypot


def center(box):
    x1, y1, x2, y2 = box
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def box_gap(a, b):
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b
    dx = max(ax1 - bx2, bx1 - ax2, 0)
    dy = max(ay1 - by2, by1 - ay2, 0)
    return hypot(dx, dy)


def assess_risk(detections):
    people = [d for d in detections if d["class_name"] == "human"]
    machines = [d for d in detections if d["class_name"] in {"forklift", "machine"}]
    risks = []

    for person in people:
        for machine in machines:
            gap = box_gap(person["bbox"], machine["bbox"])
            pc = center(person["bbox"])
            mc = center(machine["bbox"])
            center_distance = hypot(pc[0] - mc[0], pc[1] - mc[1])

            # Faixas conservadoras para o protótipo visual. Devem ser calibradas.
            if gap <= 0:
                level = "critical"
            elif gap <= 40:
                level = "high"
            elif gap <= 90:
                level = "medium"
            else:
                level = "safe"

            risks.append({
                "person_track_id": person.get("track_id"),
                "machine_track_id": machine.get("track_id"),
                "machine_class": machine.get("class_name", "machine"),
                "machine_label": machine.get("label", "machine"),
                "gap_pixels": round(gap, 1),
                "center_distance_pixels": round(center_distance, 1),
                "level": level,
            })

    priority = {"critical": 4, "high": 3, "medium": 2, "safe": 1}
    overall = max((r["level"] for r in risks), key=lambda x: priority[x], default="safe")
    return {"level": overall, "pairs": risks}
