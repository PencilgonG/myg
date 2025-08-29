import type { ChatInputCommandInteraction } from 'discord.js';
import { prisma } from '../../../infra/prisma.ts';
import { baseEmbed } from '../../../components/embeds.ts';

function parseRoles(input?: string | null): string[] | undefined {
  if (!input) return undefined;
  const tokens = input.split(',').map(s => s.trim().toUpperCase()).filter(Boolean);
  const map: Record<string, string> = { TOP:'TOP', JG:'JUNGLE', JUNGLE:'JUNGLE', MID:'MID', ADC:'ADC', BOT:'ADC', SUP:'SUPPORT', SUPPORT:'SUPPORT', FLEX:'FLEX' };
  const out = new Set<string>();
  for (const t of tokens) if (map[t]) out.add(map[t]);
  return [...out];
}

export async function handleProfileSet(interaction: ChatInputCommandInteraction) {
  const summoner = interaction.options.getString('summoner') ?? undefined;
  const roles = parseRoles(interaction.options.getString('roles')) ?? [];
  const opgg = interaction.options.getString('opgg') ?? undefined;
  const dpm = interaction.options.getString('dpm') ?? undefined;

  await prisma.userProfile.upsert({
    where: { discordUserId: interaction.user.id },
    create: { discordUserId: interaction.user.id, summonerName: summoner, preferredRoles: roles as any, opggUrl: opgg, dpmUrl: dpm },
    update: { summonerName: summoner, preferredRoles: roles as any, opggUrl: opgg, dpmUrl: dpm }
  });

  const links: string[] = [];
  if (opgg) links.push(`[OP.GG](${opgg})`);
  if (dpm)  links.push(`[DPM](${dpm})`);

  const embed = baseEmbed('Profil enregistré')
    .addFields(
      { name: 'Joueur', value: `<@${interaction.user.id}>`, inline: true },
      { name: 'Summoner', value: summoner ?? '—', inline: true },
      { name: 'Rôles', value: roles.join(', ') || '—', inline: true },
      { name: 'Liens', value: links.length ? links.join(' | ') : '—', inline: false }
    );

  await interaction.reply({ embeds: [embed], ephemeral: true });
}
