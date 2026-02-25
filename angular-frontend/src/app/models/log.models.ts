export interface ErrorEntry {
  line_number: number;
  content: string;
  category: string;
  error_code: string | null;
  matched_pattern: string;
}

export interface ScanResult {
  filename?: string;
  total_lines: number;
  error_count: number;
  errors: ErrorEntry[];
  categories: Record<string, number>;
  error_codes: Record<string, number>;
  pattern_matches: Record<string, number>;
}

export interface QueryResponse {
  answer: string;
}

export interface StatusResponse {
  ready: boolean;
  filename: string | null;
}

export interface PatternsResponse {
  patterns: string[];
  descriptions: Record<string, string>;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  text: string;
  timestamp: Date;
}