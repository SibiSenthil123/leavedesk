import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';

import { ApplyLeaveForm } from './apply-leave.form';

describe('ApplyLeaveForm', () => {
  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [ApplyLeaveForm],
      providers: [provideRouter([]), provideHttpClient(), provideHttpClientTesting()],
    });
  });

  it('shows the server 409 overlap message next to the form', async () => {
    const fixture = TestBed.createComponent(ApplyLeaveForm);
    const form = fixture.componentInstance.form;
    form.setValue({
      leave_type: 'ANNUAL',
      start: '2026-12-07',
      end: '2026-12-09',
      reason: 'Family trip',
      half_day: false,
    });

    const done = fixture.componentInstance.submit();
    TestBed.inject(HttpTestingController)
      .expectOne('/api/leave-requests')
      .flush(
        { error: { code: 'OVERLAPPING_LEAVE', message: 'overlaps existing request r1' } },
        { status: 409, statusText: 'Conflict' },
      );
    await done;
    await fixture.whenStable();

    const alert = (fixture.nativeElement as HTMLElement).querySelector('[role="alert"]');
    expect(alert?.textContent).toContain('Overlap: overlaps existing request r1');
  });

  it('keeps Apply disabled until the form is valid', async () => {
    const fixture = TestBed.createComponent(ApplyLeaveForm);
    await fixture.whenStable();
    const button = (fixture.nativeElement as HTMLElement).querySelector(
      'button[type="submit"]',
    ) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });
});
