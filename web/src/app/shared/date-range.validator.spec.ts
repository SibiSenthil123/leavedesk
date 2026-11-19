import { FormControl, FormGroup } from '@angular/forms';

import { dateRangeValidator } from './date-range.validator';

function range(start: string, end: string): FormGroup {
  return new FormGroup(
    { start: new FormControl(start), end: new FormControl(end) },
    { validators: dateRangeValidator },
  );
}

describe('dateRangeValidator', () => {
  it('accepts an end date on or after the start date', () => {
    expect(range('2026-12-07', '2026-12-09').valid).toBe(true);
    expect(range('2026-12-07', '2026-12-07').valid).toBe(true);
  });

  it('refuses an end date before the start date', () => {
    const form = range('2026-12-09', '2026-12-07');
    expect(form.hasError('dateRange')).toBe(true);
  });
});
