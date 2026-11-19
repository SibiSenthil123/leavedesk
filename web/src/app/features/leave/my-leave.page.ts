import { DatePipe } from '@angular/common';
import { Component, inject, OnInit } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatChipsModule } from '@angular/material/chips';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatSelectModule } from '@angular/material/select';
import { MatTableModule } from '@angular/material/table';

import { LeaveStatus } from '../../core/models';
import { ApplyLeaveForm } from './apply-leave.form';
import { LeaveStore } from './leave.store';

@Component({
  selector: 'app-my-leave-page',
  imports: [
    DatePipe,
    ApplyLeaveForm,
    MatCardModule,
    MatTableModule,
    MatPaginatorModule,
    MatSelectModule,
    MatButtonModule,
    MatChipsModule,
    MatProgressBarModule,
  ],
  template: `
    <h1>My leave</h1>

    <!-- Balance cards: one per leave type -->
    <section class="balances" aria-label="Leave balance">
      @for (b of store.balances(); track b.leave_type) {
        <mat-card appearance="outlined">
          <mat-card-content>
            <div class="type">{{ b.leave_type }}</div>
            <div class="remaining">{{ b.remaining }}</div>
            <div class="of">of {{ b.entitled }} days left</div>
          </mat-card-content>
        </mat-card>
      }
      <mat-card appearance="outlined">
        <mat-card-content>
          <div class="type">TOTAL</div>
          <div class="remaining">{{ store.totalRemaining() }}</div>
          <div class="of">days left</div>
        </mat-card-content>
      </mat-card>
    </section>

    <h2>Apply for leave</h2>
    <app-apply-leave-form />

    <h2>My requests</h2>
    <mat-form-field appearance="outline" class="filter">
      <mat-label>Status</mat-label>
      <mat-select [value]="store.status()" (selectionChange)="filter($event.value)">
        <mat-option value="">All</mat-option>
        <mat-option value="PENDING">Pending</mat-option>
        <mat-option value="APPROVED">Approved</mat-option>
        <mat-option value="REJECTED">Rejected</mat-option>
        <mat-option value="CANCELLED">Cancelled</mat-option>
      </mat-select>
    </mat-form-field>

    @if (store.loading()) {
      <mat-progress-bar mode="indeterminate" aria-label="Loading" />
    }
    @if (store.error()) {
      <p class="error" role="alert">{{ store.error() }}</p>
    }

    @if (!store.loading() && store.requests().length === 0) {
      <p class="empty">No leave requests yet.</p>
    } @else {
      <div class="table-wrap">
        <table mat-table [dataSource]="store.requests()">
          <ng-container matColumnDef="type">
            <th mat-header-cell *matHeaderCellDef>Type</th>
            <td mat-cell *matCellDef="let r">{{ r.leave_type }}</td>
          </ng-container>
          <ng-container matColumnDef="dates">
            <th mat-header-cell *matHeaderCellDef>Dates</th>
            <td mat-cell *matCellDef="let r">
              {{ r.start | date: 'd MMM' }} – {{ r.end | date: 'd MMM y' }}
            </td>
          </ng-container>
          <ng-container matColumnDef="reason">
            <th mat-header-cell *matHeaderCellDef>Reason</th>
            <td mat-cell *matCellDef="let r">{{ r.reason }}</td>
          </ng-container>
          <ng-container matColumnDef="status">
            <th mat-header-cell *matHeaderCellDef>Status</th>
            <td mat-cell *matCellDef="let r">
              <span class="status" [class]="r.status.toLowerCase()">{{ r.status }}</span>
              @if (r.rejection_reason) {
                <div class="why">{{ r.rejection_reason }}</div>
              }
            </td>
          </ng-container>
          <ng-container matColumnDef="actions">
            <th mat-header-cell *matHeaderCellDef><span class="visually-hidden">Actions</span></th>
            <td mat-cell *matCellDef="let r">
              @if (r.status === 'PENDING') {
                <button
                  mat-button
                  (click)="store.cancel(r.id)"
                  [attr.aria-label]="'Cancel leave from ' + r.start"
                >
                  Cancel
                </button>
              }
            </td>
          </ng-container>
          <tr mat-header-row *matHeaderRowDef="columns"></tr>
          <tr mat-row *matRowDef="let row; columns: columns"></tr>
        </table>
      </div>
      <mat-paginator
        [length]="store.total()"
        [pageIndex]="store.pageIndex()"
        [pageSize]="store.pageSize()"
        [pageSizeOptions]="[5, 10, 20]"
        (page)="page($event)"
        aria-label="Choose page"
      />
    }
  `,
  styles: `
    .balances {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 12px;
    }
    .type {
      font-size: 0.8rem;
      color: var(--mat-sys-on-surface-variant);
    }
    .remaining {
      font-size: 2rem;
      font-weight: 600;
    }
    .of {
      font-size: 0.85rem;
    }
    .filter {
      width: 200px;
    }
    .table-wrap {
      overflow-x: auto;
    }
    .status {
      padding: 2px 8px;
      border-radius: 12px;
      font-size: 0.8rem;
      background: var(--mat-sys-surface-variant);
    }
    .status.approved {
      background: #c8e6c9;
      color: #1b5e20;
    }
    .status.rejected {
      background: #ffcdd2;
      color: #b71c1c;
    }
    .status.pending {
      background: #fff3c4;
      color: #6d4c00;
    }
    .why {
      font-size: 0.8rem;
      color: var(--mat-sys-on-surface-variant);
    }
    .error {
      color: var(--mat-sys-error);
    }
    .empty {
      color: var(--mat-sys-on-surface-variant);
    }
  `,
})
export class MyLeavePage implements OnInit {
  readonly store = inject(LeaveStore);
  readonly columns = ['type', 'dates', 'reason', 'status', 'actions'];

  ngOnInit(): void {
    void this.store.load(); // fetch my requests and balances when the page opens
  }

  filter(status: LeaveStatus | ''): void {
    this.store.status.set(status);
    this.store.pageIndex.set(0); // a new filter starts again on page 1
    void this.store.load();
  }

  page(event: PageEvent): void {
    this.store.pageIndex.set(event.pageIndex);
    this.store.pageSize.set(event.pageSize);
    void this.store.load();
  }
}
