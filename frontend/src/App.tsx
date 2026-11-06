import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  Check,
  ChevronDown,
  Gift,
  Heart,
  LockKeyhole,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import { api, message } from "./api";
import { Confetti, Decor } from "./Decor";
import { Wheel } from "./Wheel";
import { CelebrationBurst, GiftReveal } from "./GiftReveal";
import { targetRotation } from "./wheelMath";
import { useDialog } from "./useDialog";
import type { State } from "./types";

type Phase =
  "idle" | "claiming" | "requesting" | "spinning" | "result" | "recovering";
const recoveryToken = new URLSearchParams(location.hash.slice(1)).get(
  "recover",
);
if (recoveryToken) history.replaceState(null, "", location.pathname);
const sleep = (ms: number) =>
  new Promise((resolve) => window.setTimeout(resolve, ms));

export function Brand({ admin = false }: { admin?: boolean }) {
  return (
    <a className="brand" href="/" aria-label="Amanda se Kersfees home">
      <span className="brand-icon">
        <Gift size={19} />
      </span>
      <span>
        AMANDA SE KERSFEES
        <span className="brand-sub">
          {admin
            ? "A LITTLE BEHIND-THE-SCENES MAGIC"
            : "A LITTLE CHRISTMAS MAGIC"}
        </span>
      </span>
    </a>
  );
}
export function App() {
  const [state, setState] = useState<State | null>(null);
  const stateRef = useRef<State | null>(null);
  const [phase, setPhaseState] = useState<Phase>("idle");
  const phaseRef = useRef<Phase>("idle");
  const [selected, setSelected] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState("");
  const [uncertain, setUncertain] = useState(false);
  const [recovery, setRecovery] = useState(recoveryToken);
  const [rotation, setRotation] = useState(0);
  const rotationRef = useRef(0);
  const [duration, setDuration] = useState(0);
  const [celebrate, setCelebrate] = useState(false);
  const [rulesOpen, setRulesOpen] = useState(false);
  const rulesRef = useRef<HTMLDivElement>(null);
  const closeRules = useCallback(() => setRulesOpen(false), []);
  useDialog(rulesOpen, rulesRef, closeRules);
  const animationId = useRef(0);
  const replayHandler = useRef<(next: State) => void>(() => {});

  const phaseTo = useCallback((next: Phase) => {
    phaseRef.current = next;
    setPhaseState(next);
  }, []);
  const applyState = useCallback(
    (next: State) => {
      const old = stateRef.current;
      if (
        old &&
        (next.event_id < old.event_id ||
          (next.event_id === old.event_id && next.revision < old.revision))
      )
        return;
      const changed =
        old &&
        (old.event_id !== next.event_id ||
          old.participant?.id !== next.participant?.id ||
          old.participant?.draw_version !== next.participant?.draw_version ||
          old.binding_lost !== next.binding_lost);
      stateRef.current = next;
      setState(next);
      if (!old || changed) {
        setSelected("");
        setConfirming(false);
        animationId.current += 1;
        const restored = next.draw
          ? targetRotation(
              0,
              next.draw.segments.findIndex(
                (p) => p.id === next.draw!.recipient.id,
              ),
              next.draw.segments.length,
              0,
            )
          : 0;
        rotationRef.current = restored;
        setRotation(restored);
        setDuration(0);
        setCelebrate(false);
        phaseTo(next.draw ? "result" : "idle");
        if (
          changed &&
          old.participant &&
          old.event_id === next.event_id &&
          !next.participant &&
          !next.binding_lost
        )
          setError(
            "Amanda has reset your name and draw. Please choose your own name again.",
          );
      } else if (
        old.participant &&
        next.participant &&
        next.draw &&
        old.participant.replay_version !== next.participant.replay_version &&
        !["requesting", "spinning"].includes(phaseRef.current)
      ) {
        replayHandler.current(next);
      } else if (
        !["requesting", "spinning", "claiming", "recovering"].includes(
          phaseRef.current,
        )
      ) {
        phaseTo(next.draw ? "result" : "idle");
      }
    },
    [phaseTo],
  );
  const refresh = useCallback(async () => {
    const next = await api<State>("/state");
    applyState(next);
    return next;
  }, [applyState]);

  useEffect(() => {
    let active = true;
    const check = () => {
      if (active && !document.hidden) void refresh().catch(() => {});
    };
    void refresh().catch((e) => {
      if (active) setError(message(e));
    });
    const interval = window.setInterval(check, 5000);
    window.addEventListener("focus", check);
    document.addEventListener("visibilitychange", check);
    return () => {
      active = false;
      window.clearInterval(interval);
      window.removeEventListener("focus", check);
      document.removeEventListener("visibilitychange", check);
      animationId.current += 1;
    };
  }, [refresh]);

  async function animateDraw(next: State) {
    if (!next.draw) return;
    const ticket = ++animationId.current;
    const reduced = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    const milliseconds = reduced ? 350 : 5500;
    setCelebrate(false);
    setDuration(0);
    phaseTo("spinning");
    // Paint the server's exact segments before changing the rotation.
    await new Promise<void>((resolve) =>
      requestAnimationFrame(() => requestAnimationFrame(() => resolve())),
    );
    if (animationId.current !== ticket) return;
    const winner = next.draw.segments.findIndex(
      (p) => p.id === next.draw!.recipient.id,
    );
    const target = targetRotation(
      rotationRef.current,
      winner,
      next.draw.segments.length,
      reduced ? 0 : 6,
    );
    setDuration(milliseconds);
    rotationRef.current = target;
    setRotation(target);
    await sleep(milliseconds + 100);
    if (animationId.current !== ticket) return;
    try {
      const verified = await refresh();
      if (
        animationId.current !== ticket ||
        verified.event_id !== next.event_id ||
        verified.participant?.draw_version !== next.participant?.draw_version ||
        verified.draw?.recipient.id !== next.draw.recipient.id
      )
        return;
      phaseTo("result");
      setCelebrate(true);
      setUncertain(false);
    } catch {
      phaseTo("idle");
      setUncertain(true);
      setError(
        "Your spin has finished. Reconnect so we can confirm your current saved result.",
      );
    }
  }
  replayHandler.current = (next) => {
    void animateDraw(next);
  };

  async function claim() {
    if (!state || phaseRef.current !== "idle") return;
    phaseTo("claiming");
    setError("");
    try {
      const next = await api<State>("/claim", {
        csrf: state.csrf,
        body: { event_id: state.event_id, participant_id: Number(selected) },
      });
      applyState(next);
      setConfirming(false);
      phaseTo(next.draw ? "result" : "idle");
    } catch (e) {
      setError(message(e));
      phaseTo("idle");
      setConfirming(false);
      await refresh().catch(() => {});
    }
  }
  async function spin() {
    const current = stateRef.current;
    if (
      !current?.participant ||
      current.draw ||
      uncertain ||
      ["requesting", "spinning"].includes(phaseRef.current)
    )
      return;
    phaseTo("requesting");
    setError("");
    try {
      const next = await api<State>("/draw", {
        csrf: current.csrf,
        body: {
          event_id: current.event_id,
          draw_version: current.participant.draw_version,
        },
      });
      applyState(next);
      const latest = stateRef.current;
      if (
        latest &&
        next.event_id === latest.event_id &&
        next.participant?.draw_version === latest.participant?.draw_version
      )
        await animateDraw(latest);
    } catch (e) {
      setError(message(e));
      try {
        const recovered = await refresh();
        if (recovered.draw) {
          phaseTo("result");
          setError(
            "Your draw was saved safely. Your original result is shown below.",
          );
        } else {
          phaseTo("idle");
          setUncertain(false);
        }
      } catch {
        phaseTo("idle");
        setUncertain(true);
      }
    }
  }
  async function checkSavedState() {
    setError("");
    phaseTo("recovering");
    try {
      const next = await refresh();
      setUncertain(false);
      phaseTo(next.draw ? "result" : "idle");
    } catch (e) {
      setError(message(e));
      phaseTo("idle");
    }
  }
  async function useRecovery() {
    if (!state || !recovery) return;
    phaseTo("recovering");
    setError("");
    try {
      const next = await api<State>("/recover", {
        csrf: state.csrf,
        body: { token: recovery },
      });
      applyState(next);
      setRecovery(null);
      phaseTo(next.draw ? "result" : "idle");
    } catch (e) {
      setError(message(e));
      phaseTo("idle");
    }
  }
  const person = state?.participant;
  const chosen = state?.participants.find((p) => String(p.id) === selected);
  const busy = ["requesting", "spinning", "claiming", "recovering"].includes(
    phase,
  );
  const result = phase === "result" && state?.draw;
  const stage =
    !person || recovery || state?.binding_lost
      ? "choose"
      : result
        ? "reveal"
        : "wheel";
  const mainRef = useRef<HTMLElement>(null);
  useEffect(() => {
    mainRef.current?.focus({ preventScroll: true });
    window.scrollTo({ top: 0, behavior: "instant" });
  }, [stage]);

  return (
    <div className="site-shell christmas-journey">
      <Decor />
      {celebrate && <Confetti />}
      <header className="site-header">
        <Brand />
        <a className="admin-link" href="/admin">
          <LockKeyhole size={14} />
          <span>Amanda’s corner</span>
        </a>
      </header>
      <main
        ref={mainRef}
        tabIndex={-1}
        className={`journey-main journey-stage-${stage}`}
        data-stage={stage}
      >
        <div className="eyebrow hero-eyebrow">
          <span /> THE SEASON OF GIVING <span />
        </div>
        <div className="hero-title journey-title">
          <h1>
            Amanda se <em>Kersfees</em>
            <span className="title-star" aria-hidden="true">
              ✧
            </span>
          </h1>
          <p>
            {stage === "choose"
              ? "Your name. A little spin. A Christmas surprise."
              : stage === "wheel"
                ? "A little spin of Christmas magic, just for you."
                : "A little secret, wrapped in Christmas joy."}
          </p>
        </div>
        <ol className="journey-steps" aria-label="Your Christmas journey">
          {["Choose your name", "Spin the wheel", "Meet your recipient"].map(
            (label, index) => {
              const current =
                stage === "choose" ? 0 : stage === "wheel" ? 1 : 2;
              return (
                <li
                  key={label}
                  className={
                    index === current
                      ? "current"
                      : index < current
                        ? "complete"
                        : ""
                  }
                  aria-current={index === current ? "step" : undefined}
                >
                  <span>
                    {index < current ? <Check size={15} /> : index + 1}
                  </span>
                  <strong>{label}</strong>
                </li>
              );
            },
          )}
        </ol>
        {error && (
          <div className="alert journey-alert" role="alert">
            {error}
            <button
              className="alert-close"
              onClick={() => setError("")}
              aria-label="Dismiss message"
            >
              <X size={16} />
            </button>
          </div>
        )}

        {stage === "choose" && (
          <section className="choose-stage" aria-label="Choose your name">
            <div className="choose-introduction">
              <div className="choose-gift-emblem">
                <Gift size={30} />
              </div>
              <h2>
                A little giving.
                <br />
                <em>A lot of Christmas joy.</em>
              </h2>
              <p>
                Choose your name below. Then we’ll find the person you’re buying
                a present for.
              </p>
            </div>
            <div className="claim-card journey-claim-card">
              {!state ? (
                <div className="loading-card">
                  <Sparkles className="twinkle" size={25} />
                  <p>Getting the Christmas magic ready…</p>
                  {error && (
                    <button
                      className="button secondary"
                      onClick={() => void checkSavedState()}
                    >
                      Reconnect
                    </button>
                  )}
                </div>
              ) : recovery ? (
                <>
                  <div className="card-label">
                    <ShieldCheck size={19} /> YOUR PERSONAL RECOVERY LINK
                  </div>
                  <h3>A fresh link to your Christmas magic.</h3>
                  <p className="muted">
                    Reconnect this browser to your name. Your saved recipient
                    stays the same.
                  </p>
                  <button
                    className="button primary"
                    onClick={() => void useRecovery()}
                    disabled={busy}
                  >
                    {busy ? "Reconnecting…" : "Reconnect my browser"}
                    <ArrowRight size={19} />
                  </button>
                </>
              ) : state.binding_lost ? (
                <>
                  <div className="card-label">
                    <ShieldCheck size={19} /> YOUR BROWSER LINK WAS RESET
                  </div>
                  <h3>Amanda can help you reconnect.</h3>
                  <p className="muted">
                    Open the recovery link from Amanda on this phone. Your saved
                    draw will still be there.
                  </p>
                </>
              ) : (
                <>
                  <label className="field-label" htmlFor="participant">
                    First things first, who are you?
                  </label>
                  <div className="select-wrap">
                    <Users size={20} />
                    <select
                      id="participant"
                      value={selected}
                      onChange={(e) => {
                        setSelected(e.target.value);
                        setConfirming(false);
                      }}
                      disabled={busy}
                    >
                      <option value="">Choose your name</option>
                      {state.participants.filter((p) => !p.claimed).map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.name}
                        </option>
                      ))}
                    </select>
                    <ChevronDown size={20} />
                  </div>
                  {confirming && chosen ? (
                    <div className="confirm-name">
                      <p>
                        This browser will be linked to{" "}
                        <strong>{chosen.name}</strong>, so your name and saved
                        draw will be here when you come back.
                      </p>
                      <div className="confirm-actions">
                        <button
                          className="button primary"
                          onClick={() => void claim()}
                          disabled={busy}
                        >
                          {busy ? "Saving your name…" : `I am ${chosen.name}`}
                          <Check size={19} />
                        </button>
                        <button
                          className="text-button"
                          onClick={() => setConfirming(false)}
                          disabled={busy}
                        >
                          Go back
                        </button>
                      </div>
                    </div>
                  ) : (
                    <button
                      className="button primary"
                      disabled={!chosen || chosen.claimed || busy}
                      onClick={() => setConfirming(true)}
                    >
                      That’s me, let’s begin
                      <ArrowRight size={19} />
                    </button>
                  )}
                  <div className="privacy-note">
                    <ShieldCheck size={17} />
                    <span>
                      Choose your own name. You’ll only need to do this once on
                      this browser.
                    </span>
                  </div>
                </>
              )}
            </div>
            <p className="choose-footnote">
              <Heart size={16} /> Everyone gives. Everyone receives.
            </p>
          </section>
        )}

        <div
          className={`journey-scene ${result ? "journey-scene-reveal" : "journey-scene-wheel"}`}
          hidden={stage === "choose"}
        >
          <section
            className="journey-wheel-column"
            aria-label="Christmas gift wheel"
          >
            <div className="wheel-stage-heading">
              <h2>
                {result ? (
                  <>
                    The wheel has <em>chosen.</em>
                  </>
                ) : (
                  <>Welcome, {person?.name}</>
                )}
              </h2>
              <p>
                {result
                  ? "Your Christmas mission is wrapped up."
                  : phase === "spinning"
                    ? "A little Christmas magic is on its way…"
                    : "Your surprise is just a spin away."}
              </p>
            </div>
            <div className="wheel-3d-stage" data-testid="wheel-3d-stage">
              {result && celebrate && <CelebrationBurst />}
              <div className="wheel-floor" aria-hidden="true" />
              <div className="wheel-3d-entrance">
                <div className="wheel-3d-object">
                  <Wheel
                    segments={state?.segments ?? []}
                    rotation={rotation}
                    duration={duration}
                    spinning={phase === "spinning"}
                  />
                </div>
              </div>
            </div>
            {!result && (
              <div className="journey-spin-controls">
                {uncertain ? (
                  <button
                    className="button primary"
                    onClick={() => void checkSavedState()}
                    disabled={busy}
                  >
                    Check my saved draw
                    <RotateCcw size={19} />
                  </button>
                ) : (
                  <button
                    className="button primary spin-button"
                    disabled={busy || !state?.segments.length}
                    onClick={() => void spin()}
                  >
                    <Gift size={21} />
                    {phase === "spinning"
                      ? "A little Christmas magic…"
                      : phase === "requesting"
                        ? "Saving your surprise…"
                        : "Spin my Christmas draw"}
                    {!busy && <ArrowRight size={19} />}
                  </button>
                )}
                <p>
                  <ShieldCheck size={16} />
                  {busy
                    ? "Your result is being saved safely."
                    : "One spin. One thoughtful Christmas gift."}
                </p>
              </div>
            )}
          </section>
          {result && (
            <GiftReveal
              name={state!.draw!.recipient.name}
              replay={() => void animateDraw(state!)}
            />
          )}
        </div>
        <div className="journey-bottom-bar">
          <div className="progress-pill">
            <span className="live-dot" />
            <span>
              <strong>{state?.completed_count ?? 0}</strong> of{" "}
              {state?.total ?? 8} Christmas surprises revealed
            </span>
          </div>
          <button
            className="journey-help"
            onClick={() => setRulesOpen(true)}
            aria-label="A secret worth keeping: how it works"
          >
            <ShieldCheck size={16} /> How does it work?
          </button>
        </div>
      </main>
      <footer className="site-footer">
        <span>Made with a little love & a lot of Christmas spirit.</span>
        <span className="footer-signoff">
          With love, Amanda <Heart size={12} />
        </span>
      </footer>
      <div className="sr-only" role="status" aria-live="polite">
        {phase === "spinning"
          ? "The wheel is spinning."
          : result
            ? `Your saved recipient is ${state.draw!.recipient.name}.`
            : ""}
      </div>
      {rulesOpen && (
        <div className="modal-backdrop" onClick={() => setRulesOpen(false)}>
          <div
            className="modal"
            ref={rulesRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="rules-title"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="modal-close"
              onClick={() => setRulesOpen(false)}
              aria-label="Close explanation"
              autoFocus
            >
              <X size={20} />
            </button>
            <Gift className="modal-gift" size={28} />
            <h2 id="rules-title">
              A little giving.
              <br />
              <em>A lot of joy.</em>
            </h2>
            <p>
              Choose your own name and confirm it on your phone. Spin once to
              reveal who you’re buying for. Everyone gives one gift and receives
              one, and nobody draws themselves.
            </p>
            <p>
              Your name and recipient stay linked to this browser. Come back any
              time to see your saved result. This is a trusted office exchange;
              the browser link is a convenience, rather than verified identity.
            </p>
            <p>
              If you choose the wrong name or change phones, ask Amanda for a
              recovery link. She can also replay your reveal without changing
              your recipient.
            </p>
            <button
              className="button primary"
              onClick={() => setRulesOpen(false)}
            >
              Let the magic begin
              <ArrowRight size={17} />
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
