// path: src/bot/commands/lobby/index.ts
import type { ChatInputCommandInteraction } from 'discord.js';
import { ButtonStyle } from 'discord.js';
import { prisma } from '../../../infra/prisma.ts';
import { baseEmbed } from '../../../components/embeds.ts';
import { row, btn } from '../../../components/buttons.ts';
import { IDS } from '../../interactions/ids.ts';

export async function handleLobbySlash(interaction: ChatInputCommandInteraction) {
  const lobby = await prisma.lobby.create({
    data: {
      guildId: interaction.guildId!,
      channelId: interaction.channelId,
      name: 'Nouveau lobby',
      slots: 2,
      mode: 'SR_5v5',
      createdBy: interaction.user.id
    }
  });

  const embed = baseEmbed('Créer un lobby', 'Configure les paramètres puis valide.')
    .addFields(
      { name: 'Nom', value: lobby.name, inline: true },
      { name: 'Slots (équipes)', value: String(lobby.slots), inline: true },
      { name: 'Mode', value: '5v5', inline: true }
    );

  const components = [
    row(
      btn(IDS.lobby.openConfig(lobby.id), 'Configurer'),
      btn(IDS.lobby.testFill(lobby.id), 'Test'),
      btn(IDS.lobby.validate(lobby.id), 'Valider', ButtonStyle.Success)
    )
  ];

  await interaction.reply({ embeds: [embed], components });
  const msg = await interaction.fetchReply();
  await prisma.lobby.update({ where: { id: lobby.id }, data: { messageId: msg.id } });
}
