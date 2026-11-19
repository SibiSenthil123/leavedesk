import { DatePipe } from '@angular/common';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Component, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatDialog } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatTableModule } from '@angular/material/table';
import { firstValueFrom } from 'rxjs';

import { AuthService } from '../../core/auth.service';
import { errorMessage } from '../../core/errors';
import { API, LeaveRequest, Page } from '../../core/models';
import { ConfirmDialog, ConfirmData } from './confirm.dialog';

/** Manager's queue: PENDING requests from people who report to me. Lazy-loaded. */
@Component({
  selector: 'app-approvals-page',
  imports: [
    DatePipe,
    FormsModule,
    MatTableModule,
    MatButtonModule,
    MatFormFieldModule,
    MatInputModule,
  ],
  template: `
    <h1>Approvals</h1>
    @if (error()) {
      <p class="error" role="alert">{{ error() }}</p>
    }
    @if (loading()) {
      <p>Loading…</p>
    } @else if (pending().length === 0) {
      <p class="empty">Nothing waiting for you. 🎉</p>
    } @else {
      <div class="table-wrap">
        <table mat-table [dataSource]="pending()">
          <ng-container matColumnDef="dates">
            <th mat-header-cell *matHeaderCellDef>Dates</th>
            <td mat-cell *matCellDef="let r">
              {{ r.start | date: 'd MMM' }} – {{ r.end | date: 'd MMM y' }}
            </td>
          </ng-container>
          <ng-container matColumnDef="type">
            <th mat-header-cell *matHeaderCellDef>Type</th>
            <td mat-cell *matCellDef="let r">{{ r.leave_type }}</td>
          </ng-container>
          <ng-container matColumnDef="reason">
            <th mat-header-cell *matHeaderCellDef>Reason</th>
            <td mat-cell *matCellDef="let r">{{ r.reason }}</td>
          </ng-container>
          <ng-container matColumnDef="actions">
            <th mat-header-cell *matHeaderCellDef><span class="visually-hidden">Actions</span></th>
            <td mat-cell *matCellDef="let r">
              <button mat-flat-button (click)="approve(r)">Approve</button>
              <button mat-button (click)="reject(r)">Reject</button>
            </td>
          </ng-container>
          <tr mat-header-row *matHeaderRowDef="columns"></tr>
          <tr mat-row *matRowDef="let row; columns: columns"></tr>
        </table>
      </div>
      <mat-form-field appearance="outline" class="reason">
        <mat-label>Reason for rejecting (min 5 characters)</mat-label>
        <input matInput [(ngModel)]="rejectReason" />
      </mat-form-field>
    }
  `,
  styles: `
    .table-wrap {
      overflow-x: auto;
    }
    .reason {
      width: 100%;
      max-width: 420px;
      margin-top: 12px;
    }
    .error {
      color: var(--mat-sys-error);
    }
    .empty {
      color: var(--mat-sys-on-surface-variant);
    }
  `,
})
export class ApprovalsPage implements OnInit {
  private readonly http = inject(HttpClient);
  private readonly auth = inject(AuthService);
  private readonly dialog = inject(MatDialog);
  private readonly snack = inject(MatSnackBar);

  readonly pending = signal<LeaveRequest[]>([]);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly columns = ['dates', 'type', 'reason', 'actions'];
  rejectReason = '';

  ngOnInit(): void {
    void this.load();
  }

  async load(): Promise<void> {
    this.loading.set(true);
    try {
      const params = new HttpParams()
        .set('status', 'PENDING')
        .set('sort', 'start')
        .set('limit', 100);
      const page = await firstValueFrom(
        this.http.get<Page<LeaveRequest>>(`${API}/leave-requests`, { params }),
      );
      const myId = this.auth.me()?.id;
      this.pending.set(page.items.filter((r) => r.employee_id !== myId)); // my own requests aren't mine to approve
    } catch (err) {
      this.error.set(errorMessage(err));
    } finally {
      this.loading.set(false);
    }
  }

  async approve(r: LeaveRequest): Promise<void> {
    const data: ConfirmData = {
      title: 'Approve leave?',
      message: `${r.start} to ${r.end}: ${r.reason}`,
      action: 'Approve',
    };
    if (!(await this.confirm(data))) return;
    await this.decide(r, 'approve', {});
  }

  async reject(r: LeaveRequest): Promise<void> {
    if (this.rejectReason.trim().length < 5) {
      this.snack.open('Type a reason of at least 5 characters below the table first', 'OK', {
        duration: 4000,
      });
      return;
    }
    const data: ConfirmData = {
      title: 'Reject leave?',
      message: `Reason: ${this.rejectReason}`,
      action: 'Reject',
    };
    if (!(await this.confirm(data))) return;
    await this.decide(r, 'reject', { reason: this.rejectReason.trim() });
  }

  /**
   * Optimistic update: remove the row from the screen straight away, so the app
   * feels instant. If the server says no, put the row back and show why.
   */
  private async decide(r: LeaveRequest, action: 'approve' | 'reject', body: object): Promise<void> {
    const before = this.pending();
    this.pending.set(before.filter((x) => x.id !== r.id));
    try {
      await firstValueFrom(
        this.http.post<LeaveRequest>(`${API}/leave-requests/${r.id}/${action}`, body),
      );
      this.snack.open(action === 'approve' ? 'Approved' : 'Rejected', undefined, {
        duration: 2500,
      });
    } catch (err) {
      this.pending.set(before); // roll back
      this.snack.open(errorMessage(err), 'OK', { duration: 5000 });
    }
  }

  private confirm(data: ConfirmData): Promise<boolean> {
    const ref = this.dialog.open(ConfirmDialog, { data });
    return firstValueFrom(ref.afterClosed()).then((yes) => yes === true);
  }
}
