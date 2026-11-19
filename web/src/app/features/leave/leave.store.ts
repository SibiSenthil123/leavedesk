import { HttpClient, HttpParams } from '@angular/common/http';
import { computed, inject, Injectable, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';

import { AuthService } from '../../core/auth.service';
import { errorMessage } from '../../core/errors';
import { API, Balance, LeaveRequest, LeaveStatus, NewLeaveRequest, Page } from '../../core/models';

/**
 * The "store" for the My leave screen: all its data and every action on it,
 * in one place. Screens only READ its signals and CALL its methods, so the
 * rules for loading, errors and refreshing live here once.
 */
@Injectable({ providedIn: 'root' })
export class LeaveStore {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);

  // ---- state (private, writable) ----
  private readonly _requests = signal<LeaveRequest[]>([]);
  private readonly _total = signal(0);
  private readonly _balances = signal<Balance[]>([]);
  private readonly _loading = signal(false);
  private readonly _error = signal<string | null>(null);

  // ---- what screens may read (public, read-only) ----
  readonly requests = this._requests.asReadonly();
  readonly total = this._total.asReadonly();
  readonly balances = this._balances.asReadonly();
  readonly loading = this._loading.asReadonly();
  readonly error = this._error.asReadonly();

  // Filters and paging: changing them and calling load() refreshes the table.
  readonly status = signal<LeaveStatus | ''>('');
  readonly pageIndex = signal(0);
  readonly pageSize = signal(10);

  /** Total days left across all leave types: worked out, never stored. */
  readonly totalRemaining = computed(() =>
    this._balances().reduce((sum, b) => sum + b.remaining, 0),
  );

  async load(): Promise<void> {
    const me = this.auth.me() ?? (await this.auth.loadMe());
    if (!me) return;
    this._loading.set(true);
    this._error.set(null);
    try {
      let params = new HttpParams()
        .set('employee_id', me.id) // only MY requests on this screen
        .set('limit', this.pageSize())
        .set('offset', this.pageIndex() * this.pageSize());
      if (this.status()) params = params.set('status', this.status());

      // Both calls run at the same time; we wait for both.
      const [page, balances] = await Promise.all([
        firstValueFrom(this.http.get<Page<LeaveRequest>>(`${API}/leave-requests`, { params })),
        firstValueFrom(this.http.get<Balance[]>(`${API}/employees/${me.id}/balance`)),
      ]);
      this._requests.set(page.items);
      this._total.set(page.total);
      this._balances.set(balances);
    } catch (err) {
      this._error.set(errorMessage(err));
    } finally {
      this._loading.set(false);
    }
  }

  /** Throws on failure so the form can show the message next to the fields. */
  async apply(body: NewLeaveRequest): Promise<LeaveRequest> {
    const created = await firstValueFrom(
      this.http.post<LeaveRequest>(`${API}/leave-requests`, body),
    );
    await this.load();
    return created;
  }

  async cancel(id: string): Promise<void> {
    try {
      await firstValueFrom(this.http.delete<LeaveRequest>(`${API}/leave-requests/${id}`));
      await this.load();
    } catch (err) {
      this._error.set(errorMessage(err));
    }
  }
}
