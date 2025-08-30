import { EmbedBuilder } from 'discord.js';

const color = 0x5865F2;
const logo = process.env.LOGO_URL;
const banner = process.env.BANNER_URL;

export function baseEmbed(title: string, description?: string) {
  const e = new EmbedBuilder().setColor(color).setTitle(title);
  if (description) e.setDescription(description);
  if (logo) e.setThumbnail(logo);
  if (banner) e.setImage(banner);
  return e;
}
