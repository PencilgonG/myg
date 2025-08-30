// src/ready.ts
import { Client, REST, Routes } from 'discord.js';
import pino from 'pino';
import { allCommands } from './config/commands.ts';

const log = pino({ level: process.env.LOG_LEVEL || 'info' });

export async function onReady(client: Client) {
  const token = process.env.DISCORD_TOKEN!;
  const appId = process.env.DISCORD_CLIENT_ID!;
  const devGuildId = process.env.DEV_GUILD_ID;

  const rest = new REST({ version: '10' }).setToken(token);

  if (devGuildId) {
    await rest.put(Routes.applicationGuildCommands(appId, devGuildId), { body: allCommands });
    log.info('Slash commands registered to DEV guild');
  } else {
    await rest.put(Routes.applicationCommands(appId), { body: allCommands });
    log.info('Slash commands registered globally');
  }
}
