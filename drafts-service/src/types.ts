export interface DraftJobData {
  blueName: string;
  redName: string;
  matchName?: string;
}

export interface DraftResult {
  status: "ready";
  provider: "lolprodraft";
  blue: string;
  red: string;
  spec: string;
}

export interface DraftError {
  status: "error";
  message: string;
}
