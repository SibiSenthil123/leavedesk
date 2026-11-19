// The shapes the LeaveDesk API sends and receives (see API_SPEC.md).
// TypeScript checks every use of them at compile time, so a typo in a field
// name is caught before the app even runs.

export type LeaveType = 'ANNUAL' | 'SICK' | 'CASUAL';
export type LeaveStatus = 'PENDING' | 'APPROVED' | 'REJECTED' | 'CANCELLED';

export interface Me {
  id: string;
  name: string;
  email: string;
  manager_id: string | null;
  is_manager: boolean;
}

export interface Token {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface Balance {
  leave_type: LeaveType;
  entitled: number;
  used: number;
  remaining: number;
}

export interface LeaveRequest {
  id: string;
  employee_id: string;
  leave_type: LeaveType;
  start: string; // "2026-12-07": dates travel as text in JSON
  end: string;
  half_day: boolean;
  reason: string;
  status: LeaveStatus;
  rejection_reason: string | null;
  created_at: string;
}

export interface NewLeaveRequest {
  leave_type: LeaveType;
  start: string;
  end: string;
  half_day: boolean;
  reason: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface AppNotification {
  id: string;
  event: 'submitted' | 'approved' | 'rejected' | 'cancelled';
  request_id: string;
  message: string;
  read: boolean;
  created_at: string;
}

/** Every API error has this shape: { "error": { code, message, ... } } */
export interface ApiError {
  error: { code: string; message: string; request_id?: string };
}

/** All API calls start with /api; the dev server forwards them to FastAPI. */
export const API = '/api';
