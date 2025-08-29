import { ModalBuilder, TextInputBuilder, TextInputStyle, ActionRowBuilder } from 'discord.js';

export function modalLobbyConfig(id: string) {
  const modal = new ModalBuilder().setCustomId(id).setTitle('Configuration du lobby');
  const name = new TextInputBuilder().setCustomId('name').setLabel('Nom du lobby').setRequired(true).setStyle(TextInputStyle.Short);
  const slots = new TextInputBuilder().setCustomId('slots').setLabel('Nombre de slots (équipes)').setRequired(true).setStyle(TextInputStyle.Short).setValue('2');
  const mode = new TextInputBuilder().setCustomId('mode').setLabel('Mode (5v5,4v4,3v3,2v2,1v1,ARAM,TFT)').setRequired(true).setStyle(TextInputStyle.Short).setValue('5v5');

  modal.addComponents(
    new ActionRowBuilder<TextInputBuilder>().addComponents(name),
    new ActionRowBuilder<TextInputBuilder>().addComponents(slots),
    new ActionRowBuilder<TextInputBuilder>().addComponents(mode)
  );
  return modal;
}
