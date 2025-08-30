// src/bot/lobby/wizard.ts
import type {
  ButtonInteraction,
  ModalSubmitInteraction,
  StringSelectMenuInteraction,
  MessageEditOptions,
  ChatInputCommandInteraction,
} from "discord.js";
import { ButtonStyle, MessageFlags } from "discord.js";
import { prisma } from "../../infra/prisma.js";
import { IDS } from "../interactions/ids.js";
import { modalLobbyConfig } from "../../components/modals.js";
import { baseEmbed } from "../../components/embeds.js";
import { row, btn } from "../../components/buttons.js";
import { selectMenu } from "../../components/selects.js";
import {
  GameMode,
  RoleName,
  rosterSizeFor,
  modeLabel,
} from "../../domain/types.js";
import { parseScheduleFormat } from "./schedule.js";
import {
  sendRoundMatches,
  onMatchValidated,
  onDraftRemakeButton,
  postLineupSummary,
} from "./matches.js";
import {
  ensureLobbyCategory,
  ensureTeamResources,
} from "../../services/guild.js";

/* ───────────────────────────── helpers ───────────────────────────── */

function toGameMode(input: string): GameMode {
  const map = new Set(["SR_5v5", "SR_4v4", "SR_3v3", "SR_2v2"]);
  const key = (input || "SR_5v5").toUpperCase();
  return (map.has(key) ? key : "SR_5v5") as GameMode;
}

function lobbyEmbed(lobby: { name: string; slots: number; mode: GameMode }) {
  return baseEmbed(
    "Créer un lobby",
    "Configuration mise à jour. Clique sur **Valider** pour continuer."
  ).addFields(
    { name: "Nom", value: lobby.name, inline: true },
    { name: "Slots (équipes)", value: String(lobby.slots), inline: true },
    { name: "Mode", value: modeLabel(lobby.mode), inline: true }
  );
}

function controlsRow(lobbyId: string) {
  return row(
    btn(IDS.lobby.openConfig(lobbyId), "Configurer"),
    btn(IDS.lobby.testFill(lobbyId), "Test (auto-fill)"),
    btn(IDS.lobby.validate(lobbyId), "Valider", ButtonStyle.Success)
  );
}

async function acknowledgeAndEdit(
  interaction: ButtonInteraction,
  payload: MessageEditOptions
) {
  try {
    await interaction.deferUpdate();
  } catch {}
  try {
    await (interaction.message as any).edit(payload);
  } catch {}
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

/* ─────────────────────── WAITING ROOM (signup) ─────────────────────── */

function waitingRoomButtons(lobbyId: string) {
  const r1 = row(
    btn(`wait:join:role:${RoleName.TOP}:${lobbyId}`, "TOP"),
    btn(`wait:join:role:${RoleName.JUNGLE}:${lobbyId}`, "JUNGLE"),
    btn(`wait:join:role:${RoleName.MID}:${lobbyId}`, "MID"),
    btn(`wait:join:role:${RoleName.ADC}:${lobbyId}`, "ADC"),
    btn(`wait:join:role:${RoleName.SUPPORT}:${lobbyId}`, "SUPPORT")
  );
  const r2 = row(
    btn(`wait:join:role:${RoleName.FLEX}:${lobbyId}`, "FLEX"),
    btn(`wait:join:sub:${lobbyId}`, "S’inscrire en SUB", ButtonStyle.Secondary),
    btn(`wait:leave:${lobbyId}`, "Se désinscrire", ButtonStyle.Danger),
    btn(`wait:pick:${lobbyId}`, "Pick teams", ButtonStyle.Success)
  );
  return [r1, r2];
}

async function renderWaitingRoomEmbed(lobbyId: string) {
  const lobby = await prisma.lobby.findUniqueOrThrow({ where: { id: lobbyId } });
  const participants = await prisma.lobbyParticipant.findMany({
    where: { lobbyId },
    include: { profile: true },
    orderBy: { userId: "asc" },
  });

  const byRole: Record<RoleName, string[]> = {
    [RoleName.TOP]: [],
    [RoleName.JUNGLE]: [],
    [RoleName.MID]: [],
    [RoleName.ADC]: [],
    [RoleName.SUPPORT]: [],
    [RoleName.FLEX]: [],
  } as any;
  const subs: string[] = [];

  for (const p of participants) {
    const line = formatParticipantLine(p);
    if (p.isSub) subs.push(line);
    else if (p.selectedRole) byRole[p.selectedRole].push(line);
  }

  const embed = baseEmbed(
    `Salle d’attente — ${lobby.name}`,
    "Inscrivez-vous par rôle ou en SUB. Vous pouvez vous désinscrire à tout moment. Quand prêt, cliquez **Pick teams**."
  )
    .addFields(
      { name: "TOP", value: byRole.TOP.join("\n") || "—", inline: true },
      { name: "JUNGLE", value: byRole.JUNGLE.join("\n") || "—", inline: true },
      { name: "MID", value: byRole.MID.join("\n") || "—", inline: true },
    )
    .addFields(
      { name: "ADC", value: byRole.ADC.join("\n") || "—", inline: true },
      { name: "SUPPORT", value: byRole.SUPPORT.join("\n") || "—", inline: true },
      { name: "FLEX", value: byRole.FLEX.join("\n") || "—", inline: true },
    )
    .addFields({
      name: "SUBS",
      value: subs.join("\n") || "—",
      inline: false,
    });

  return embed;
}

async function showWaitingRoom(interaction: ButtonInteraction, lobbyId: string) {
  const embed = await renderWaitingRoomEmbed(lobbyId);
  const components = waitingRoomButtons(lobbyId);
  await acknowledgeAndEdit(interaction, { embeds: [embed], components });
}

async function signupForRole(userId: string, lobbyId: string, role: RoleName) {
  await prisma.userProfile.upsert({
    where: { discordUserId: userId },
    create: { discordUserId: userId },
    update: {},
  });
  await prisma.lobbyParticipant.upsert({
    where: { lobbyId_userId: { lobbyId, userId } },
    create: { lobbyId, userId, selectedRole: role, isSub: false },
    update: { selectedRole: role, isSub: false },
  });
}

async function signupAsSub(userId: string, lobbyId: string) {
  await prisma.userProfile.upsert({
    where: { discordUserId: userId },
    create: { discordUserId: userId },
    update: {},
  });
  await prisma.lobbyParticipant.upsert({
    where: { lobbyId_userId: { lobbyId, userId } },
    create: { lobbyId, userId, isSub: true, selectedRole: null },
    update: { isSub: true, selectedRole: null },
  });
}

async function leaveWaitingRoom(userId: string, lobbyId: string) {
  await prisma.lobbyParticipant.deleteMany({ where: { lobbyId, userId } });
}

/* ─────────────────────────── slash / lobby ─────────────────────────── */

export async function handleSlashLobby(
  interaction: ChatInputCommandInteraction
) {
  const name = "Inhouse Lobby";
  const slots = 2;
  const mode = toGameMode("SR_5v5");

  await interaction.reply({
    embeds: [lobbyEmbed({ name, slots, mode })],
    components: [controlsRow("temp")],
  });
  const msg = await interaction.fetchReply();

  const lobby = await prisma.lobby.create({
    data: {
      guildId: interaction.guildId!,
      channelId: msg.channelId,
      messageId: msg.id as string,
      name,
      slots,
      mode,
      createdBy: interaction.user.id,
    },
  });

  await (interaction.editReply as any)({
    embeds: [lobbyEmbed(lobby)],
    components: [controlsRow(lobby.id)],
  });
}

/* ────────────────────────── button handlers ────────────────────────── */

export async function onLobbyButton(interaction: ButtonInteraction) {
  const id = interaction.customId;

  if (id.startsWith("lobby:config:")) {
    const lobbyId = id.split(":")[2];
    return interaction.showModal(
      modalLobbyConfig(IDS.lobby.configModal(lobbyId))
    );
  }

  if (id.startsWith("lobby:test:")) {
    const lobbyId = id.split(":")[2];
    const lobby = await prisma.lobby.findUniqueOrThrow({ where: { id: lobbyId } });
    for (let i = 0; i < lobby.slots * 5; i++) {
      const uid = `${interaction.user.id}-${i + 1}`;
      await prisma.userProfile.upsert({
        where: { discordUserId: uid },
        create: { discordUserId: uid, summonerName: `Player${i + 1}` },
        update: {},
      });
      await prisma.lobbyParticipant.upsert({
        where: { lobbyId_userId: { lobbyId, userId: uid } },
        create: { lobbyId, userId: uid, selectedRole: RoleName.FLEX },
        update: {},
      });
    }
    try {
      await interaction.reply({
        content: "✅ Participants de test ajoutés. Passage au pick teams…",
        flags: MessageFlags.Ephemeral,
      });
    } catch {}
    const payload = await buildPickPayload(lobbyId, 1);
    return (interaction.message as any).edit(payload);
  }

  if (id.startsWith("lobby:validate:")) {
    const lobbyId = id.split(":")[2];
    return showWaitingRoom(interaction, lobbyId);
  }

  if (id.startsWith("pick:page:")) {
    const [, , lobbyId, teamNo] = id.split(":");
    return openPick(interaction, lobbyId, Number(teamNo));
  }
  if (id.startsWith("pick:prev:")) {
    const [, , lobbyId, teamNo] = id.split(":");
    return openPick(interaction, lobbyId, Math.max(1, Number(teamNo) - 1));
  }
  if (id.startsWith("pick:next:")) {
    const [, , lobbyId, teamNo] = id.split(":");
    return openPick(interaction, lobbyId, Number(teamNo) + 1);
  }
  if (id.startsWith("pick:validate:")) {
    const lobbyId = id.split(":")[2];
    return validateTeams(interaction, lobbyId);
  }
  if (id.startsWith("pick:schedule:")) {
    const lobbyId = id.split(":")[2];
    return showPlanningPicker(interaction, lobbyId);
  }

  if (id.startsWith("wait:join:role:")) {
    const [, , , roleStr, lobbyId] = id.split(":");
    const role = roleStr as RoleName;
    await signupForRole(interaction.user.id, lobbyId, role);
    const embed = await renderWaitingRoomEmbed(lobbyId);
    const components = waitingRoomButtons(lobbyId);
    try { await interaction.deferUpdate(); } catch {}
    return (interaction.message as any).edit({ embeds: [embed], components });
  }
  if (id.startsWith("wait:join:sub:")) {
    const lobbyId = id.split(":")[3];
    await signupAsSub(interaction.user.id, lobbyId);
    const embed = await renderWaitingRoomEmbed(lobbyId);
    const components = waitingRoomButtons(lobbyId);
    try { await interaction.deferUpdate(); } catch {}
    return (interaction.message as any).edit({ embeds: [embed], components });
  }
  if (id.startsWith("wait:leave:")) {
    const lobbyId = id.split(":")[2];
    await leaveWaitingRoom(interaction.user.id, lobbyId);
    const embed = await renderWaitingRoomEmbed(lobbyId);
    const components = waitingRoomButtons(lobbyId);
    try { await interaction.deferUpdate(); } catch {}
    return (interaction.message as any).edit({ embeds: [embed], components });
  }
  if (id.startsWith("wait:pick:")) {
    const lobbyId = id.split(":")[2];
    return openPick(interaction, lobbyId, 1);
  }

  if (id.startsWith("match:validate:")) {
    return onMatchValidated(interaction, id.split(":")[2]);
  }
  if (id.startsWith("draft:remake:")) {
    return onDraftRemakeButton(interaction, id.split(":")[2]);
  }
}

/* ───────────────────────── select handlers ───────────────────────── */

export async function handleLobbySelect(
  interaction: StringSelectMenuInteraction
) {
  const id = interaction.customId;

  if (id.startsWith("select:captain:")) {
    const [, , lobbyId, teamNo] = id.split(":");
    const userId = interaction.values[0];

    await prisma.lobbyParticipant.updateMany({
      where: { lobbyId, teamNumber: Number(teamNo), isCaptain: true },
      data: { isCaptain: false },
    });
    await prisma.lobbyParticipant.updateMany({
      where: { lobbyId, userId },
      data: { teamNumber: Number(teamNo), isCaptain: true },
    });

    await interaction.update({
      content: `✅ Capitaine pour l'équipe ${teamNo} : <@${userId}>`,
      components: [],
      embeds: [],
    });
    const payload = await buildPickPayload(lobbyId, Number(teamNo));
    return (interaction.message as any).edit(payload);
  }

  if (id.startsWith("select:players:")) {
    const [, , lobbyId, teamNo] = id.split(":");
    const members = interaction.values;

    await prisma.lobbyParticipant.updateMany({
      where: { lobbyId, teamNumber: Number(teamNo) },
      data: { teamNumber: null },
    });
    for (const userId of members) {
      await prisma.lobbyParticipant.updateMany({
        where: { lobbyId, userId },
        data: { teamNumber: Number(teamNo) },
      });
    }

    await interaction.update({
      content: `✅ Joueurs affectés à l'équipe ${teamNo}.`,
      components: [],
      embeds: [],
    });
    const payload = await buildPickPayload(lobbyId, Number(teamNo));
    return (interaction.message as any).edit(payload);
  }

  if (id.startsWith("select:planning:")) {
    const lobbyId = id.split(":")[2];
    const choice = interaction.values[0];
    const lobby = await prisma.lobby.findUniqueOrThrow({ where: { id: lobbyId } });
    const schedule = buildScheduleFromChoice(lobby.slots, choice);

    await prisma.match.deleteMany({ where: { lobbyId } });

    for (let r = 0; r < schedule.length; r++) {
      for (let i = 0; i < schedule[r].length; i++) {
        const { a, b } = schedule[r][i];
        const blueTeam = await prisma.team.upsert({
          where: { lobbyId_number: { lobbyId, number: a } },
          create: { lobbyId, number: a, name: `Équipe ${a}` },
          update: {},
        });
        const redTeam = await prisma.team.upsert({
          where: { lobbyId_number: { lobbyId, number: b } },
          create: { lobbyId, number: b, name: `Équipe ${b}` },
          update: {},
        });
        await prisma.match.create({
          data: {
            lobbyId,
            round: r,
            indexInRound: i,
            blueTeamId: blueTeam.id,
            redTeamId: redTeam.id,
          },
        });
      }
    }

    await interaction.update({
      content:
        "✅ Planning généré. Clique **Valider** pour créer rôles/salons et envoyer la manche 1.",
      components: [],
      embeds: [],
    });
  }
}

/* ───────────────────────── modal handlers ───────────────────────── */

export async function handleLobbyModal(interaction: ModalSubmitInteraction) {
  const id = interaction.customId;

  if (id.startsWith("modal:schedule:")) {
    const lobbyId = id.split(":")[2];
    const format = interaction.fields.getTextInputValue("format");
    const lobby = await prisma.lobby.findUniqueOrThrow({ where: { id: lobbyId } });

    const schedule = parseScheduleFormat(format, lobby.slots);
    if (!schedule.length)
      return interaction.reply({
        content: "❌ Format invalide.",
        flags: MessageFlags.Ephemeral,
      });

    await prisma.match.deleteMany({ where: { lobbyId } });

    for (let r = 0; r < schedule.length; r++) {
      for (let i = 0; i < schedule[r].length; i++) {
        const { a, b } = schedule[r][i];
        const blueTeam = await prisma.team.upsert({
          where: { lobbyId_number: { lobbyId, number: a } },
          create: { lobbyId, number: a, name: `Équipe ${a}` },
          update: {},
        });
        const redTeam = await prisma.team.upsert({
          where: { lobbyId_number: { lobbyId, number: b } },
          create: { lobbyId, number: b, name: `Équipe ${b}` },
          update: {},
        });
        await prisma.match.create({
          data: {
            lobbyId,
            round: r,
            indexInRound: i,
            blueTeamId: blueTeam.id,
            redTeamId: redTeam.id,
          },
        });
      }
    }

    return interaction.reply({
      content:
        "✅ Planning enregistré. Clique **Valider** pour créer rôles/salons et envoyer la manche 1.",
      flags: MessageFlags.Ephemeral,
    });
  }

  if (id.startsWith("modal:config:")) {
    const lobbyId = id.split(":")[2];
    const name = interaction.fields.getTextInputValue("name");
    const slots = Number(interaction.fields.getTextInputValue("slots") || "2");
    const mode = toGameMode(interaction.fields.getTextInputValue("mode"));

    await prisma.lobby.update({
      where: { id: lobbyId },
      data: { name, slots, mode },
    });

    const lobby = await prisma.lobby.findUniqueOrThrow({ where: { id: lobbyId } });
    const ch = (await interaction.client.channels.fetch(lobby.channelId).catch(() => null)) as any;
    if (ch?.isTextBased?.()) {
      const msg = await ch.messages.fetch(lobby.messageId!).catch(() => null);
      if (msg)
        await msg.edit({
          embeds: [lobbyEmbed({ name, slots, mode })],
          components: [controlsRow(lobbyId)],
        });
    }

    try {
      await interaction.reply({
        content: "⚙️ Config mise à jour.",
        flags: MessageFlags.Ephemeral,
      });
    } catch {}
    return;
  }

  return interaction.reply({
    content: "❌ Modal inconnue.",
    flags: MessageFlags.Ephemeral,
  });
}

/* ───────────────────────────── pick flow ───────────────────────────── */

async function buildPickPayload(
  lobbyId: string,
  teamNo: number
): Promise<MessageEditOptions> {
  const lobby = await prisma.lobby.findUniqueOrThrow({ where: { id: lobbyId } });

  for (let i = 1; i <= lobby.slots; i++) {
    await prisma.team.upsert({
      where: { lobbyId_number: { lobbyId, number: i } },
      create: { lobbyId, number: i, name: `Équipe ${i}` },
      update: {},
    });
  }

  const team = await prisma.team.findUniqueOrThrow({
    where: { lobbyId_number: { lobbyId, number: teamNo } },
  });
  const participants = await prisma.lobbyParticipant.findMany({
    where: { lobbyId },
    include: { profile: true },
    orderBy: { userId: "asc" },
  });
  const rosterSize = rosterSizeFor(lobby.mode);

  const currentMembers = participants.filter((p) => p.teamNumber === teamNo);
  const captain = currentMembers.find((p) => p.isCaptain);

  const rosterCount = currentMembers.length;
  const rosterList = currentMembers.length
    ? currentMembers.map((o) => `<@${o.userId}>`).join(" ")
    : "—";

  const embed = baseEmbed(`Pick équipes — ${team.name}`)
    .addFields(
      { name: "Équipe", value: `${team.number}/${lobby.slots}`, inline: true },
      {
        name: "Capitaine",
        value: captain ? `<@${captain.userId}>` : "—",
        inline: true,
      },
      {
        name: `Joueurs (${rosterCount}/${rosterSize})`,
        value: rosterList,
        inline: false,
      }
    )
    .setDescription(
      "Sélectionne le **capitaine** puis les **joueurs** (le capitaine doit aussi être dans les joueurs). Utilise *Suivant/Précédent* pour changer d’équipe."
    );

  const allOptions = participants.map((p) => ({
    label: p.profile?.summonerName || p.userId,
    value: p.userId,
  }));

  const menus = [
    selectMenu(
      IDS.lobby.selectCaptain(lobbyId, teamNo),
      "Capitaine",
      allOptions,
      1,
      1
    ),
    selectMenu(
      IDS.lobby.selectPlayers(lobbyId, teamNo),
      `Joueurs (${rosterCount}/${rosterSize})`,
      allOptions,
      1,
      rosterSize
    ),
  ];

  const navRow = row(
    btn(IDS.lobby.pickPrev(lobbyId, teamNo), "← Précédent"),
    btn(IDS.lobby.pickNext(lobbyId, teamNo), "Suivant →")
  );
  const actionsRow = row(
    btn(IDS.lobby.pickSchedule(lobbyId), "Planning des matchs"),
    btn(IDS.lobby.pickValidate(lobbyId), "Valider", ButtonStyle.Success)
  );

  return { embeds: [embed], components: [...menus, navRow, actionsRow] as any };
}

async function openPick(
  interaction: ButtonInteraction,
  lobbyId: string,
  teamNo: number
) {
  const lobby = await prisma.lobby.findUniqueOrThrow({ where: { id: lobbyId } });
  const t = Math.min(Math.max(1, teamNo), lobby.slots);
  const payload = await buildPickPayload(lobbyId, t);
  return acknowledgeAndEdit(interaction, payload);
}

/* ─────────────── Planning picker (menu) + génération ─────────────── */

function showPlanningPicker(inter: ButtonInteraction, lobbyId: string) {
  return inter.reply({
    content: "🗓️ Choisis un planning :",
    components: [
      selectMenu(
        `select:planning:${lobbyId}`,
        "Sélectionne un planning",
        [
          { label: "2 équipes — Bo1", value: "2:bo1" },
          { label: "2 équipes — Bo3", value: "2:bo3" },
          { label: "2 équipes — Bo5", value: "2:bo5" },
          { label: "4 équipes — 1 round (random)", value: "4:1" },
          { label: "4 équipes — 2 rounds (random)", value: "4:2" },
          { label: "4 équipes — 3 rounds (round robin)", value: "4:3" },
        ],
        1,
        1
      ),
    ],
    flags: MessageFlags.Ephemeral,
  });
}

function shuffleInPlace<T>(a: T[]) {
  for (let i = a.length - 1; i > 0; i--) {
    const j = (Math.random() * (i + 1)) | 0;
    [a[i], a[j]] = [a[j], a[i]];
  }
}

function buildScheduleFromChoice(
  slots: number,
  choice: string
): { a: number; b: number }[][] {
  if (slots === 2) {
    const count = choice.endsWith("bo5") ? 5 : choice.endsWith("bo3") ? 3 : 1;
    return Array.from({ length: count }, () => [{ a: 1, b: 2 }]);
  }

  const rr: { a: number; b: number }[][] = [
    [
      { a: 1, b: 2 },
      { a: 3, b: 4 },
    ],
    [
      { a: 1, b: 3 },
      { a: 2, b: 4 },
    ],
    [
      { a: 1, b: 4 },
      { a: 2, b: 3 },
    ],
  ];

  const ask = Number(choice.split(":")[1] || "3");
  if (ask >= 3) return rr;

  const copy = rr.slice();
  shuffleInPlace(copy);
  return copy.slice(0, Math.max(1, Math.min(ask, 3)));
}

/* ────────────────────── validation & round 1 send ───────────────────── */

async function validateTeams(
  interaction: ButtonInteraction,
  lobbyId: string
) {
  const lobby = await prisma.lobby.findUniqueOrThrow({ where: { id: lobbyId } });
  const category = await ensureLobbyCategory(interaction.guild!, `${lobby.name}`);

  for (let n = 1; n <= lobby.slots; n++) {
    const team = await prisma.team.findUniqueOrThrow({
      where: { lobbyId_number: { lobbyId, number: n } },
    });

    const res = await ensureTeamResources(
      interaction.guild!,
      category.id,
      team.name
    );

    await prisma.team.update({
      where: { id: team.id },
      data: {
        roleId: res.roleId,
        textChannelId: res.textChannelId,
        voiceChannelId: res.voiceChannelId,
      },
    });
  }

  const matchesCount = await prisma.match.count({
    where: { lobbyId, round: 0 },
  });
  if (matchesCount === 0) {
    return interaction.reply({
      content:
        "✅ Équipes validées. Clique **Planning des matchs** pour définir le planning.",
      flags: MessageFlags.Ephemeral,
    });
  }

  await acknowledgeAndEdit(interaction, {
    content:
      "✅ Équipes validées, envoi des **premiers matchs** dans les salons. Les capitaines cliqueront **Valider** à la fin.",
    embeds: [],
    components: [],
  });

  await sendRoundMatches(interaction.guild!, lobbyId, 0, lobby.channelId);
  await postLineupSummary(interaction.guild!, lobbyId, lobby.channelId);

  await prisma.lobby.update({
    where: { id: lobbyId },
    data: { state: "RUNNING", currentRound: 0 },
  });
}
