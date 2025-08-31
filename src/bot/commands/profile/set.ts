// src/bot/commands/profile/set.ts
import type { ChatInputCommandInteraction } from "discord.js";
import { MessageFlags } from "discord.js";

import { prisma } from "../../../infra/prisma.js";
import { baseEmbed } from "../../../components/embeds.js";
import { RoleName } from "../../../domain/types.js";

// Regions alignées sur l'enum Prisma LoLRegion (valeurs UPPERCASE)
const REGION_CHOICES = [
  "EUW",
  "EUNE",
  "NA",
  "KR",
  "JP",
  "OCE",
  "BR",
  "LAN",
  "LAS",
  "TR",
  "RU",
] as const;

type RegionValue = (typeof REGION_CHOICES)[number];

function parseMainRole(input?: string | null): RoleName | undefined {
  if (!input) return undefined;
  const k = input.toUpperCase();
  // On accepte TOP/JUNGLE/MID/ADC/SUPPORT/FLEX
  if ((RoleName as any)[k]) return k as RoleName;
  return undefined;
}

export async function handleProfileSet(interaction: ChatInputCommandInteraction) {
  // champs attendus :
  // summoner: string (Nom#Tag)
  // opgg: string (url) - optionnel
  // dpm: string (url) - optionnel
  // mainrole: string (enum RoleName) - optionnel
  // region: string (enum LoLRegion) - optionnel  👈 NOUVEAU

  const summoner = interaction.options.getString("summoner")?.trim() || null;
  const opgg = interaction.options.getString("opgg")?.trim() || null;
  const dpm = interaction.options.getString("dpm")?.trim() || null;
  const mainRoleRaw = interaction.options.getString("mainrole");
  const regionRaw = interaction.options.getString("region");

  const mainRole = parseMainRole(mainRoleRaw) || null;

  let region: RegionValue | null = null;
  if (regionRaw) {
    const up = regionRaw.toUpperCase();
    if ((REGION_CHOICES as readonly string[]).includes(up)) {
      region = up as RegionValue;
    }
  }

  await prisma.userProfile.upsert({
    where: { discordUserId: interaction.user.id },
    create: {
      discordUserId: interaction.user.id,
      summonerName: summoner,
      opggUrl: opgg,
      dpmUrl: dpm,
      preferredRoles: mainRole ? [mainRole] : [],
      region: region ?? undefined,
    },
    update: {
      summonerName: summoner ?? undefined,
      opggUrl: opgg ?? undefined,
      dpmUrl: dpm ?? undefined,
      preferredRoles: mainRole ? [mainRole] : [],
      region: region ?? undefined,
    },
  });

  const embed = baseEmbed("Profil mis à jour").addFields(
    { name: "Summoner", value: summoner || "—", inline: true },
    { name: "Rôle principal", value: mainRole ?? "—", inline: true },
    { name: "Région", value: region ?? "—", inline: true },
    { name: "OP.GG", value: opgg || "—", inline: false },
    { name: "DPM", value: dpm || "—", inline: false },
  );

  await interaction.reply({
    embeds: [embed],
    flags: MessageFlags.Ephemeral,
  });
}
