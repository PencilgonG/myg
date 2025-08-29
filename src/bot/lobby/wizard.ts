// BOT: src/bot/lobby/wizard.ts
// (version complète avec routage du bouton "draft:remake")
import type { ButtonInteraction, ModalSubmitInteraction, StringSelectMenuInteraction, MessageEditOptions } from 'discord.js';
import { ButtonStyle, MessageFlags } from 'discord.js';
import { prisma } from '../../infra/prisma.ts';
import { IDS } from '../interactions/ids.ts';
import { modalLobbyConfig } from '../../components/modals.ts';
import { baseEmbed } from '../../components/embeds.ts';
import { row, btn } from '../../components/buttons.ts';
import { selectMenu } from '../../components/selects.ts';
import { GameMode, RoleName, rosterSizeFor } from '../../domain/types.ts';
import { parseScheduleFormat } from './schedule.ts';
import { sendRoundMatches, onMatchValidated } from './matches.ts';
import { onDraftRemakeButton } from './matches.ts';

function toGameMode(input: string): GameMode {
  const s = input.toLowerCase();
  if (s.includes('aram')) return GameMode.ARAM;
  if (s.includes('tft')) return GameMode.TFT;
  if (s.includes('4v4')) return GameMode.SR_4v4;
  if (s.includes('3v3')) return GameMode.SR_3v3;
  if (s.includes('2v2')) return GameMode.SR_2v2;
  if (s.includes('1v1')) return GameMode.SR_1v1;
  return GameMode.SR_5v5;
}
function modeLabel(m: GameMode): string {
  return { SR_5v5: '5v5', SR_4v4: '4v4', SR_3v3: '3v3', SR_2v2: '2v2', SR_1v1: '1v1', ARAM: 'ARAM', TFT: 'TFT' }[m];
}
async function acknowledgeAndEdit(interaction: ButtonInteraction, payload: MessageEditOptions) {
  if (!interaction.deferred && !interaction.replied) await interaction.deferUpdate().catch(() => {});
  return (interaction.message as any).edit(payload);
}
async function editLobbyMessageFromModal(interaction: ModalSubmitInteraction, lobbyId: string, payload: MessageEditOptions) {
  const lobby = await prisma.lobby.findUnique({ where: { id: lobbyId } });
  if (!lobby?.messageId) return;
  const ch = await interaction.client.channels.fetch(lobby.channelId).catch(() => null) as any;
  if (!ch || !ch.isTextBased?.()) return;
  const msg = await ch.messages.fetch(lobby.messageId).catch(() => null);
  if (msg) await msg.edit(payload).catch(() => {});
}

export async function handleLobbyButtons(interaction: ButtonInteraction) {
  const id = interaction.customId;
  if (!id.includes(':')) return;

  if (id.startsWith('lobby:config:'))  return interaction.showModal(modalLobbyConfig(`modal:lobby:${id.split(':')[2]}`));
  if (id.startsWith('lobby:test:'))    return testFill(interaction, id.split(':')[2]);
  if (id.startsWith('lobby:validate:'))return renderPlayersEmbed(interaction, id.split(':')[2]);
  if (id.startsWith('lobby:gotoPick:'))return openPick(interaction, id.split(':')[2], 1);
  if (id.startsWith('pick:page:'))     return openPick(interaction, id.split(':')[2], Number(id.split(':')[3]));
  if (id.startsWith('pick:prev:'))     return openPick(interaction, id.split(':')[2], Math.max(1, Number(id.split(':')[3]) - 1));
  if (id.startsWith('pick:next:')) {
    const [, , lobbyId, page] = id.split(':');
    const lobby = await prisma.lobby.findUniqueOrThrow({ where: { id: lobbyId } });
    return openPick(interaction, lobbyId, Math.min(lobby.slots, Number(page) + 1));
  }
  if (id.startsWith('pick:validate:')) return validateTeams(interaction, id.split(':')[2]);
  if (id.startsWith('pick:schedule:')) return openScheduleModal(interaction, id.split(':')[2]);
  if (id.startsWith('match:validate:'))return onMatchValidated(interaction, id.split(':')[2]);

  // nouveau: relance draft
  if (id.startsWith('draft:remake:'))  return onDraftRemakeButton(interaction, id.split(':')[2]);
}

export async function handleLobbySelects(interaction: StringSelectMenuInteraction) {
  const id = interaction.customId;

  if (id.startsWith('select:captain:')) {
    const [, , lobbyId, teamNo] = id.split(':');
    const userId = interaction.values[0];

    await prisma.lobbyParticipant.updateMany({
      where: { lobbyId, userId },
      data: { isCaptain: true, teamNumber: Number(teamNo) }
    });
    await prisma.team.upsert({
      where: { lobbyId_number: { lobbyId, number: Number(teamNo) } },
      create: { lobbyId, number: Number(teamNo), name: `Équipe ${teamNo}` },
      update: {}
    });

    await interaction.update({ content: `✅ Capitaine pour l'équipe ${teamNo} : <@${userId}>`, components: [], embeds: [] });
    const payload = await buildPickPayload(lobbyId, Number(teamNo));
    return (interaction.message as any).edit(payload);
  }

  if (id.startsWith('select:players:')) {
    const [, , lobbyId, teamNo] = id.split(':');
    const members = interaction.values;

    await prisma.lobbyParticipant.updateMany({
      where: { lobbyId, userId: { in: members } },
      data: { teamNumber: Number(teamNo) }
    });

    await interaction.update({ content: `✅ Joueurs assignés à l'équipe ${teamNo}.`, components: [], embeds: [] });
    const payload = await buildPickPayload(lobbyId, Number(teamNo));
    return (interaction.message as any).edit(payload);
  }
}

export async function handleLobbyModal(interaction: ModalSubmitInteraction) {
  if (interaction.customId.startsWith('modal:lobby:')) {
    const lobbyId = interaction.customId.split(':')[2];

    const name = interaction.fields.getTextInputValue('name');
    const slots = Math.max(2, Math.min(16, Number.parseInt(interaction.fields.getTextInputValue('slots'), 10) || 2));
    const mode = toGameMode(interaction.fields.getTextInputValue('mode'));

    const lobby = await prisma.lobby.update({ where: { id: lobbyId }, data: { name, slots, mode, state: 'CONFIGURED' } });

    const embed = baseEmbed('Créer un lobby', 'Configuration mise à jour. Clique sur **Valider** pour continuer.')
      .addFields(
        { name: 'Nom', value: lobby.name, inline: true },
        { name: 'Slots (équipes)', value: String(lobby.slots), inline: true },
        { name: 'Mode', value: modeLabel(lobby.mode), inline: true }
      );
    const components = [row(
      btn(IDS.lobby.openConfig(lobby.id), 'Configurer'),
      btn(IDS.lobby.testFill(lobby.id), 'Test'),
      btn(IDS.lobby.validate(lobby.id), 'Valider', ButtonStyle.Success)
    )];

    await editLobbyMessageFromModal(interaction, lobbyId, { embeds: [embed], components });
    return interaction.reply({ content: '✅ Configuration mise à jour.', flags: MessageFlags.Ephemeral });
  }

  if (interaction.customId.startsWith('modal:schedule:')) {
    const lobbyId = interaction.customId.split(':')[2];
    await interaction.deferReply({ flags: MessageFlags.Ephemeral }).catch(() => {});

    const raw = interaction.fields.getTextInputValue('format');
    const lobby = await prisma.lobby.findUniqueOrThrow({ where: { id: lobbyId } });
    const rounds = parseScheduleFormat(raw, lobby.slots);

    await prisma.match.deleteMany({ where: { lobbyId } });

    let roundIdx = 0;
    for (const r of rounds) {
      let idx = 0;
      for (const p of r) {
        const blue = Math.random() < 0.5 ? p.a : p.b;
        const red  = blue === p.a ? p.b : p.a;

        const teamBlue = await prisma.team.upsert({
          where: { lobbyId_number: { lobbyId, number: blue } },
          create: { lobbyId, number: blue, name: `Équipe ${blue}` },
          update: {}
        });
        const teamRed = await prisma.team.upsert({
          where: { lobbyId_number: { lobbyId, number: red } },
          create: { lobbyId, number: red, name: `Équipe ${red}` },
          update: {}
        });

        await prisma.match.create({
          data: {
            lobbyId,
            round: roundIdx,
            indexInRound: idx++,
            blueTeamId: teamBlue.id,
            redTeamId: teamRed.id,
            draftBlueUrl: null,
            draftRedUrl: null,
            specUrl: null,
            state: 'PENDING'
          }
        });
      }
      roundIdx++;
    }

    await prisma.lobby.update({ where: { id: lobbyId }, data: { state: 'SCHEDULED', currentRound: 0 } });

    const summary = baseEmbed('Planning enregistré', `**${rounds.length}** rounds configurés. Clique **Valider** pour créer les salons & rôles et démarrer.`);
    const components = [row(
      btn(IDS.lobby.pickSchedule(lobbyId), 'Replanifier'),
      btn(IDS.lobby.pickValidate(lobbyId), 'Valider', ButtonStyle.Success)
    )];

    await editLobbyMessageFromModal(interaction, lobbyId, { embeds: [summary], components });
    return interaction.editReply({ content: '✅ Planning enregistré.' });
  }
}

async function renderPlayersEmbed(interaction: ButtonInteraction, lobbyId: string) {
  const lobby = await prisma.lobby.update({ where: { id: lobbyId }, data: { state: 'PICKING' } });
  const participants = await prisma.lobbyParticipant.findMany({ where: { lobbyId }, include: { profile: true } });

  const playerLines = participants.map((p) => {
    const links: string[] = [];
    if (p.profile?.opggUrl) links.push(`[OP.GG](${p.profile.opggUrl})`);
    if (p.profile?.dpmUrl)  links.push(`[DPM](${p.profile.dpmUrl})`);
    const linksStr = links.length ? ` — ${links.join(' | ')}` : '';
    return `• <@${p.userId}> (${p.selectedRole ?? '—'})${linksStr}`;
  });

  const embed = baseEmbed(`Lobby: ${lobby.name}`, `Mode: **${modeLabel(lobby.mode)}** — Équipes: **${lobby.slots}**\n\n**Joueurs**\n${playerLines.join('\n') || '*Aucun joueur*'}`);
  const components = [row(btn(IDS.lobby.gotoPick(lobby.id), 'Pick teams', ButtonStyle.Primary))];

  return acknowledgeAndEdit(interaction, { embeds: [embed], components });
}

async function buildPickPayload(lobbyId: string, teamNo: number): Promise<MessageEditOptions> {
  const lobby = await prisma.lobby.findUniqueOrThrow({ where: { id: lobbyId } });

  for (let i = 1; i <= lobby.slots; i++) {
    await prisma.team.upsert({
      where: { lobbyId_number: { lobbyId, number: i } },
      create: { lobbyId, number: i, name: `Équipe ${i}` },
      update: {}
    });
  }

  const team = await prisma.team.findUniqueOrThrow({ where: { lobbyId_number: { lobbyId, number: teamNo } } });
  const participants = await prisma.lobbyParticipant.findMany({ where: { lobbyId }, include: { profile: true }, orderBy: { userId: 'asc' } });
  const rosterSize = rosterSizeFor(lobby.mode);

  const currentMembers = participants.filter((p) => p.teamNumber === teamNo);
  const captain = participants.find((p) => p.isCaptain && p.teamNumber === teamNo);

  const descLines: string[] = [
    `Équipe **${team.number}** — ${team.name}`,
    `Capitaine: ${captain ? `<@${captain.userId}>` : '*Non défini*'}`,
    `Joueurs (${currentMembers.length}/${rosterSize}):`,
    ...currentMembers.map((p) => `• <@${p.userId}>`)
  ];

  const embed = baseEmbed(`Pick teams • ${lobby.name}`, descLines.join('\n'));

  const optionsAll = participants.map((p) => ({
    label: p.profile?.summonerName ?? p.userId,
    value: p.userId,
    description: p.profile?.preferredRoles?.join(', ') || '—'
  }));

  const navRow = row(
    btn(IDS.lobby.pickPrev(lobbyId, teamNo), '← Précédent'),
    btn(IDS.lobby.pickNext(lobbyId, teamNo), 'Suivant →')
  );
  const actionsRow = row(
    btn(IDS.lobby.pickSchedule(lobbyId), 'Sélectionner matchs'),
    btn(IDS.lobby.pickValidate(lobbyId), 'Valider', ButtonStyle.Success)
  );

  const menus = [
    selectMenu(IDS.lobby.selectCaptain(lobbyId, teamNo), 'Capitaine', optionsAll, 1, 1),
    selectMenu(IDS.lobby.selectPlayers(lobbyId, teamNo), 'Joueurs (multi)', optionsAll, 1, rosterSize)
  ];

  return { embeds: [embed], components: [...menus, navRow, actionsRow] as any };
}

async function openPick(interaction: ButtonInteraction, lobbyId: string, teamNo: number) {
  const payload = await buildPickPayload(lobbyId, teamNo);
  return acknowledgeAndEdit(interaction, payload);
}

async function validateTeams(interaction: ButtonInteraction, lobbyId: string) {
  const lobby = await prisma.lobby.findUniqueOrThrow({ where: { id: lobbyId } });
  const rosterSize = rosterSizeFor(lobby.mode);
  const teams = await prisma.team.findMany({ where: { lobbyId }, orderBy: { number: 'asc' } });
  const parts = await prisma.lobbyParticipant.findMany({ where: { lobbyId } });

  for (const t of teams) {
    const roster = parts.filter((p) => p.teamNumber === t.number);
    if (roster.length < rosterSize) return interaction.reply({ content: `❌ L'équipe ${t.number} n'a pas assez de joueurs (${roster.length}/${rosterSize}).`, flags: MessageFlags.Ephemeral });
    const hasCap = parts.some((p) => p.teamNumber === t.number && p.isCaptain);
    if (!hasCap) return interaction.reply({ content: `❌ L'équipe ${t.number} n'a pas de capitaine.`, flags: MessageFlags.Ephemeral });
  }

  const guild = interaction.guild!;
  const categoryName = `${process.env.DEFAULT_CATEGORY_PREFIX || 'Inhouse -'}${lobby.name}`;
  const { ensureLobbyCategory, createTeamResources } = await import('../../services/guild.ts');
  const category = await ensureLobbyCategory(guild, categoryName);

  const newTeams = [] as { id: string; roleId: string; textChannelId: string; voiceChannelId: string }[];
  for (const t of teams) {
    const res = await createTeamResources(guild, category.id, t.name);
    newTeams.push({ id: t.id, ...res });
    await prisma.team.update({ where: { id: t.id }, data: { roleId: res.roleId, textChannelId: res.textChannelId, voiceChannelId: res.voiceChannelId } });
  }
  await prisma.lobby.update({ where: { id: lobbyId }, data: { categoryId: category.id } });

  for (const p of parts) {
    if (p.teamNumber) {
      const t = newTeams.find((nt) => nt.id === teams.find((x) => x.number === p.teamNumber)?.id);
      if (t?.roleId) {
        const member = await guild.members.fetch(p.userId).catch(() => null);
        if (member) await member.roles.add(t.roleId).catch(() => {});
      }
    }
  }

  const matchesCount = await prisma.match.count({ where: { lobbyId } });
  if (matchesCount === 0) return interaction.reply({ content: '✅ Équipes validées. Configure le planning avec **Sélectionner matchs**.', flags: MessageFlags.Ephemeral });

  await acknowledgeAndEdit(interaction, { content: '✅ Équipes validées. Les premiers matchs vont être envoyés.', embeds: [], components: [] });
  await sendRoundMatches(guild, lobbyId, 0, lobby.channelId);
  await prisma.lobby.update({ where: { id: lobbyId }, data: { state: 'RUNNING', currentRound: 0 } });
}

async function openScheduleModal(interaction: ButtonInteraction, lobbyId: string) {
  const { ModalBuilder, TextInputBuilder, TextInputStyle, ActionRowBuilder } = await import('discord.js');
  const modal = new ModalBuilder().setCustomId(IDS.lobby.scheduleModal(lobbyId)).setTitle('Planning des matchs');
  const format = new TextInputBuilder()
    .setCustomId('format')
    .setLabel('Format (ex: 1-2,3-4 | 1-3,2-4)')
    .setStyle(TextInputStyle.Paragraph)
    .setRequired(true)
    .setValue('1-2,3-4 | 1-3,2-4 | 1-4,2-3');
  modal.addComponents(new ActionRowBuilder<TextInputBuilder>().addComponents(format));
  await interaction.showModal(modal);
}

async function testFill(interaction: ButtonInteraction, lobbyId: string) {
  const lobby = await prisma.lobby.findUniqueOrThrow({ where: { id: lobbyId } });
  const roster = rosterSizeFor(lobby.mode);
  const needs = lobby.slots * roster;

  const tx: any[] = [];
  for (let i = 0; i < needs; i++) {
    const userId = `9999${i.toString().padStart(6, '0')}`;
    tx.push(
      prisma.userProfile.upsert({
        where: { discordUserId: userId },
        create: { discordUserId: userId, summonerName: `Fake${i}`, preferredRoles: ['FLEX'] as any, opggUrl: `https://op.gg/summoners/euw/Fake${i}`, dpmUrl: `https://example.com/dpm/Fake${i}` },
        update: {}
      })
    );
    tx.push(
      prisma.lobbyParticipant.upsert({
        where: { lobbyId_userId: { lobbyId, userId } },
        create: { lobbyId, userId, selectedRole: 'FLEX' as any },
        update: {}
      })
    );
  }
  await prisma.$transaction(tx);
  await interaction.reply({ content: `✅ Test: ${needs} faux joueurs ajoutés.`, flags: MessageFlags.Ephemeral });
}

function nextRole(current?: RoleName | null): RoleName {
  const order = [RoleName.TOP, RoleName.JUNGLE, RoleName.MID, RoleName.ADC, RoleName.SUPPORT, RoleName.FLEX];
  const i = current ? order.indexOf(current) : -1;
  return order[(i + 1) % order.length];
}
