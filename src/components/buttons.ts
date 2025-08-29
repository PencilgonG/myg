import { ActionRowBuilder, ButtonBuilder, ButtonStyle } from 'discord.js';

export function row(...buttons: ButtonBuilder[]) {
  return new ActionRowBuilder<ButtonBuilder>().addComponents(...buttons);
}

export function btn(id: string, label: string, style: ButtonStyle = ButtonStyle.Secondary) {
  return new ButtonBuilder().setCustomId(id).setLabel(label).setStyle(style);
}
