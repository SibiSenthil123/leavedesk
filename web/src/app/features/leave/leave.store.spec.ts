import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { AuthService } from '../../core/auth.service';
import { LeaveStore } from './leave.store';

describe('LeaveStore', () => {
  let store: LeaveStore;
  let backend: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
    TestBed.inject(AuthService).me.set({
      id: 'priya-id',
      name: 'Priya Nair',
      email: 'priya@leavedesk.dev',
      manager_id: 'arjun-id',
      is_manager: false,
    });
    store = TestBed.inject(LeaveStore);
    backend = TestBed.inject(HttpTestingController);
  });

  it('loads my requests and balances, and totals the days left', async () => {
    const done = store.load();
    expect(store.loading()).toBe(true);

    const list = backend.expectOne((r) => r.url === '/api/leave-requests');
    expect(list.request.params.get('employee_id')).toBe('priya-id');
    list.flush({ items: [{ id: 'r1', status: 'PENDING' }], total: 1, limit: 10, offset: 0 });
    backend.expectOne('/api/employees/priya-id/balance').flush([
      { leave_type: 'ANNUAL', entitled: 18, used: 5, remaining: 13 },
      { leave_type: 'SICK', entitled: 10, used: 0, remaining: 10 },
    ]);
    await done;

    expect(store.requests().length).toBe(1);
    expect(store.totalRemaining()).toBe(23);
    expect(store.loading()).toBe(false);
  });

  it('shows the API error message when loading fails', async () => {
    const done = store.load();
    backend
      .expectOne((r) => r.url === '/api/leave-requests')
      .flush(
        { error: { code: 'INTERNAL_ERROR', message: 'database is down' } },
        { status: 500, statusText: 'Error' },
      );
    backend.expectOne('/api/employees/priya-id/balance').flush([]);
    await done;
    expect(store.error()).toBe('database is down');
  });
});
