export type Summary = {
  totals: {
    calls: number;
    booked: number;
    no_agreement: number;
    no_match: number;
    failed_auth: number;
    abandoned: number;
  };
  rates: {
    avg_board: number | null;
    avg_agreed: number | null;
    avg_delta: number | null;
  };
  sentiment: {
    positive: number;
    neutral: number;
    negative: number;
  };
  by_equipment: { equipment_type: string; booked: number; avg_rate: number | null }[];
  timeseries: { date: string; calls: number; booked: number }[];
};

export type CallsList = {
  items: CallItem[];
  total: number;
};

export type CallItem = {
  id: string;
  started_at: string;
  duration_sec: number;
  mc_number?: string | null;
  selected_load_id?: string | null;
  agreed_rate?: number | null;
  negotiation_round?: number | null;
  outcome?: string | null;
  sentiment?: string | null;
};

export type CallDetail = {
  id: string;
  started_at: string;
  duration_sec: number;
  mc_number?: string | null;
  selected_load_id?: string | null;
  offers: { t: string; who: 'carrier' | 'agent'; value: number }[];
  outcome?: string | null;
  sentiment?: string | null;
  transcript: { role: 'assistant' | 'user'; text: string }[];
  tool_calls: { fn: string; ok: boolean; [k: string]: any }[];
};
