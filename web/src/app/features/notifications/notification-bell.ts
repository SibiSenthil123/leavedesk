import { DatePipe } from '@angular/common';
import { Component, inject } from '@angular/core';
import { MatBadgeModule } from '@angular/material/badge';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';

import { NotificationStore } from './notification.store';

@Component({
  selector: 'app-notification-bell',
  imports: [DatePipe, MatBadgeModule, MatButtonModule, MatIconModule, MatMenuModule],
  template: `
    <button
      mat-icon-button
      [matMenuTriggerFor]="panel"
      (menuOpened)="store.markAllRead()"
      [attr.aria-label]="'Notifications, ' + store.unreadCount() + ' unread'"
    >
      <mat-icon
        [matBadge]="store.unreadCount()"
        [matBadgeHidden]="store.unreadCount() === 0"
        matBadgeColor="warn"
        aria-hidden="false"
        >notifications</mat-icon
      >
    </button>
    <!-- aria-live: screen readers announce the new count when it changes -->
    <span class="visually-hidden" aria-live="polite"
      >{{ store.unreadCount() }} unread notifications</span
    >

    <mat-menu #panel="matMenu" class="panel">
      @if (store.error()) {
        <p class="note">{{ store.error() }}</p>
      }
      @for (n of store.items(); track n.id) {
        <div mat-menu-item class="item" [class.unread]="!n.read">
          <span>{{ n.message }}</span>
          <small>{{ n.created_at | date: 'd MMM, HH:mm' }}</small>
        </div>
      } @empty {
        <p class="note">No notifications yet.</p>
      }
    </mat-menu>
  `,
  styles: `
    .item {
      display: flex;
      flex-direction: column;
      align-items: flex-start;
      height: auto;
      line-height: 1.3;
      padding: 8px 16px;
      white-space: normal;
    }
    .item.unread {
      font-weight: 600;
    }
    .note {
      padding: 8px 16px;
      margin: 0;
    }
  `,
})
export class NotificationBell {
  readonly store = inject(NotificationStore);
}
