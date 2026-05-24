export interface TodoItem {
  id: string;
  agent_name: string;
  session_id: string;
  session_title: string | null;
  description: string;
  status: "pending" | "in_progress" | "completed" | "cancelled";
  created_at: number;
  updated_at: number;
}

export type StatusFilter = "all" | "pending" | "in_progress" | "completed" | "cancelled";
