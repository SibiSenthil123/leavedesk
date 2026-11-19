import { AbstractControl, ValidationErrors, ValidatorFn } from '@angular/forms';

/**
 * Form-level check: the end date may not be before the start date.
 * The API checks this too, but checking here gives instant feedback.
 * "2026-12-09" < "2026-12-07" compares correctly as text because ISO dates
 * are written biggest unit first (year, month, day).
 */
export const dateRangeValidator: ValidatorFn = (
  group: AbstractControl,
): ValidationErrors | null => {
  const start = group.get('start')?.value as string | null;
  const end = group.get('end')?.value as string | null;
  if (start && end && end < start) {
    return { dateRange: 'End date must be on or after the start date' };
  }
  return null;
};
