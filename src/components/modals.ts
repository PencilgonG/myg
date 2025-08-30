import { ModalBuilder, TextInputBuilder, TextInputStyle, ActionRowBuilder } from 'discord.js';

export function modalLobbyConfig(customId: string) {
  const modal = new ModalBuilder().setCustomId(customId).setTitle('Configurer le lobby');

  const name = new TextInputBuilder()
    .setCustomId('name')
    .setLabel('Nom du lobby')
    .setStyle(TextInputStyle.Short)
    .setRequired(true);

  const slots = new TextInputBuilder()
    .setCustomId('slots')
    .setLabel('Nombre d’équipes')
    .setStyle(TextInputStyle.Short)
    .setRequired(true)
    .setPlaceholder('2-8');

  const mode = new TextInputBuilder()
    .setCustomId('mode')
    .setLabel('Mode (SR_5v5, SR_4v4, SR_3v3, SR_2v2)')
    .setStyle(TextInputStyle.Short)
    .setRequired(true)
    .setPlaceholder('SR_5v5');

  modal.addComponents(
    new ActionRowBuilder<TextInputBuilder>().addComponents(name),
    new ActionRowBuilder<TextInputBuilder>().addComponents(slots),
    new ActionRowBuilder<TextInputBuilder>().addComponents(mode),
  );

  return modal;
}

export function modalSchedule(customId: string) {
  const modal = new ModalBuilder().setCustomId(customId).setTitle('Planning des matchs');

  const format = new TextInputBuilder()
    .setCustomId('format')
    .setLabel('Format (ex: 1-2,3-4 | 1-3,2-4)')
    .setStyle(TextInputStyle.Paragraph)
    .setRequired(true);

  modal.addComponents(new ActionRowBuilder<TextInputBuilder>().addComponents(format));
  return modal;
}
