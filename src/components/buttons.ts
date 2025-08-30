import { ActionRowBuilder, ButtonBuilder, ButtonStyle } from "discord.js";

/** Crée un bouton */
export function btn(
  customId: string,
  label: string,
  style: ButtonStyle = ButtonStyle.Primary
): ButtonBuilder {
  return new ButtonBuilder()
    .setCustomId(customId)
    .setLabel(label)
    .setStyle(style);
}

/** Crée une row qui contient un ou plusieurs boutons */
export function row(...components: ButtonBuilder[]) {
  return new ActionRowBuilder<ButtonBuilder>().addComponents(components);
}
