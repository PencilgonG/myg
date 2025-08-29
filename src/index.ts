// src/index.ts
import dotenv from 'dotenv';
dotenv.config({ override: true }); // force .env to remplacer les variables d'env existantes

import { Client, GatewayIntentBits, Partials, Events, ActivityType } from 'discord.js';
import pino from 'pino';

const log = pino({ level: process.env.LOG_LEVEL || 'info' });

const TOKEN = process.env.DISCORD_TOKEN;
if (!TOKEN) {
  log.error('DISCORD_TOKEN manquant dans .env');
  process.exit(1);
}

const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMembers,
    GatewayIntentBits.GuildMessages,
    GatewayIntentBits.MessageContent,
    GatewayIntentBits.GuildVoiceStates
  ],
  partials: [Partials.Channel, Partials.GuildMember, Partials.Message, Partials.Reaction, Partials.User]
});

async function loadDispatcher() {
  try {
    const mod = await import('./bot/interactions/dispatcher.ts');
    const fn = (mod as any).dispatch;
    if (typeof fn === 'function') return fn as (i: any) => Promise<void>;
  } catch (e) {
    log.warn('Dispatcher non trouvé (src/bot/interactions/dispatcher.ts). Le bot démarre sans routage d’interactions.');
  }
  return null;
}
const dispatcherPromise = loadDispatcher();

client.once(Events.ClientReady, (c) => {
  log.info({ tag: 'bot' }, `Logged in as ${c.user.tag}`);
  c.user.setPresence({
    activities: [{ name: '/lobby • /profile', type: ActivityType.Playing }],
    status: 'online'
  });
  (async () => {
    try {
      const mod = await import('./ready.ts');
      if (typeof (mod as any).onReady === 'function') {
        await (mod as any).onReady(client);
      }
    } catch {}
  })();
});

client.on(Events.InteractionCreate, async (interaction) => {
  const dispatch = await dispatcherPromise;
  if (dispatch) {
    try {
      await dispatch(interaction);
    } catch (err: any) {
      const msg = err?.message || 'Erreur inconnue';
      log.error({ err: String(err) }, 'Erreur dans le dispatcher');
      if (interaction.isRepliable?.()) {
        const payload = { content: `❌ ${msg}`, flags: 64 } as any;
        try { await (interaction as any).reply(payload); }
        catch { try { await (interaction as any).editReply?.(payload); } catch {} }
      }
    }
  } else if (interaction.isChatInputCommand?.()) {
    try { await (interaction as any).reply({ content: '⚠️ Commandes non routées (dispatcher manquant).', flags: 64 }); } catch {}
  }
});

client.login(TOKEN);
