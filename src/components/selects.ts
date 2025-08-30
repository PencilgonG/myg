import { ActionRowBuilder, StringSelectMenuBuilder } from 'discord.js';

export function selectMenu(customId: string, placeholder: string, options: { label: string; value: string }[], min = 1, max = 1) {
  const menu = new StringSelectMenuBuilder()
    .setCustomId(customId)
    .setPlaceholder(placeholder)
    .setMinValues(min)
    .setMaxValues(max)
    .addOptions(options.map(o => ({ label: o.label, value: o.value })));
  return new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(menu);
}
