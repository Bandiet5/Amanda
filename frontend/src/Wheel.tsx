import { useId } from "react";
import type { Person } from "./types";

const palette = [
  "#174f40",
  "#9b343c",
  "#c5a265",
  "#2b6150",
  "#ab4648",
  "#52623d",
  "#c7ac79",
  "#7d2e39",
];
function point(angle: number, radius: number) {
  const r = ((angle - 90) * Math.PI) / 180;
  return [200 + radius * Math.cos(r), 200 + radius * Math.sin(r)];
}
export function Wheel({
  segments,
  rotation,
  duration,
  spinning,
}: {
  segments: Person[];
  rotation: number;
  duration: number;
  spinning: boolean;
}) {
  const uid = useId().replaceAll(":", "");
  const count = segments.length || 1;
  return (
    <div className={`wheel-scene ${spinning ? "is-spinning" : ""}`}>
      <div className="wheel-halo" />
      <svg className="wheel-stand" viewBox="0 0 440 500" aria-hidden="true">
        <defs>
          <linearGradient id={`${uid}stand`}>
            <stop stopColor="#9b743b" />
            <stop offset=".5" stopColor="#edce89" />
            <stop offset="1" stopColor="#967137" />
          </linearGradient>
        </defs>
        <path d="M197 375h46l18 97h-82z" fill={`url(#${uid}stand)`} />
        <path d="M155 478q65-22 130 0l7 11H148z" fill={`url(#${uid}stand)`} />
        <ellipse cx="220" cy="492" rx="83" ry="6" fill="#000" opacity=".12" />
      </svg>
      <div className="wheel-frame">
        <div className="wheel-pointer" aria-hidden="true">
          <svg viewBox="0 0 36 50">
            <path
              d="M3 5Q18-1 33 5L18 46z"
              fill="#eed7a5"
              stroke="#a8864f"
              strokeWidth="2"
            />
            <circle cx="18" cy="10" r="4" fill="#a77a3c" />
          </svg>
        </div>
        <svg
          className="wheel-svg"
          viewBox="0 0 400 400"
          role="img"
          aria-label={`Christmas wheel${segments.length ? ": " + segments.map((s) => s.name).join(", ") : ""}`}
        >
          <defs>
            <radialGradient id={`${uid}rim`}>
              <stop offset=".88" stopColor="#9f763a" />
              <stop offset=".92" stopColor="#f2dca4" />
              <stop offset=".97" stopColor="#d1ad69" />
              <stop offset="1" stopColor="#9c743c" />
            </radialGradient>
            <radialGradient id={`${uid}hub`} cx=".35" cy=".25">
              <stop stopColor="#fff8df" />
              <stop offset=".75" stopColor="#e6ce94" />
              <stop offset="1" stopColor="#b99557" />
            </radialGradient>
            <radialGradient id={`${uid}shade`}>
              <stop offset=".4" stopColor="#fff" stopOpacity=".08" />
              <stop offset="1" stopColor="#000" stopOpacity=".15" />
            </radialGradient>
          </defs>
          <circle cx="200" cy="200" r="199" fill={`url(#${uid}rim)`} />
          <circle cx="200" cy="200" r="189" fill="#eedbad" />
          <g
            data-testid="wheel-rotor"
            style={{
              transform: `rotate(${rotation}deg)`,
              transformOrigin: "200px 200px",
              transition: `transform ${duration}ms cubic-bezier(.12,.72,.12,1)`,
            }}
          >
            {segments.map((segment, i) => {
              const angle = 360 / count;
              const start = point(i * angle - angle / 2, 183);
              const end = point(i * angle + angle / 2, 183);
              const label =
                segment.name.length > 12
                  ? segment.name.slice(0, 10) + "…"
                  : segment.name;
              return (
                <g key={segment.id}>
                  <title>{segment.name}</title>
                  {count === 1 ? (
                    <circle cx="200" cy="200" r="183" fill={palette[0]} />
                  ) : (
                    <path
                      d={`M200 200L${start.join(" ")}A183 183 0 ${angle > 180 ? 1 : 0} 1 ${end.join(" ")}Z`}
                      fill={palette[i % palette.length]}
                      stroke="#ead4a0"
                      strokeWidth="1"
                    />
                  )}
                  <g transform={`rotate(${i * angle} 200 200)`}>
                    <path
                      d="M200 39l2.3 6.6 7 .2-5.6 4.3 2 6.7-5.7-4-5.7 4 2-6.7-5.6-4.3 7-.2z"
                      fill="#f4dfae"
                      opacity=".75"
                    />
                    <text
                      x="200"
                      y="89"
                      textAnchor="middle"
                      fill={
                        [2, 6].includes(i % palette.length)
                          ? "#173b2b"
                          : "#fff7df"
                      }
                      fontFamily="DM Sans, sans-serif"
                      fontSize={segment.name.length > 9 ? 17 : 21}
                      fontWeight="600"
                      dominantBaseline="middle"
                      style={{
                        transform: `rotate(${-i * angle - rotation}deg)`,
                        transformOrigin: "200px 89px",
                        transition: `transform ${duration}ms cubic-bezier(.12,.72,.12,1)`,
                      }}
                    >
                      {label}
                    </text>
                    <circle
                      cx="200"
                      cy="130"
                      r="2"
                      fill="#eed7a5"
                      opacity=".7"
                    />
                  </g>
                </g>
              );
            })}
            {!segments.length && (
              <circle cx="200" cy="200" r="183" fill="#235847" />
            )}
            <circle
              cx="200"
              cy="200"
              r="183"
              fill={`url(#${uid}shade)`}
              pointerEvents="none"
            />
          </g>
          {Array.from({ length: 48 }, (_, i) => {
            const [x, y] = point(i * 7.5, 193.5);
            return (
              <circle
                key={i}
                cx={x}
                cy={y}
                r="1.6"
                fill={i % 2 ? "#f7e4b2" : "#9e773c"}
              />
            );
          })}
          <circle
            cx="200"
            cy="200"
            r="46"
            fill="#000"
            opacity=".13"
            transform="translate(1 3)"
          />
          <circle
            cx="200"
            cy="200"
            r="44"
            fill={`url(#${uid}hub)`}
            stroke="#f7e6bc"
            strokeWidth="2"
          />
          <g
            fill="none"
            stroke="#856631"
            strokeWidth="2.3"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M181 195h38v26h-38zM178 188h44v8h-44zM200 188v33" />
            <path d="M200 188c-23 0-20-21-9-14l9 14c23 0 20-21 9-14z" />
          </g>
          <circle
            cx="200"
            cy="200"
            r="36"
            fill="none"
            stroke="#b79555"
            strokeWidth=".6"
          />
        </svg>
      </div>
      <div className="wheel-spark spark-one" aria-hidden="true">
        ✧
      </div>
      <div className="wheel-spark spark-two" aria-hidden="true">
        ✦
      </div>
      <div className="wheel-spark spark-three" aria-hidden="true">
        ✧
      </div>
    </div>
  );
}
