import { ActionRowBuilder, StringSelectMenuBuilder, StringSelectMenuOptionBuilder } from 'discord.js';


export function selectMenu(
customId: string,
placeholder: string,
options: { label: string; value: string; description?: string }[],
minValues = 1,
maxValues = 1
) {
const menu = new StringSelectMenuBuilder()
.setCustomId(customId)
.setPlaceholder(placeholder)
.setMinValues(minValues)
.setMaxValues(maxValues);


for (const opt of options.slice(0, 25)) {
menu.addOptions(new StringSelectMenuOptionBuilder().setLabel(opt.label).setValue(opt.value).setDescription(opt.description ?? ''));
}
return new ActionRowBuilder<StringSelectMenuBuilder>().addComponents(menu);
}