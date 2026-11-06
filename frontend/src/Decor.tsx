export function Pine({ className = "" }: { className?: string }) {
  return (
    <svg
      className={`pine ${className}`}
      viewBox="0 0 360 220"
      fill="none"
      aria-hidden="true"
    >
      <g stroke="#315744" strokeLinecap="round">
        <path d="M-20 5Q150 30 340 183" strokeWidth="6" />
        {Array.from({ length: 16 }, (_, i) => {
          const x = i * 20;
          const y = 8 + i * 8;
          return (
            <g key={i} strokeWidth="2">
              <path
                d={`M${x} ${y}l-12 49m17-44l-5 57m13-50l10 54m-13-54l-47 14m54-8l-51-4m63 13l-42-30`}
              />
              <path
                d={`M${x + 2} ${y + 1}l-33 39m39-34l-20 55m29-45l23 38`}
                stroke="#5a7050"
              />
            </g>
          );
        })}
      </g>
      <g fill="#ae4243">
        <circle cx="62" cy="57" r="7" />
        <circle cx="76" cy="64" r="6" />
        <circle cx="66" cy="73" r="5" />
      </g>
    </svg>
  );
}
export function Decor() {
  return (
    <div className="decor" aria-hidden="true">
      <svg
        className="fairy-lights"
        viewBox="0 0 1440 160"
        preserveAspectRatio="none"
      >
        <path
          d="M-20 22Q160 125 350 43Q550 136 745 43Q940 134 1130 38Q1300 116 1460 12"
          fill="none"
          stroke="#7b7546"
          strokeWidth="1.5"
        />
        {[
          [44, 53],
          [112, 76],
          [187, 82],
          [264, 69],
          [397, 64],
          [472, 86],
          [550, 88],
          [625, 78],
          [791, 63],
          [866, 87],
          [945, 89],
          [1026, 76],
          [1170, 57],
          [1240, 74],
          [1318, 68],
          [1386, 43],
        ].map(([x, y], i) => (
          <g key={i}>
            <path d={`M${x} ${y}v8`} stroke="#9d8c5d" />
            <ellipse
              cx={x}
              cy={y + 14}
              rx="3.5"
              ry="6"
              fill="#fbe3a5"
              className="lightbulb"
              style={{ animationDelay: `${i % 5}s` }}
            />
          </g>
        ))}
      </svg>
      <Pine className="pine-left" />
      <Pine className="pine-right" />
      <svg className="bauble bauble-one" viewBox="0 0 90 220">
        <defs>
          <radialGradient id="redBauble" cx=".3" cy=".25">
            <stop stopColor="#c16a62" />
            <stop offset=".6" stopColor="#963e40" />
            <stop offset="1" stopColor="#582c31" />
          </radialGradient>
        </defs>
        <path d="M45 0v106" stroke="#b49b64" />
        <path d="M36 108h18v12H36z" fill="#c9ae70" />
        <circle cx="45" cy="156" r="39" fill="url(#redBauble)" />
        <path
          d="M12 153q33 25 66 0M16 174q29 15 58 0"
          fill="none"
          stroke="#d1ac72"
          strokeWidth="1"
        />
        <path
          d="M36 134l2 6 6 .2-5 4 2 6-5-4-5 4 2-6-5-4 6-.2z"
          fill="#e1bf84"
          opacity=".8"
        />
      </svg>
      <svg className="bauble bauble-two" viewBox="0 0 70 175">
        <defs>
          <radialGradient id="goldBauble" cx=".3" cy=".25">
            <stop stopColor="#f0d597" />
            <stop offset=".7" stopColor="#b8985e" />
            <stop offset="1" stopColor="#6d623c" />
          </radialGradient>
        </defs>
        <path d="M35 0v89" stroke="#b49b64" />
        <path d="M28 90h14v10H28z" fill="#b99a5f" />
        <circle cx="35" cy="128" r="29" fill="url(#goldBauble)" />
        <path
          d="M35 100v56m-16-51q-15 23 0 46m32-46q15 23 0 46"
          fill="none"
          stroke="#f0d79b"
          opacity=".45"
        />
      </svg>
      <div className="snow">
        {Array.from({ length: 19 }, (_, i) => (
          <i
            key={i}
            style={{
              left: `${(i * 37 + 7) % 100}%`,
              top: `${(i * 17 + 13) % 100}%`,
              animationDelay: `-${i * 1.7}s`,
              animationDuration: `${14 + (i % 7)}s`,
              width: i % 3 ? 3 : 5,
              height: i % 3 ? 3 : 5,
            }}
          />
        ))}
      </div>
      <svg className="gift-scene" viewBox="0 0 310 200">
        <defs>
          <linearGradient id="giftRed" x2="1" y2="1">
            <stop stopColor="#b85b53" />
            <stop offset="1" stopColor="#7f343b" />
          </linearGradient>
          <linearGradient id="giftGold" x2="1" y2="1">
            <stop stopColor="#dfc996" />
            <stop offset="1" stopColor="#a68e59" />
          </linearGradient>
        </defs>
        <ellipse
          cx="160"
          cy="185"
          rx="142"
          ry="10"
          fill="#041e18"
          opacity=".2"
        />
        <g transform="translate(97 46) rotate(5 70 70)">
          <path d="M7 38h124v99H7z" fill="url(#giftRed)" />
          <path d="M0 28h138v27H0z" fill="#b76057" />
          <path d="M58 28h20v110H58z" fill="#d3b47d" />
          <path
            d="M68 28C-4 29 24-23 50 0l18 28c72 0 44-51 18-28z"
            fill="none"
            stroke="#d6bc86"
            strokeWidth="10"
          />
        </g>
        <g transform="translate(22 108) rotate(-7 55 35)">
          <path d="M4 20h93v56H4z" fill="url(#giftGold)" />
          <path d="M0 12h102v20H0z" fill="#dbc493" />
          <path d="M42 12h15v64H42z" fill="#71816a" />
          <path
            d="M50 12C0 11 16-21 36-4l14 16c50 0 34-33 14-16z"
            fill="none"
            stroke="#859178"
            strokeWidth="7"
          />
        </g>
        <path
          d="M250 162l4-9 4 9 9 4-9 4-4 9-4-9-9-4zM14 90l3-6 3 6 6 3-6 3-3 6-3-6-6-3z"
          fill="#dbbd7f"
          opacity=".65"
        />
      </svg>
    </div>
  );
}
export function Confetti() {
  return (
    <div className="confetti" aria-hidden="true">
      {Array.from({ length: 44 }, (_, i) => (
        <i
          key={i}
          style={
            {
              left: `${(i * 31) % 100}%`,
              background: ["#d3ae6c", "#b34e4f", "#f3e5bd", "#638c71"][i % 4],
              animationDelay: `${(i % 8) * 0.09}s`,
              "--drift": `${((i % 7) - 3) * 30}px`,
              "--turn": `${i * 63}deg`,
            } as React.CSSProperties
          }
        />
      ))}
    </div>
  );
}
