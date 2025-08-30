// src/bot/commands/profile/view.ts
import type { ChatInputCommandInteraction } from "discord.js";
import { prisma } from "../../../infra/prisma.js";
import { baseEmbed } from "../../../components/embeds.js";

export async function handleProfileView(interaction: ChatInputCommandInteraction) {
  const user = interaction.options.getUser("user") ?? interaction.user;
  const profile = await prisma.userProfile.findUnique({
    where: { discordUserId: user.id },
  });

  const roleLabel = profile?.preferredRoles?.[0] ?? "—";
  const summonerLabel =
    profile?.summonerName && profile?.opggUrl
      ? `[${profile.summonerName}](${profile.opggUrl})`
      : (profile?.summonerName ?? "—");

  const embed = baseEmbed(`Profil de ${user.username}`).addFields(
    { name: "Utilisateur", value: `<@${user.id}>`, inline: true },
    { name: "Main role", value: String(roleLabel), inline: true },
    { name: "Summoner", value: summonerLabel, inline: false },
    { name: "OP.GG", value: profile?.opggUrl ?? "—", inline: true },
    { name: "DPM", value: profile?.dpmUrl ?? "—", inline: true },
  );

  await interaction.reply({ embeds: [embed], ephemeral: true });
}
