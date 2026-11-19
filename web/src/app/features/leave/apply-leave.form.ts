import { HttpErrorResponse } from '@angular/common/http';
import { Component, inject, output, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';

import { errorMessage } from '../../core/errors';
import { LeaveType } from '../../core/models';
import { dateRangeValidator } from '../../shared/date-range.validator';
import { LeaveStore } from './leave.store';

@Component({
  selector: 'app-apply-leave-form',
  imports: [
    ReactiveFormsModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatCheckboxModule,
    MatButtonModule,
  ],
  template: `
    <form [formGroup]="form" (ngSubmit)="submit()" aria-label="Apply for leave">
      <mat-form-field appearance="outline">
        <mat-label>Leave type</mat-label>
        <mat-select formControlName="leave_type">
          <mat-option value="ANNUAL">Annual</mat-option>
          <mat-option value="SICK">Sick</mat-option>
          <mat-option value="CASUAL">Casual</mat-option>
        </mat-select>
      </mat-form-field>

      <mat-form-field appearance="outline">
        <mat-label>Start date</mat-label>
        <input matInput type="date" formControlName="start" />
      </mat-form-field>

      <mat-form-field appearance="outline">
        <mat-label>End date</mat-label>
        <input matInput type="date" formControlName="end" />
      </mat-form-field>

      <mat-form-field appearance="outline" class="reason">
        <mat-label>Reason</mat-label>
        <input matInput formControlName="reason" maxlength="500" />
        @if (form.controls.reason.hasError('minlength')) {
          <mat-error>At least 5 characters</mat-error>
        }
      </mat-form-field>

      <mat-checkbox formControlName="half_day">Half day</mat-checkbox>

      <button mat-flat-button type="submit" [disabled]="form.invalid || busy()">Apply</button>

      <!-- Messages that are not about one field: shown under the whole form. -->
      @if (form.hasError('dateRange')) {
        <p class="error" role="alert">{{ form.getError('dateRange') }}</p>
      }
      @if (serverError()) {
        <p class="error" role="alert">{{ serverError() }}</p>
      }
    </form>
  `,
  styles: `
    form {
      display: flex;
      flex-wrap: wrap;
      gap: 8px 12px;
      align-items: baseline;
    }
    .reason {
      flex: 1 1 220px;
    }
    .error {
      color: var(--mat-sys-error);
      width: 100%;
      margin: 0;
    }
  `,
})
export class ApplyLeaveForm {
  private readonly store = inject(LeaveStore);

  /** Tells the parent screen "a request was created" (an output event). */
  readonly applied = output<void>();

  readonly form = inject(FormBuilder).nonNullable.group(
    {
      leave_type: ['ANNUAL' as LeaveType, Validators.required],
      start: ['', Validators.required],
      end: ['', Validators.required],
      reason: ['', [Validators.required, Validators.minLength(5)]],
      half_day: [false],
    },
    { validators: dateRangeValidator },
  );
  readonly busy = signal(false);
  readonly serverError = signal<string | null>(null);

  async submit(): Promise<void> {
    if (this.form.invalid) return;
    this.busy.set(true);
    this.serverError.set(null);
    try {
      await this.store.apply(this.form.getRawValue());
      this.form.reset();
      this.applied.emit();
    } catch (err) {
      // 409 = overlaps an existing request; 422 = not enough days or a policy rule.
      const prefix = err instanceof HttpErrorResponse && err.status === 409 ? 'Overlap: ' : '';
      this.serverError.set(prefix + errorMessage(err));
    } finally {
      this.busy.set(false);
    }
  }
}
