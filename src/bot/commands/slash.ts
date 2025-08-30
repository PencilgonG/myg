// src/bot/commands/slash.ts
import { REST, Routes, SlashCommandBuilder } from "discord.js";

// /lobby
const lobbyCmd = new SlashCommandBuilder()
  .setName("lobby")
  .setDescription("Créer et gérer un lobby inhouse.");

// /profil
const profilCmd = new SlashCommandBuilder()
  .setName("profil")
  .setDescription("Gérer et afficher ton profil LoL.");

profilCmd.addSubcommand(sc =>
  sc.setName("set")
    .setDescription("Configurer/mettre à jour ton profil (opgg, dpm, elo, région, rôle principal).")
    .addStringOption(o => o.setName("summoner").setDescription("Riot ID (Nom#Tag)").setRequired(false))
    .addStringOption(o => o.setName("opgg").setDescription("Lien OP.GG").setRequired(false))
    .addStringOption(o => o.setName("dpm").setDescription("Lien DPM").setRequired(false))
    .addStringOption(o => o.setName("elo").setDescription("Ton elo (texte libre)").setRequired(false))
    .addStringOption(o => o.setName("region").setDescription("Région (euw, eun, na, ... )").setRequired(false))
    .addStringOption(o =>
      o.setName("mainrole")
        .setDescription("Rôle principal")
        .addChoices(
          { name: "TOP", value: "TOP" },
          { name: "JUNGLE", value: "JUNGLE" },
          { name: "MID", value: "MID" },
          { name: "ADC", value: "ADC" },
          { name: "SUPPORT", value: "SUPPORT" },
          { name: "FLEX", value: "FLEX" },
        )
        .setRequired(false),
    )
);

profilCmd.addSubcommand(sc =>
  sc.setName("view")
    .setDescription("Afficher un profil (par défaut le tien).")
    .addUserOption(o => o.setName("user").setDescription("Utilisateur cible").setRequired(false))
);

export const commandsJSON = [lobbyCmd, profilCmd].map(c => c.toJSON());

// call this from your setup script
export async function registerSlash(token: string, clientId: string, guildId?: string) {
  const rest = new REST({ version: "10" }).setToken(token);
  if (guildId) {
    await rest.put(Routes.applicationGuildCommands(clientId, guildId), { body: commandsJSON });
    console.log("Slash commands registered to DEV guild");
  } else {
    await rest.put(Routes.applicationCommands(clientId), { body: commandsJSON });
    console.log("Slash commands registered globally");
  }
}
