import { z } from 'zod';

const EnvSchema = z.object({
  DISCORD_TOKEN: z.string().min(1),
  DISCORD_CLIENT_ID: z.string().min(1),
  DATABASE_URL: z.string().min(1),
  LOGO_URL: z.string().url().optional(),
  BANNER_URL: z.string().url().optional(),
  DEFAULT_CATEGORY_PREFIX: z.string().default('Inhouse -'),
  DEV_GUILD_ID: z.string().optional()
});

export type Env = z.infer<typeof EnvSchema>;

export function validateEnv(): Env {
  const parsed = EnvSchema.safeParse(process.env);
  if (!parsed.success) {
    console.error(parsed.error.format());
    throw new Error('Invalid .env');
  }
  return parsed.data;
}
