// ===== [BOT] src/bot/lobby/matches.ts (remplacer ENTIER) =====
import type { Guild, TextChannel, ButtonInteraction } from 'discord.js';
import { ActionRowBuilder, ButtonBuilder, ButtonStyle, MessageFlags } from 'discord.js';
import { baseEmbed } from '../../components/embeds.ts';
import { prisma } from '../../infra/prisma.ts';
import { requestDraft, waitDraft } from '../../services/draft/client.ts';

const BTN_VALIDATE = (matchId: string) =>
  new ActionRowBuilder<ButtonBuilder>().addComponents(
    new ButtonBuilder().setCustomId(`match:validate:${matchId}`).setLabel('Valider').setStyle(ButtonStyle.Success)
  );
const BTN_REMAKE = (matchId: string) =>
  new ActionRowBuilder<ButtonBuilder>().addComponents(
    new ButtonBuilder().setCustomId(`draft:remake:${matchId}`).setLabel('Régénérer la draft').setStyle(ButtonStyle.Primary)
  );

export async function sendRoundMatches(guild: Guild, lobbyId: string, round: number, mainChannelId: string) {
  const matches = await prisma.match.findMany({
    where: { lobbyId, round },
    include: { blueTeam: true, redTeam: true },
    orderBy: { indexInRound: 'asc' }
  });
  if (!matches.length) return;

  const main = guild.channels.cache.get(mainChannelId) as TextChannel | undefined;

  for (const m of matches) {
    if (!m.draftBlueUrl || !m.draftRedUrl || !m.specUrl) {
      try {
        const jobId = await requestDraft(m.blueTeam.name, m.redTeam.name);
        const links = await waitDraft(jobId, 45000);
        await prisma.match.update({
          where: { id: m.id },
          data: { draftBlueUrl: links.blue, draftRedUrl: links.red, specUrl: links.spec }
        });
        m.draftBlueUrl = links.blue; m.draftRedUrl = links.red; m.specUrl = links.spec;
      } catch {
        if (main) {
          const err = baseEmbed(`Draft en attente • R${round + 1} • ${m.blueTeam.name} vs ${m.redTeam.name}`,
            `La création prend plus de temps que prévu. Cliquez **Régénérer la draft** pour relancer.`)
          await main.send({ embeds: [err], components: [BTN_REMAKE(m.id)] });
        }
        continue;
      }
    }

    if (m.blueTeam.textChannelId) {
      const ch = guild.channels.cache.get(m.blueTeam.textChannelId) as TextChannel | undefined;
      if (ch) {
        const embedBlue = baseEmbed(`Match R${round + 1} • ${m.blueTeam.name} vs ${m.redTeam.name}`)
          .setDescription(`Capitaines: cliquez **Valider** une fois terminé.\n\n**Blue**: <@&${m.blueTeam.roleId}>  •  **Red**: <@&${m.redTeam.roleId}>`)
          .addFields({ name: 'Lien Blue', value: m.draftBlueUrl! }, { name: 'Lien Spec', value: m.specUrl! });
        await ch.send({ embeds: [embedBlue], components: [BTN_VALIDATE(m.id)] });
      }
    }
    if (m.redTeam.textChannelId) {
      const ch = guild.channels.cache.get(m.redTeam.textChannelId) as TextChannel | undefined;
      if (ch) {
        const embedRed = baseEmbed(`Match R${round + 1} • ${m.blueTeam.name} vs ${m.redTeam.name}`)
          .setDescription(`Capitaines: cliquez **Valider** une fois terminé.\n\n**Blue**: <@&${m.blueTeam.roleId}>  •  **Red**: <@&${m.redTeam.roleId}>`)
          .addFields({ name: 'Lien Red', value: m.draftRedUrl! }, { name: 'Lien Spec', value: m.specUrl! });
        await ch.send({ embeds: [embedRed], components: [BTN_VALIDATE(m.id)] });
      }
    }

    if (main) {
      const spec = baseEmbed(`Spectateur • R${round + 1} • ${m.blueTeam.name} vs ${m.redTeam.name}`, `[Lien spectateur](${m.specUrl!})`);
      await main.send({ embeds: [spec] });
    }
  }
}

export async function onDraftRemakeButton(interaction: ButtonInteraction, matchId: string) {
  try { await interaction.deferReply({ flags: MessageFlags.Ephemeral }); } catch {}
  const m = await prisma.match.findUnique({
    where: { id: matchId },
    include: { blueTeam: true, redTeam: true, lobby: true }
  });
  if (!m) return interaction.editReply({ content: 'Match introuvable.' });

  try {
    const jobId = await requestDraft(m.blueTeam.name, m.redTeam.name);
    const links = await waitDraft(jobId, 45000);
    await prisma.match.update({
      where: { id: m.id },
      data: { draftBlueUrl: links.blue, draftRedUrl: links.red, specUrl: links.spec }
    });

    const guild = interaction.guild!;
    const main = guild.channels.cache.get(m.lobby.channelId) as TextChannel | undefined;

    if (m.blueTeam.textChannelId) {
      const ch = guild.channels.cache.get(m.blueTeam.textChannelId) as TextChannel | undefined;
      if (ch) await ch.send({
        embeds: [baseEmbed(`Match R${m.round + 1} • ${m.blueTeam.name} vs ${m.redTeam.name}`)
          .addFields({ name: 'Lien Blue', value: links.blue }, { name: 'Lien Spec', value: links.spec })
          .setDescription(`Capitaines: cliquez **Valider** une fois terminé.\n\n**Blue**: <@&${m.blueTeam.roleId}>  •  **Red**: <@&${m.redTeam.roleId}>`)],
        components: [BTN_VALIDATE(m.id)]
      });
    }
    if (m.redTeam.textChannelId) {
      const ch = guild.channels.cache.get(m.redTeam.textChannelId) as TextChannel | undefined;
      if (ch) await ch.send({
        embeds: [baseEmbed(`Match R${m.round + 1} • ${m.blueTeam.name} vs ${m.redTeam.name}`)
          .addFields({ name: 'Lien Red', value: links.red }, { name: 'Lien Spec', value: links.spec })
          .setDescription(`Capitaines: cliquez **Valider** une fois terminé.\n\n**Blue**: <@&${m.blueTeam.roleId}>  •  **Red**: <@&${m.redTeam.roleId}>`)],
        components: [BTN_VALIDATE(m.id)]
      });
    }
    if (main) {
      await main.send({ embeds: [baseEmbed(`Spectateur • R${m.round + 1} • ${m.blueTeam.name} vs ${m.redTeam.name}`, `[Lien spectateur](${links.spec})`)] });
    }
    return interaction.editReply({ content: '✅ Draft régénérée et envoyée.' });
  } catch (e: any) {
    return interaction.editReply({ content: `❌ Échec: ${e.message || 'unknown error'}` });
  }
}
