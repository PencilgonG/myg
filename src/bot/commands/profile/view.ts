import type { ChatInputCommandInteraction } from 'discord.js';
import { prisma } from '../../../infra/prisma.ts';
import { baseEmbed } from '../../../components/embeds.ts';

export async function handleProfileView(interaction: ChatInputCommandInteraction) {
  const user = interaction.options.getUser('user') ?? interaction.user;
  const p = await prisma.userProfile.findUnique({ where: { discordUserId: user.id } });

  const links: string[] = [];
  if (p?.opggUrl) links.push(`[OP.GG](${p.opggUrl})`);
  if (p?.dpmUrl)  links.push(`[DPM](${p.dpmUrl})`);

  const embed = baseEmbed('Profil joueur')
    .addFields(
      { name: 'Joueur', value: `<@${user.id}>`, inline: true },
      { name: 'Summoner', value: p?.summonerName ?? '—', inline: true },
      { name: 'Rôles', value: p?.preferredRoles?.join(', ') || '—', inline: true },
      { name: 'Liens', value: links.length ? links.join(' | ') : '—', inline: false }
    );

  await interaction.reply({ embeds: [embed], ephemeral: true });
}
