import { z } from 'zod';

/** Mirrors Django's password validators so users see problems before submitting. */
export const passwordSchema = z
  .string()
  .min(8, 'At least 8 characters')
  .refine((v) => !/^\d+$/.test(v), 'Cannot be only numbers');

export const phoneSchema = z
  .string()
  .trim()
  .refine((v) => v === '' || /^[6-9]\d{9}$/.test(v), 'Enter a valid 10-digit mobile number');

export const newPasswordPair = z
  .object({ new_password: passwordSchema, confirm_password: z.string() })
  .refine((d) => d.new_password === d.confirm_password, {
    message: 'Passwords do not match',
    path: ['confirm_password'],
  });
