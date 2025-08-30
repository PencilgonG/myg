import {
  ChatInputCommandInteraction,
  SlashCommandBuilder,
  EmbedBuilder,
} from "discord.js";
import { createLolProDraftLinks } from "../../bot/draft/lolprodraft.js";

export const data = new SlashCommandBuilder()
  .setName("draft")
  .setDescription("Créer une draft LoLProDraft avec liens auto")
  .addStringOption((opt) =>
    opt
      .setName("blue")
      .setDescription("Nom de l'équipe bleue")
      .setRequired(true)
  )
  .addStringOption((opt) =>
    opt
      .setName("red")
      .setDescription("Nom de l'équipe rouge")
      .setRequired(true)
  );

export async function execute(interaction: ChatInputCommandInteraction) {
  const blueName = interaction.options.getString("blue", true);
  const redName = interaction.options.getString("red", true);

  // Génère les 4 liens (Blue / Red / Spec / Stream)
  const links = createLolProDraftLinks(blueName, redName);

  const embed = new EmbedBuilder()
    .setTitle(`Draft créée (${links.roomId})`)
    .setDescription("Voici les liens générés automatiquement :")
    .addFields(
      { name: "🔵 Blue", value: links.blue },
      { name: "🔴 Red", value: links.red },
      { name: "👀 Spectateur", value: links.spec },
      { name: "📺 Stream overlay", value: links.stream }
    )
    .setColor(0x1d4ed8); // bleu Discord

  await interaction.reply({ embeds: [embed] });
}
