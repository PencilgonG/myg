// src/index.ts
import "dotenv/config";
import {
  Client,
  GatewayIntentBits,
  Partials,
  Events,
  ActivityType,
} from "discord.js";

import { registerSlashCommands } from "./bot/interactions/register.js";
import {
  handleSlash,
  handleInteractionComponent,
} from "./bot/interactions/dispatcher.js";

// ───────────────────────────────── client ─────────────────────────────────
const client = new Client({
  intents: [
    GatewayIntentBits.Guilds,
    GatewayIntentBits.GuildMembers, // utile si tu lis des pseudos/roles
    GatewayIntentBits.GuildMessages,
  ],
  partials: [Partials.Channel],
});

// ─────────────────────────────── ready: register ───────────────────────────────
client.once(Events.ClientReady, async () => {
  try {
    const token = (process.env.DISCORD_TOKEN || "").trim();
    const guildId = process.env.GUILD_DEV_ID?.trim();
    const appId = client.application?.id;

    if (!appId) {
      console.error("❌ Application non prête (pas d'appId).");
      return;
    }

    await registerSlashCommands(appId, token, guildId);
    console.log(`✅ Connecté en tant que ${client.user?.tag}`);

    // petite présence
    client.user?.setPresence({
      activities: [{ name: "inhouse lobby", type: ActivityType.Watching }],
      status: "online",
    });
  } catch (err) {
    console.error("❌ Échec initialisation:", err);
  }
});

// ───────────────────────────── interactions ─────────────────────────────
client.on(Events.InteractionCreate, async (interaction) => {
  try {
    if (interaction.isChatInputCommand()) {
      return handleSlash(interaction);
    }
    if (
      interaction.isButton() ||
      interaction.isStringSelectMenu() ||
      interaction.isModalSubmit()
    ) {
      return handleInteractionComponent(interaction);
    }
  } catch (err) {
    console.error("Erreur durant InteractionCreate:", err);
    if (interaction.isRepliable()) {
      try {
        await interaction.reply({
          content: "❌ Une erreur est survenue.",
          ephemeral: true,
        });
      } catch {}
    }
  }
});

// ─────────────────────────────── login ───────────────────────────────
const raw = (process.env.DISCORD_TOKEN || "").trim();
if (!raw || raw.split(".").length !== 3) {
  console.error(
    "DISCORD_TOKEN manquant ou invalide. Assure-toi d'avoir .env avec DISCORD_TOKEN et GUILD_DEV_ID."
  );
  process.exit(1);
}

client.login(raw);
