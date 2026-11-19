import { Component, inject } from '@angular/core';
import { MatButtonModule } from '@angular/material/button';
import { MAT_DIALOG_DATA, MatDialogModule } from '@angular/material/dialog';

export interface ConfirmData {
  title: string;
  message: string;
  action: string;
}

/** A small "Are you sure?" box. It closes with true (yes) or nothing (no). */
@Component({
  selector: 'app-confirm-dialog',
  imports: [MatDialogModule, MatButtonModule],
  template: `
    <h2 mat-dialog-title>{{ data.title }}</h2>
    <mat-dialog-content>{{ data.message }}</mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button mat-dialog-close>Back</button>
      <button mat-flat-button [mat-dialog-close]="true" cdkFocusInitial>{{ data.action }}</button>
    </mat-dialog-actions>
  `,
})
export class ConfirmDialog {
  readonly data = inject<ConfirmData>(MAT_DIALOG_DATA);
}
