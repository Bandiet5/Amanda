/** Segment zero is centred at twelve o’clock. The fixed pointer is at twelve. */
export function targetRotation(
  current: number,
  winnerIndex: number,
  count: number,
  turns = 6,
): number {
  if (count < 1 || winnerIndex < 0 || winnerIndex >= count)
    throw new Error("Invalid wheel result");
  const target = ((((-winnerIndex * 360) / count) % 360) + 360) % 360;
  const currentAngle = ((current % 360) + 360) % 360;
  return current + turns * 360 + ((target - currentAngle + 360) % 360);
}
export function pointedIndex(rotation: number, count: number): number {
  const angle = ((-rotation % 360) + 360) % 360;
  return Math.round(angle / (360 / count)) % count;
}
