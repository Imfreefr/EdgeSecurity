window.RiskEngine = (() => {
  function center(b) {
    return [(b[0] + b[2]) / 2, (b[1] + b[3]) / 2];
  }
  function boxGap(a, b) {
    const dx = Math.max(a[0] - b[2], b[0] - a[2], 0);
    const dy = Math.max(a[1] - b[3], b[1] - a[3], 0);
    return Math.hypot(dx, dy);
  }
  function assess(detections, { frame_width = 640 } = {}) {
    if (!Number.isFinite(frame_width) || frame_width <= 0) {
      throw new Error("Largura do frame inválida para aproximação visual.");
    }
    const referenceScale = 640 / frame_width;
    // Class 2 is an occupant, not an outside pedestrian. Legacy detections
    // without a class ID remain supported when explicitly named human.
    const people = detections.filter((d) =>
      d.class_id === 0 || (d.class_id == null && d.class_name === "human"));
    const machines = detections.filter((d) => d.class_name === "forklift" || d.class_name === "machine");
    const risks = [];
    for (const p of people) {
      for (const m of machines) {
        const gap = boxGap(p.bbox, m.bbox);
        const referenceGap = gap * referenceScale;
        const pc = center(p.bbox);
        const mc = center(m.bbox);
        const cd = Math.hypot(pc[0] - mc[0], pc[1] - mc[1]);
        let level = "safe";
        if (referenceGap <= 0) level = "critical";
        else if (referenceGap <= 40) level = "high";
        else if (referenceGap <= 90) level = "medium";
        risks.push({ person_track_id: p.track_id ?? null, machine_track_id: m.track_id ?? null, gap_pixels: Math.round(gap * 10) / 10, gap_reference_pixels: Math.round(referenceGap * 10) / 10, center_distance_pixels: Math.round(cd * 10) / 10, level });
      }
    }
    const prio = { critical: 4, high: 3, medium: 2, safe: 1 };
    let overall = "safe";
    let best = 0;
    for (const r of risks) if ((prio[r.level] || 0) > best) { best = prio[r.level]; overall = r.level; }
    return { level: overall, pairs: risks };
  }
  return { assess, center, boxGap };
})();
