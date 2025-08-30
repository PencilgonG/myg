import { SlashCommandBuilder } from "discord.js";

export const allCommands = [
  // ... tes autres commandes

  new SlashCommandBuilder()
    .setName("profil")
    .setDescription("Gérer ton profil joueur")
    .addSubcommand(sub =>
      sub.setName("set")
        .setDescription("Configurer ton profil")
        .addStringOption(o => o.setName("pseudo").setDescription("Pseudo LoL (Nom#Tag)").setRequired(true))
        .addStringOption(o => o.setName("role").setDescription("Rôle principal").setRequired(true)
          .addChoices(
            { name: "Top", value: "TOP" },
            { name: "Jungle", value: "JUNGLE" },
            { name: "Mid", value: "MID" },
            { name: "ADC", value: "ADC" },
            { name: "Support", value: "SUPPORT" },
            { name: "Flex", value: "FLEX" },
          ))
        .addStringOption(o => o.setName("elo").setDescription("Elo (ex: Emerald 3)"))
        .addStringOption(o => o.setName("opgg").setDescription("Lien OP.GG (facultatif)"))
        .addStringOption(o => o.setName("dpm").setDescription("Lien DPM (facultatif)"))
    )
    .addSubcommand(sub =>
      sub.setName("view")
        .setDescription("Voir un profil")
        .addUserOption(o => o.setName("user").setDescription("Joueur à afficher"))
    )
].map(c => c.toJSON());
