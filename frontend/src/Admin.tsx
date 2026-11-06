import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type FormEvent,
} from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  Copy,
  Eye,
  EyeOff,
  Gift,
  KeyRound,
  Link,
  LockKeyhole,
  LogOut,
  RotateCcw,
  ShieldCheck,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import { api, ApiError, message } from "./api";
import { Brand } from "./App";
import { Decor } from "./Decor";
import type { AdminPerson, Dashboard } from "./types";
import { useDialog } from "./useDialog";

type Action = {
  kind: "recovery" | "new-draw" | "reset" | "reveal";
  person?: AdminPerson;
};
const date = (value: string | null) =>
  value
    ? new Intl.DateTimeFormat("en-ZA", {
        dateStyle: "medium",
        timeStyle: "short",
      }).format(new Date(value))
    : "—";
const auditLabels: Record<string, string> = {
  admin_login: "Admin signed in",
  admin_login_failed: "Unsuccessful admin sign-in",
  admin_logout: "Admin signed out",
  admin_password_changed: "Admin password updated",
  participant_names_updated: "Participant names updated",
  assignments_revealed: "Secret assignments revealed",
  animation_replayed: "Animation replay requested",
  new_draw_granted: "New draw granted; previous recipient released",
  browser_binding_reset: "Browser link reset; recovery link created",
  recovery_link_used: "One-use recovery link redeemed",
  entire_event_reset: "Entire event reset for a new round",
};

export function Admin() {
  const [auth, setAuth] = useState<boolean | null>(null);
  const [csrf, setCsrf] = useState("");
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [editing, setEditing] = useState(false);
  const [names, setNames] = useState<string[]>([]);
  const [savedNames, setSavedNames] = useState<string[]>([]);
  const namesEvent = useRef<number | null>(null);
  const [assignments, setAssignments] = useState<Record<number, string> | null>(
    null,
  );
  const revealRevision = useRef<number | null>(null);
  const [action, setAction] = useState<Action | null>(null);
  const [recoveryUrl, setRecoveryUrl] = useState("");
  const [copied, setCopied] = useState(false);
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeDialog = useCallback(() => {
    if (!busyRef.current) {
      setAction(null);
      setRecoveryUrl("");
      setCopied(false);
    }
  }, []);
  useDialog(!!action, dialogRef, closeDialog);

  const loadDashboard = useCallback(async () => {
    try {
      const next = await api<Dashboard>("/admin/dashboard");
      setDashboard((old) =>
        !old ||
        next.event_id > old.event_id ||
        (next.event_id === old.event_id && next.revision >= old.revision)
          ? next
          : old,
      );
      if (
        revealRevision.current !== null &&
        next.revision !== revealRevision.current
      ) {
        setAssignments(null);
        revealRevision.current = null;
      }
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setAuth(false);
        setAssignments(null);
        setDashboard(null);
        const session = await api<{ csrf: string }>("/admin/session");
        setCsrf(session.csrf);
      } else throw e;
    }
  }, []);
  useEffect(() => {
    void api<{ authenticated: boolean; csrf: string }>("/admin/session")
      .then((s) => {
        setAuth(s.authenticated);
        setCsrf(s.csrf);
      })
      .catch((e) => setError(message(e)));
  }, []);
  useEffect(() => {
    if (!auth) return;
    void loadDashboard().catch((e) => setError(message(e)));
    const timer = window.setInterval(() => {
      if (!document.hidden && !busyRef.current)
        void loadDashboard().catch(() => {});
    }, 8000);
    return () => window.clearInterval(timer);
  }, [auth, loadDashboard]);
  useEffect(() => {
    if (!dashboard) return;
    if (!editing || namesEvent.current !== dashboard.event_id) {
      const current = dashboard.participants.map((person) => person.name);
      setNames(current);
      setSavedNames(current);
      setEditing(false);
      namesEvent.current = dashboard.event_id;
    }
  }, [dashboard, editing]);

  function setWorking(value: boolean) {
    busyRef.current = value;
    setBusy(value);
  }
  async function login(event: FormEvent) {
    event.preventDefault();
    if (busyRef.current || !csrf) return;
    setWorking(true);
    setError("");
    try {
      const session = await api<{ authenticated: boolean; csrf: string }>(
        "/admin/login",
        { csrf, body: { password } },
      );
      setCsrf(session.csrf);
      setAuth(true);
      setPassword("");
    } catch (e) {
      setError(message(e));
    } finally {
      setWorking(false);
    }
  }
  async function logout() {
    if (busyRef.current) return;
    setWorking(true);
    try {
      await api("/admin/logout", { csrf, body: {} });
      setAuth(false);
      setDashboard(null);
      setAssignments(null);
      const s = await api<{ csrf: string }>("/admin/session");
      setCsrf(s.csrf);
    } catch (e) {
      setError(message(e));
    } finally {
      setWorking(false);
    }
  }
  function openAction(next: Action) {
    setAction(next);
    setError("");
    setRecoveryUrl("");
  }
  async function replay(person: AdminPerson) {
    if (!dashboard || busyRef.current) return;
    setWorking(true);
    setError("");
    try {
      await api(`/admin/participants/${person.id}/replay`, {
        csrf,
        body: { event_id: dashboard.event_id },
      });
      setNotice(
        `Replay requested for ${person.name}. Their recipient stays the same; their open page will replay within a few seconds.`,
      );
      await loadDashboard();
    } catch (e) {
      setError(message(e));
    } finally {
      setWorking(false);
    }
  }
  async function executeAction(event: FormEvent) {
    event.preventDefault();
    if (!action || !dashboard || busyRef.current) return;
    setWorking(true);
    setError("");
    try {
      if (action.kind === "reveal") {
        const response = await api<{
          revision: number;
          assignments: { giver_id: number; recipient: string }[];
        }>("/admin/reveal", {
          csrf,
          body: { confirmation: "REVEAL ASSIGNMENTS" },
        });
        revealRevision.current = response.revision;
        setAssignments(
          Object.fromEntries(
            response.assignments.map((a) => [a.giver_id, a.recipient]),
          ),
        );
        setAction(null);
      } else if (action.kind === "reset") {
        await api("/admin/reset", {
          csrf,
          body: {
            event_id: dashboard.event_id,
            confirmation: "RESET ENTIRE EVENT",
          },
        });
        setAssignments(null);
        setEditing(false);
        setAction(null);
        setNotice(
          "A fresh Christmas round is ready. All claims and draws have been cleared, and old browser links are invalid.",
        );
      } else if (action.kind === "new-draw") {
        await api(`/admin/participants/${action.person!.id}/new-draw`, {
          csrf,
          body: {
            event_id: dashboard.event_id,
            draw_version: action.person!.draw_version,
            confirmation: "NEW DRAW",
          },
        });
        setAction(null);
        setAssignments(null);
        setNotice(
          `${action.person!.name} can draw again. Everyone else’s completed assignment has been preserved.`,
        );
      } else {
        const response = await api<{ recovery_url: string }>(
          `/admin/participants/${action.person!.id}/recovery`,
          {
            csrf,
            body: {
              event_id: dashboard.event_id,
              confirmation: "RESET BROWSER LINK",
            },
          },
        );
        setRecoveryUrl(response.recovery_url);
        setNotice(
          `${action.person!.name}’s old browser link has been reset. Share the one-use recovery link with them directly.`,
        );
      }
      await loadDashboard();
    } catch (e) {
      setError(message(e));
      await loadDashboard().catch(() => {});
    } finally {
      setWorking(false);
    }
  }
  async function saveNames(event: FormEvent) {
    event.preventDefault();
    if (!dashboard || busyRef.current) return;
    setWorking(true);
    setError("");
    try {
      await api("/admin/names", {
        csrf,
        body: {
          event_id: dashboard.event_id,
          original_names: savedNames,
          names,
        },
      });
      setEditing(false);
      setNotice(
        "All eight names are saved. The name selector, wheel and presents will update automatically.",
      );
      await loadDashboard();
    } catch (e) {
      setError(message(e));
    } finally {
      setWorking(false);
    }
  }
  const completed =
    dashboard?.participants.filter((p) => p.completed).length ?? 0;
  const claimed = dashboard?.participants.filter((p) => p.claimed).length ?? 0;

  return (
    <div className="site-shell admin-shell">
      <Decor />
      <header className="site-header">
        <Brand admin />
        <a href="/" className="admin-link">
          <ArrowLeft size={14} />
          <span>Back to the magic</span>
        </a>
      </header>
      <main className={auth ? "admin-main" : "login-main"}>
        {!auth ? (
          <div className="login-card">
            <div className="login-emblem">
              <LockKeyhole size={26} />
            </div>
            <div className="small-label">A LITTLE BEHIND-THE-SCENES MAGIC</div>
            <h1>
              Amanda’s <em>corner.</em>
            </h1>
            <p>
              A quiet little space to bring everyone’s Christmas surprise
              together.
            </p>
            <form onSubmit={(e) => void login(e)}>
              {error && (
                <div className="alert" role="alert">
                  {error}
                </div>
              )}
              <label className="field-label" htmlFor="password">
                Administrator password
              </label>
              <div className="password-wrap">
                <KeyRound size={17} />
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  maxLength={1024}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
              <button
                className="button primary"
                disabled={busy || !csrf || !password}
              >
                {busy ? "Signing in…" : "Open Amanda’s corner"}
                <ArrowRight size={17} />
              </button>
            </form>
            <div className="privacy-note">
              <ShieldCheck size={14} />
              <span>
                Admin access uses a separate password.
                <br />
                Choosing Amanda on the wheel doesn’t sign you in.
              </span>
            </div>
          </div>
        ) : (
          <>
            <div className="admin-heading">
              <div>
                <div className="small-label">
                  <Sparkles size={13} /> THE CHRISTMAS CONTROL ROOM
                </div>
                <h1>
                  Hello, <em>Amanda.</em>
                </h1>
                <p>
                  Eight little surprises. A little organisation. A lot of joy.
                </p>
              </div>
              <button
                className="button small secondary"
                onClick={() => void logout()}
                disabled={busy}
              >
                <LogOut size={15} /> Sign out
              </button>
            </div>
            {error && !action && (
              <div className="alert" role="alert">
                {error}
              </div>
            )}
            {notice && (
              <div className="notice" role="status">
                <Check size={16} />
                <span>{notice}</span>
                <button
                  onClick={() => setNotice("")}
                  aria-label="Dismiss notification"
                >
                  <X size={16} />
                </button>
              </div>
            )}
            {!dashboard ? (
              <div className="admin-card loading-card">
                <p>Gathering the Christmas list…</p>
                <button
                  className="text-button"
                  onClick={() =>
                    void loadDashboard().catch((e) => setError(message(e)))
                  }
                >
                  Refresh dashboard
                </button>
              </div>
            ) : (
              <>
                <section
                  className="admin-card names-setup-card"
                  aria-labelledby="names-setup-title"
                >
                  <div className="section-heading">
                    <div>
                      <h2 id="names-setup-title">
                        Names for the Christmas wheel
                      </h2>
                      <p>
                        Amanda, type the eight names below and press Save names.
                        Everyone’s screen will update automatically.
                      </p>
                    </div>
                    <span className="names-admin-badge">
                      <LockKeyhole size={15} /> Admin only
                    </span>
                  </div>
                  <form
                    className="names-setup-form"
                    onSubmit={(event) => void saveNames(event)}
                  >
                    <div className="names-editor-grid">
                      {dashboard.participants.map((person, index) => (
                        <label className="names-editor-field" key={person.id}>
                          <span>Name {index + 1}</span>
                          <input
                            value={names[index] ?? person.name}
                            maxLength={40}
                            required
                            disabled={busy}
                            autoComplete="off"
                            onFocus={(event) => event.currentTarget.select()}
                            onChange={(event) => {
                              setNames((current) =>
                                current.map((name, slot) =>
                                  slot === index ? event.target.value : name,
                                ),
                              );
                              setEditing(true);
                            }}
                          />
                        </label>
                      ))}
                    </div>
                    <div className="names-setup-actions">
                      <p>
                        <ShieldCheck size={16} /> Only names change. Saved draws
                        and browser links stay with the same people.
                      </p>
                      {editing && (
                        <button
                          type="button"
                          className="button secondary"
                          disabled={busy}
                          onClick={() => setEditing(false)}
                        >
                          Use saved names
                        </button>
                      )}
                      <button
                        className="button primary"
                        disabled={busy || !editing}
                      >
                        {busy ? "Saving…" : "Save names"}
                        <Check size={18} />
                      </button>
                    </div>
                  </form>
                </section>
                <div className="stat-grid">
                  <div className="stat-card">
                    <Users size={22} />
                    <span>
                      <strong>
                        {claimed}
                        <small> / 8</small>
                      </strong>
                      <span>Names safely linked</span>
                    </span>
                  </div>
                  <div className="stat-card">
                    <Gift size={22} />
                    <span>
                      <strong>
                        {completed}
                        <small> / 8</small>
                      </strong>
                      <span>Surprises revealed</span>
                    </span>
                  </div>
                  <div className="stat-card">
                    <ShieldCheck size={22} />
                    <span>
                      <strong className="status-stat">
                        {dashboard.started
                          ? completed === 8
                            ? "All wrapped up"
                            : "Magic in progress"
                          : "Ready for the magic"}
                      </strong>
                      <span>
                        {dashboard.started
                          ? "Amanda can still update the names"
                          : "Fill in the eight names above"}
                      </span>
                    </span>
                  </div>
                </div>
                <section className="admin-card">
                  <div className="section-heading">
                    <div>
                      <h2>The Christmas list</h2>
                      <p>
                        Saved recipients stay hidden until you deliberately
                        reveal them.
                      </p>
                    </div>
                    <div className="button-row">
                      <button
                        className="button small secondary"
                        onClick={() =>
                          assignments
                            ? setAssignments(null)
                            : openAction({ kind: "reveal" })
                        }
                        disabled={busy}
                      >
                        {assignments ? <EyeOff size={14} /> : <Eye size={14} />}
                        {assignments ? "Hide recipients" : "Reveal recipients"}
                      </button>
                    </div>
                  </div>
                  <div>
                    <div className="participant-table">
                      <div className="table-header">
                        <span>PARTICIPANT</span>
                        <span>BROWSER LINK</span>
                        <span>CHRISTMAS DRAW</span>
                        <span>HELP & RECOVERY</span>
                      </div>
                      {dashboard.participants.map((person, i) => (
                        <div className="participant-row" key={person.id}>
                          <div className="person-cell">
                            <span className="avatar">
                              {person.name.slice(0, 1)}
                            </span>
                            <span>
                              <strong>{person.name}</strong>
                              {person.name === "Amanda" && (
                                <small>Participant · separate from admin</small>
                              )}
                            </span>
                          </div>
                          <div className="status-cell">
                            <span
                              className={`badge ${person.claimed ? "green" : "neutral"}`}
                            >
                              <i />
                              {person.claimed ? "Linked" : "Not selected"}
                            </span>
                            <small>{date(person.claimed_at)}</small>
                          </div>
                          <div className="status-cell">
                            <span
                              className={`badge ${person.completed ? "gold" : "neutral"}`}
                            >
                              <i />
                              {person.completed
                                ? "Draw saved"
                                : "Waiting to spin"}
                            </span>
                            <small>
                              {assignments && person.completed ? (
                                <strong className="revealed-recipient">
                                  For {assignments[person.id]}
                                </strong>
                              ) : (
                                date(person.drawn_at)
                              )}
                            </small>
                          </div>
                          <div className="row-actions">
                            <button
                              type="button"
                              className="icon-action"
                              disabled={busy || !person.completed}
                              onClick={() => void replay(person)}
                              title="Replay saved animation"
                              aria-label={`Replay animation for ${person.name}`}
                            >
                              <RotateCcw size={15} />
                              <span>Replay</span>
                            </button>
                            <button
                              type="button"
                              className="icon-action"
                              disabled={busy}
                              onClick={() =>
                                openAction({ kind: "recovery", person })
                              }
                              title="Reset browser link"
                              aria-label={`Recover browser for ${person.name}`}
                            >
                              <Link size={15} />
                              <span>Recover</span>
                            </button>
                            <button
                              type="button"
                              className="icon-action danger-text"
                              disabled={busy || !person.completed}
                              onClick={() =>
                                openAction({ kind: "new-draw", person })
                              }
                              title="Invalidate recipient and grant a new draw"
                              aria-label={`Grant new draw for ${person.name}`}
                            >
                              <Gift size={15} />
                              <span>New draw</span>
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </section>
                <div className="admin-bottom-grid">
                  <section className="admin-card audit-card">
                    <div className="section-heading">
                      <div>
                        <h2>A little paper trail</h2>
                        <p>Administrative changes, recorded with care.</p>
                      </div>
                      <span className="audit-count">
                        LATEST {dashboard.audit.length}
                      </span>
                    </div>
                    <div
                      className="audit-list"
                      tabIndex={0}
                      role="region"
                      aria-label="Administrative audit history"
                    >
                      {dashboard.audit.length ? (
                        dashboard.audit.map((entry) => (
                          <div key={entry.id}>
                            <span className="audit-dot" />
                            <div>
                              <strong>
                                {auditLabels[entry.action] ?? entry.action}
                                {entry.participant_name
                                  ? ` · ${entry.participant_name}`
                                  : ""}
                              </strong>
                              <small>
                                {entry.actor} · {date(entry.created_at)}
                              </small>
                            </div>
                          </div>
                        ))
                      ) : (
                        <p className="muted">
                          Your administrative changes will appear here.
                        </p>
                      )}
                    </div>
                  </section>
                  <section className="admin-card recovery-guide">
                    <ShieldCheck size={24} />
                    <h2>Keep the surprise.</h2>
                    <p>
                      If a spin is interrupted, use <strong>Replay</strong>. It
                      reveals the same saved recipient and keeps every
                      assignment intact.
                    </p>
                    <p>
                      Changed phones or picked the wrong name?{" "}
                      <strong>Recover</strong> creates a private, one-use link
                      and retains the saved result.
                    </p>
                    <p>
                      <strong>New draw</strong> releases only that person’s
                      recipient. They may draw the same name again, especially
                      if it’s the only valid option.
                    </p>
                    <div className="danger-zone">
                      <h3>A fresh start for everyone</h3>
                      <p>
                        Clear every claim and draw and invalidate old browser
                        links. The audit history is retained.
                      </p>
                      <button
                        className="button small danger-button"
                        disabled={busy}
                        onClick={() => openAction({ kind: "reset" })}
                      >
                        <RotateCcw size={14} /> Reset entire event
                      </button>
                    </div>
                  </section>
                </div>
              </>
            )}
          </>
        )}
      </main>
      <footer className="site-footer">
        <span>A little care behind every Christmas surprise.</span>
        <span className="footer-signoff">
          With love, Amanda <Gift size={12} />
        </span>
      </footer>
      {action && (
        <div className="modal-backdrop" onClick={closeDialog}>
          <div
            className="modal admin-modal"
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby="action-title"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="modal-close"
              onClick={closeDialog}
              disabled={busy}
              aria-label="Close dialog"
            >
              <X size={20} />
            </button>
            <ShieldCheck className="modal-gift" size={28} />
            <h2 id="action-title">
              {action.kind === "reset"
                ? "Start a fresh round?"
                : action.kind === "reveal"
                  ? "Peek at the surprises?"
                  : action.kind === "new-draw"
                    ? `A new draw for ${action.person?.name}?`
                    : `Reconnect ${action.person?.name}.`}
            </h2>
            {error && (
              <div className="alert" role="alert">
                {error}
              </div>
            )}
            {recoveryUrl ? (
              <>
                <p>
                  The old browser link is now invalid. Share this link directly
                  with {action.person?.name}. It expires in 24 hours and works
                  once. Their saved recipient is retained.
                </p>
                <label className="field-label" htmlFor="recovery-link">
                  Private one-use recovery link
                </label>
                <textarea
                  id="recovery-link"
                  className="recovery-url"
                  readOnly
                  value={recoveryUrl}
                  onFocus={(e) => e.target.select()}
                />
                <button
                  className="button primary"
                  onClick={() => {
                    void navigator.clipboard
                      .writeText(recoveryUrl)
                      .then(() => setCopied(true))
                      .catch(() => setError("Select and copy the link above."));
                  }}
                >
                  {copied ? <Check size={17} /> : <Copy size={17} />}
                  {copied ? "Link copied" : "Copy recovery link"}
                </button>
                <button
                  className="text-button modal-cancel"
                  onClick={closeDialog}
                >
                  Done
                </button>
              </>
            ) : (
              <form onSubmit={(e) => void executeAction(e)}>
                <p>
                  {action.kind === "reset"
                    ? "Everyone will choose their name and spin again. All current draws will be cleared. The eight names will stay the same."
                    : action.kind === "reveal"
                      ? "This will show each giver’s saved recipient on your dashboard. Keep your screen private. This deliberate reveal will be recorded in the audit log."
                      : action.kind === "new-draw"
                        ? `This removes ${action.person?.name}’s old result so they can spin again. Everyone else keeps their result. They may draw the same name again.`
                        : `This immediately invalidates ${action.person?.name}’s current browser link and creates a new one-use recovery link. The name is reserved for them and any saved recipient is retained. Share the link directly with them.`}
                </p>
                <button
                  className={`button ${["reset", "new-draw"].includes(action.kind) ? "danger-button" : "primary"}`}
                  disabled={busy}
                >
                  {busy
                    ? "Saving…"
                    : action.kind === "reset"
                      ? "Yes, reset everyone"
                      : action.kind === "new-draw"
                        ? "Yes, give a new draw"
                        : action.kind === "reveal"
                          ? "Reveal the saved recipients"
                          : "Reset browser & create recovery link"}
                  <ArrowRight size={16} />
                </button>
                <button
                  type="button"
                  className="text-button modal-cancel"
                  disabled={busy}
                  onClick={closeDialog}
                >
                  Cancel
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
