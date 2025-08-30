// src/bot/lobby/matches.ts
import type { ButtonInteraction, Guild, TextChannel, CategoryChannel } from "discord.js";
import { ButtonStyle, MessageFlags } from "discord.js";

import { prisma } from "../../infra/prisma.js";
import { baseEmbed } from "../../components/embeds.js";
import { IDS } from "../interactions/ids.js";
import { row, btn } from "../../components/buttons.js";
import { createLolProDraftLinks } from "../../services/draft/lolprodraft.js";

/* ------------------------------- Helpers -------------------------------- */

function chunkFirst<T>(arr: T[], n: number): T[] {
  return arr.slice(0, Math.max(0, Math.min(n, arr.length)));
}

async function fetchTextChannel(guild: Guild, id?: string | null) {
  if (!id) return null;
  const ch = await guild.channels.fetch(id).catch(() => null);
  return ch && (ch as any).isTextBased?.() ? (ch as TextChannel) : null;
}

function batchSizeForLobby(slots: number): number {
  return slots === 4 ? 2 : 1;
}

function matchTitle(m: { indexInRound: number; round: number }) {
  return `Match ${m.indexInRound + 1} — Round ${m.round + 1}`;
}

// formateur d’une ligne joueur : "<@user> — [Summoner](opgg)"
function formatParticipantLine(p: {
  userId: string;
  profile: { summonerName: string | null; opggUrl: string | null } | null;
}) {
  const who = `<@${p.userId}>`;
  const sum =
    p.profile?.summonerName && p.profile?.opggUrl
      ? `[${p.profile.summonerName}](${p.profile.opggUrl})`
      : (p.profile?.summonerName ?? null);
  return sum ? `${who} — ${sum}` : who;
}

/* --------------------------- Messages d’équipes -------------------------- */

async function postTeamMessage(
  guild: Guild,
  team: { id: string; roleId: string | null; textChannelId: string | null; name: string; number: number },
  sideLabel: "Blue" | "Red",
  sideUrl: string,
  specUrl: string,
  title: string
) {
  const ch = await fetchTextChannel(guild, team.textChannelId ?? null);
  if (!ch) return;

  const mention = team.roleId ? `<@&${team.roleId}>` : "";
  const embed = baseEmbed(`${title}`)
    .addFields(
      { name: `Votre lien (${sideLabel})`, value: sideUrl, inline: false },
      { name: "Spec", value: specUrl, inline: false },
    );

  await ch.send({ content: mention, embeds: [embed] });
}

async function postGeneralMessage(
  guild: Guild,
  generalChannelId: string,
  matchId: string,
  title: string,
  specUrl: string
) {
  const ch = await fetchTextChannel(guild, generalChannelId);
  if (!ch) return;

  const embed = baseEmbed(title).addFields({ name: "Spec", value: specUrl });

  const components = row(
    btn(IDS.match.validate(matchId), "Valider", ButtonStyle.Success),
    btn(IDS.draft.remake(matchId), "Remake draft"),
  );

  await ch.send({ embeds: [embed], components: [components] });
}

/* ----------------------- Préparation / envoi d’un match ------------------ */

async function prepareAndSendMatch(
  guild: Guild,
  lobbyId: string,
  generalChannelId: string,
  matchId?: string
) {
  if (!matchId) return;

  const match = await prisma.match.findUniqueOrThrow({
    where: { id: matchId },
    include: {
      blueTeam: true,
      redTeam: true,
      lobby: true,
    },
  });

  const title = matchTitle(match);

  let blueTeam = match.blueTeam;
  let redTeam = match.redTeam;

  const isUnsent = !match.draftBlueUrl && !match.draftRedUrl && !match.specUrl;

  if (isUnsent) {
    const flip = Math.random() < 0.5;
    if (flip) {
      [blueTeam, redTeam] = [redTeam, blueTeam];
      await prisma.match.update({
        where: { id: match.id },
        data: { blueTeamId: blueTeam.id, redTeamId: redTeam.id },
      });
    }

    const links = await createLolProDraftLinks(
      blueTeam.name,
      redTeam.name,
      title
    );

    await prisma.match.update({
      where: { id: match.id },
      data: {
        draftBlueUrl: links.blue,
        draftRedUrl: links.red,
        specUrl: links.spec,
      },
    });

    match.draftBlueUrl = links.blue;
    match.draftRedUrl = links.red;
    match.specUrl = links.spec;
  }

  await postTeamMessage(
    guild,
    { ...blueTeam, roleId: blueTeam.roleId ?? null, textChannelId: blueTeam.textChannelId ?? null } as any,
    "Blue",
    match.draftBlueUrl!,
    match.specUrl!,
    title
  );

  await postTeamMessage(
    guild,
    { ...redTeam, roleId: redTeam.roleId ?? null, textChannelId: redTeam.textChannelId ?? null } as any,
    "Red",
    match.draftRedUrl!,
    match.specUrl!,
    title
  );

  await postGeneralMessage(guild, generalChannelId, match.id, title, match.specUrl!);
}

/* ------------------- Envoi d’un batch de matchs par round ----------------- */

export async function sendRoundMatches(
  guild: Guild,
  lobbyId: string,
  round: number,
  generalChannelId: string
) {
  const lobby = await prisma.lobby.findUniqueOrThrow({ where: { id: lobbyId } });

  const allInRound = await prisma.match.findMany({
    where: { lobbyId, round },
    orderBy: { indexInRound: "asc" },
  });
  if (!allInRound.length) return;

  const unsent = allInRound.filter(m => !m.draftBlueUrl && !m.specUrl);
  if (!unsent.length) return;

  const size = batchSizeForLobby(lobby.slots);
  const batch = chunkFirst(unsent, size);

  for (const m of batch) {
    await prepareAndSendMatch(guild, lobbyId, generalChannelId, m.id);
  }
}

/* ------------------------ Nettoyage des ressources ------------------------ */

async function cleanupLobbyResources(guild: Guild, lobbyId: string) {
  const lobby = await prisma.lobby.findUniqueOrThrow({
    where: { id: lobbyId },
    include: { teams: true },
  });

  const possibleCategoryIds = new Set<string>();
  for (const t of lobby.teams) {
    try {
      if (t.textChannelId) {
        const ch = await guild.channels.fetch(t.textChannelId).catch(() => null);
        // @ts-ignore
        if (ch?.parentId) possibleCategoryIds.add(ch.parentId as string);
        await ch?.delete().catch(() => {});
      }
    } catch {}

    try {
      if (t.voiceChannelId) {
        const ch = await guild.channels.fetch(t.voiceChannelId).catch(() => null);
        // @ts-ignore
        if (ch?.parentId) possibleCategoryIds.add(ch.parentId as string);
        await ch?.delete().catch(() => {});
      }
    } catch {}

    try {
      if (t.roleId) {
        const role = await guild.roles.fetch(t.roleId).catch(() => null);
        await role?.delete("Inhouse terminé — nettoyage auto").catch(() => {});
      }
    } catch {}

    await prisma.team.update({
      where: { id: t.id },
      data: { roleId: null, textChannelId: null, voiceChannelId: null },
    });
  }

  for (const catId of possibleCategoryIds) {
    try {
      const cat = await guild.channels.fetch(catId).catch(() => null);
      if (cat && cat.type === 4 /* GuildCategory */) {
        const c = cat as unknown as CategoryChannel;
        // @ts-ignore
        const children = c.children?.cache ?? (await guild.channels.fetch()).filter(ch => (ch as any).parentId === catId);
        if (children.size === 0) {
          await c.delete("Inhouse terminé — catégorie vide").catch(() => {});
        }
      }
    } catch {}
  }

  await prisma.lobby.update({
    where: { id: lobbyId },
    data: { state: "FINISHED" },
  });
}

/* ------------------------ Validation & avancement -------------------------- */

export async function onMatchValidated(
  interaction: ButtonInteraction,
  matchIdFromDispatcher?: string
) {
  await interaction.deferUpdate().catch(() => {});

  const mid =
    matchIdFromDispatcher ||
    (interaction.customId?.startsWith("match:validate:")
      ? interaction.customId.split(":")[2]
      : undefined);

  if (!mid) {
    return interaction.followUp({
      content: "❌ match id invalide.",
      flags: MessageFlags.Ephemeral,
    }).catch(() => {});
  }

  const match = await prisma.match.update({
    where: { id: mid },
    data: { state: "DONE" },
    include: { lobby: true },
  });

  const lobby = match.lobby;

  const roundMatches = await prisma.match.findMany({
    where: { lobbyId: lobby.id, round: match.round },
    orderBy: { indexInRound: "asc" },
  });

  const remainingActive = roundMatches.filter(m => m.draftBlueUrl && m.state !== "DONE");
  const unsent = roundMatches.filter(m => !m.draftBlueUrl && !m.specUrl);

  if (remainingActive.length === 0 && unsent.length === 0) {
    const nextRound = match.round + 1;
    const hasNext = await prisma.match.count({
      where: { lobbyId: lobby.id, round: nextRound },
    });

    if (hasNext > 0) {
      await prisma.lobby.update({
        where: { id: lobby.id },
        data: { currentRound: nextRound },
      });

      await sendRoundMatches(
        interaction.guild!,
        lobby.id,
        nextRound,
        lobby.channelId,
      );

      return;
    }

    await interaction.followUp({
      content: "🏁 Tous les matchs sont terminés. Nettoyage des salons & rôles…",
      flags: MessageFlags.Ephemeral,
    }).catch(() => {});

    await cleanupLobbyResources(interaction.guild!, lobby.id);

    return;
  }

  if (remainingActive.length === 0 && unsent.length > 0) {
    await sendRoundMatches(
      interaction.guild!,
      lobby.id,
      match.round,
      lobby.channelId,
    );
  }
}

/* ------------------------------ Remake draft ------------------------------- */

export async function onDraftRemakeButton(
  interaction: ButtonInteraction,
  matchIdFromDispatcher?: string
) {
  await interaction.deferUpdate().catch(() => {});

  const mid =
    matchIdFromDispatcher ||
    (interaction.customId?.startsWith("draft:remake:")
      ? interaction.customId.split(":")[2]
      : undefined);

  if (!mid) {
    return interaction.followUp({
      content: "❌ match id invalide.",
      flags: MessageFlags.Ephemeral,
    }).catch(() => {});
  }

  const match = await prisma.match.findUniqueOrThrow({
    where: { id: mid },
    include: { blueTeam: true, redTeam: true, lobby: true },
  });

  const blueTeam = match.blueTeam;
  const redTeam = match.redTeam;
  const title = `${matchTitle(match)} (remake)`;

  const links = await createLolProDraftLinks(
    blueTeam.name,
    redTeam.name,
    title,
  );

  await prisma.match.update({
    where: { id: match.id },
    data: {
      draftBlueUrl: links.blue,
      draftRedUrl: links.red,
      specUrl: links.spec,
    },
  });

  await postTeamMessage(
    interaction.guild!,
    { ...blueTeam, roleId: blueTeam.roleId ?? null, textChannelId: blueTeam.textChannelId ?? null } as any,
    "Blue",
    links.blue,
    links.spec,
    title,
  );

  await postTeamMessage(
    interaction.guild!,
    { ...redTeam, roleId: redTeam.roleId ?? null, textChannelId: redTeam.textChannelId ?? null } as any,
    "Red",
    links.red,
    links.spec,
    title,
  );

  await postGeneralMessage(
    interaction.guild!,
    match.lobby.channelId,
    match.id,
    title,
    links.spec,
  );

  await interaction.followUp({
    content: "♻️ Draft régénérée et renvoyée dans les salons.",
    flags: MessageFlags.Ephemeral,
  }).catch(() => {});
}

/* ---------------------------- Line-up (propre) ---------------------------- */

export async function postLineupSummary(
  guild: Guild,
  lobbyId: string,
  channelId: string
) {
  const lobby = await prisma.lobby.findUniqueOrThrow({
    where: { id: lobbyId },
    include: {
      teams: { orderBy: { number: "asc" } },
      matches: true,
      participants: {
        where: { teamNumber: { not: null } },
        include: { profile: true },
        orderBy: [{ teamNumber: "asc" }, { isCaptain: "desc" }, { userId: "asc" }],
      },
    },
  });

  const embed = baseEmbed("Line-up & Planning");

  for (const t of lobby.teams) {
    const members = lobby.participants
      .filter(p => p.teamNumber === t.number)
      .sort((a, b) => (a.isCaptain === b.isCaptain ? 0 : a.isCaptain ? -1 : 1));

    const lines =
      members.length === 0
        ? "—"
        : members.map(formatParticipantLine).map(s => (members.find(m => m.isCaptain && formatParticipantLine(m) === s) ? `**${s} (C)**` : s)).join("\n");

    embed.addFields({ name: `Équipe ${t.number}`, value: lines, inline: true });
  }

  const teamsById = new Map(lobby.teams.map(t => [t.id, t]));
  const scheduleLines = lobby.matches
    .slice()
    .sort((a, b) => (a.round === b.round ? a.indexInRound - b.indexInRound : a.round - b.round))
    .map(m => {
      const A = teamsById.get(m.blueTeamId);
      const B = teamsById.get(m.redTeamId);
      return `**R${m.round + 1} M${m.indexInRound + 1}** — Équipe ${A?.number} vs Équipe ${B?.number}`;
    })
    .join("\n");

  embed.addFields({ name: "Planning", value: scheduleLines || "—", inline: false });

  const ch = await fetchTextChannel(guild, channelId);
  if (ch) await ch.send({ embeds: [embed] });
}
