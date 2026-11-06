import { describe, expect, it } from "vitest";
import { pointedIndex, targetRotation } from "./wheelMath";
describe("the fixed SVG pointer lands on the committed server recipient", () => {
  for (let count = 1; count <= 8; count++) {
    it(`lands on each of ${count} possible segments from any existing rotation`, () => {
      for (const current of [0, 15, 77, 359, 2159, 2567.2, 10000]) {
        for (let winner = 0; winner < count; winner++) {
          const final = targetRotation(current, winner, count);
          expect(final - current).toBeGreaterThanOrEqual(2160);
          expect(pointedIndex(final, count)).toBe(winner);
          expect(
            pointedIndex(targetRotation(current, winner, count, 0), count),
          ).toBe(winner);
        }
      }
    });
  }
  it("rejects inconsistent server segments", () => {
    expect(() => targetRotation(0, -1, 7)).toThrow();
    expect(() => targetRotation(0, 7, 7)).toThrow();
    expect(() => targetRotation(0, 0, 0)).toThrow();
  });
});
