import type { Guild, PermissionResolvable } from 'discord.js';
import { ChannelType, PermissionsBitField } from 'discord.js';


export type TeamResource = {
roleId: string;
textChannelId: string;
voiceChannelId: string;
};


export async function ensureLobbyCategory(guild: Guild, name: string) {
const cat = await guild.channels.create({
name,
type: ChannelType.GuildCategory,
permissionOverwrites: [
{ id: guild.roles.everyone, deny: [PermissionsBitField.Flags.ViewChannel] }
]
});
return cat;
}


export async function createTeamResources(guild: Guild, categoryId: string, teamName: string, visibleRoleId?: string): Promise<TeamResource> {
const role = await guild.roles.create({ name: teamName, mentionable: false });


const overwrites = (extraAllow?: PermissionResolvable) => ([
{ id: guild.roles.everyone, deny: [PermissionsBitField.Flags.ViewChannel] },
{ id: role.id, allow: [
PermissionsBitField.Flags.ViewChannel,
PermissionsBitField.Flags.SendMessages,
PermissionsBitField.Flags.Connect,
PermissionsBitField.Flags.Speak,
PermissionsBitField.Flags.UseApplicationCommands,
extraAllow ?? []
].flat() },
...(visibleRoleId ? [{ id: visibleRoleId, allow: [PermissionsBitField.Flags.ViewChannel] }] : [])
] as any);


const text = await guild.channels.create({
name: teamName.toLowerCase().replace(/\s+/g, '-'),
type: ChannelType.GuildText,
parent: categoryId,
permissionOverwrites: overwrites(PermissionsBitField.Flags.ReadMessageHistory)
});


const voice = await guild.channels.create({
name: `${teamName} VC`,
type: ChannelType.GuildVoice,
parent: categoryId,
permissionOverwrites: overwrites()
});


return { roleId: role.id, textChannelId: text.id, voiceChannelId: voice.id };
}


export async function cleanupLobby(guild: Guild, roleIds: string[], channelIds: string[], categoryId?: string) {
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