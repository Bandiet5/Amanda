import type { CSSProperties } from "react";
import { Heart, RotateCcw, ShieldCheck } from "lucide-react";

function Present({
  tone,
  position,
  name,
}: {
  tone: string;
  position: string;
  name?: string;
}) {
  return (
    <div className={`present-drop present-drop--${position}`}>
      <div className={`present-cube present-cube--${tone}`}>
        <div className="present-face present-front" />
        <div className="present-face present-side" />
        <div className="present-face present-left" />
        <div className="present-face present-top" />
        <div className="present-lid">
          <div className="lid-front" />
          <div className="lid-side" />
          <div className="lid-left" />
          <div className="lid-top" />
          <div className="present-bow">
            <i />
            <i />
            <b />
          </div>
        </div>
        {name && (
          <div className="present-name-tag">
            <Heart size={12} />
            <span>For {name}</span>
          </div>
        )}
      </div>
    </div>
  );
}

export function GiftReveal({
  name,
  replay,
}: {
  name: string;
  replay: () => void;
}) {
  return (
    <section
      className="gift-reveal result-card"
      data-testid="result-card"
      aria-labelledby="gift-recipient"
    >
      <div className="reveal-eyebrow">
        <span /> YOUR CHRISTMAS SURPRISE <span />
      </div>
      <p>You’re buying a Christmas present for</p>
      <div className="gift-name-drop" data-testid="gift-name-drop">
        <h2
          id="gift-recipient"
          className={`recipient-name-3d${name.length > 12 ? " recipient-name--long" : ""}`}
          data-testid="recipient-name"
          data-name={name}
          aria-label={name}
        >
          <span>{name}</span>
        </h2>
        <span className="recipient-name-plinth" aria-hidden="true" />
      </div>
      <div className="gift-stack" data-testid="gift-stack" aria-hidden="true">
        <div className="gift-floor-light" />
        <div className="gift-floor-shadow" />
        <Present tone="green" position="left" />
        <Present tone="cream" position="right" />
        <Present tone="red" position="centre" name={name} />
        <span className="gift-star gift-star-one">✧</span>
        <span className="gift-star gift-star-two">✦</span>
        <span className="gift-star gift-star-three">✧</span>
      </div>
      <p className="gift-message">
        One thoughtful gift. One very lucky person.
      </p>
      <div className="gift-saved">
        <ShieldCheck size={16} /> Saved for when you come back
      </div>
      <button className="button gift-replay" onClick={replay}>
        <RotateCcw size={17} /> Replay the Christmas magic
      </button>
      <p className="gift-secret">
        <Heart size={14} /> Keep it a secret until the big exchange.
      </p>
    </section>
  );
}

export function CelebrationBurst() {
  return (
    <div
      className="celebration-bursts"
      data-testid="celebration-bursts"
      aria-hidden="true"
    >
      {[0, 1, 2, 3].map((burst) => (
        <div key={burst} className={`celebration-burst burst-${burst}`}>
          {Array.from({ length: 12 }, (_, index) => (
            <i
              key={index}
              style={
                {
                  "--ray": `${index * 30}deg`,
                  "--burst-delay": `${burst * 0.55}s`,
                } as CSSProperties
              }
            >
              <b />
            </i>
          ))}
        </div>
      ))}
    </div>
  );
}
