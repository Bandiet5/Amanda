export interface Person {
  id: number;
  name: string;
}
export interface Draw {
  recipient: Person;
  segments: Person[];
  drawn_at: string;
}
export interface State {
  event_id: number;
  revision: number;
  csrf: string;
  binding_lost: boolean;
  participants: (Person & { claimed: boolean })[];
  participant:
    (Person & { draw_version: number; replay_version: number }) | null;
  draw: Draw | null;
  segments: Person[];
  completed_count: number;
  total: number;
}
export interface AdminPerson extends Person {
  draw_version: number;
  claimed: boolean;
  completed: boolean;
  claimed_at: string | null;
  drawn_at: string | null;
}
export interface Dashboard {
  event_id: number;
  revision: number;
  started: boolean;
  participants: AdminPerson[];
  audit: {
    id: number;
    actor: string;
    action: string;
    participant_name: string | null;
    created_at: string;
  }[];
}
