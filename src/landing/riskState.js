// One illustrative scale for the text, diagram and WebGL scene.
export function riskState(distance) {
  if (distance > 3) return { label: "SEGURO", color: 0x8dbca6 };
  if (distance > 1.5) return { label: "ATENÇÃO", color: 0xe6bc69 };
  return { label: "CRÍTICO", color: 0xf08c7f };
}

export const distanceAt = (progress) => Math.round((4.8 - progress * 4) * 10) / 10;
