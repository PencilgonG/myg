// src/services/guild.ts
import type { Guild, CategoryChannel, TextChannel, VoiceChannel } from 'discord.js';
import { ChannelType, PermissionsBitField } from 'discord.js';

export type TeamResource = {
  roleId: string;
  textChannelId: string;
  voiceChannelId: string;
};

export async function ensureLobbyCategory(guild: Guild, name: string): Promise<CategoryChannel> {
  const cat = await guild.channels.create({
    name,
    type: ChannelType.GuildCategory,
    permissionOverwrites: [
      { id: guild.roles.everyone, deny: [PermissionsBitField.Flags.ViewChannel] }
    ]
  });
  return cat as CategoryChannel;
}

export async function ensureTeamResources(
  guild: Guild,
  categoryId: string,
  teamName: string
): Promise<TeamResource> {
  const role = await guild.roles.create({ name: teamName, mentionable: true });

  const text = await guild.channels.create({
    name: teamName.toLowerCase().replace(/\s+/g, '-'),
    type: ChannelType.GuildText,
    parent: categoryId,
    permissionOverwrites: [
      { id: guild.roles.everyone, deny: [PermissionsBitField.Flags.ViewChannel] },
      { id: role.id, allow: [PermissionsBitField.Flags.ViewChannel, PermissionsBitField.Flags.SendMessages] }
    ]
  });

  const voice = await guild.channels.create({
    name: teamName,
    type: ChannelType.GuildVoice,
    parent: categoryId,
    permissionOverwrites: [
      { id: guild.roles.everyone, deny: [PermissionsBitField.Flags.Connect, PermissionsBitField.Flags.ViewChannel] },
      { id: role.id, allow: [PermissionsBitField.Flags.Connect, PermissionsBitField.Flags.ViewChannel, PermissionsBitField.Flags.Speak] }
    ]
  });

  return {
    roleId: role.id,
    textChannelId: (text as TextChannel).id,
    voiceChannelId: (voice as VoiceChannel).id
  };
}

export async function cleanupLobby(
  guild: Guild,
  roleIds: string[],
  channelIds: string[],
  categoryId?: string
) {
  for (const chId of channelIds) {
    const ch = guild.channels.cache.get(chId);
    if (ch) await ch.delete().catch(() => {});
  }
  for (const roleId of roleIds) {
    const role = guild.roles.cache.get(roleId);
    if (role) await role.delete().catch(() => {});
  }
  if (categoryId) {
    const cat = guild.channels.cache.get(categoryId);
    if (cat) await cat.delete().catch(() => {});
  }
}
