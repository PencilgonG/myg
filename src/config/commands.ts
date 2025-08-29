// src/config/commands.ts
import { SlashCommandBuilder } from 'discord.js';

export const lobbyCmd = new SlashCommandBuilder()
  .setName('lobby')
  .setDescription('Créer/configurer un lobby');

export const profileCmd = new SlashCommandBuilder()
  .setName('profile')
  .setDescription('Gérer ton profil')
  .addSubcommand((sub) =>
    sub.setName('set')
      .setDescription('Définir ou mettre à jour ton profil')
      .addStringOption(o => o.setName('summoner').setDescription('Pseudo LoL').setRequired(false))
      .addStringOption(o => o.setName('opgg').setDescription('Lien OP.GG').setRequired(false))
      .addStringOption(o => o.setName('dpm').setDescription('Lien DPM/Porofessor').setRequired(false))
  )
  .addSubcommand((sub) =>
    sub.setName('view')
      .setDescription('Voir un profil')
      .addUserOption(o => o.setName('user').setDescription('Membre (optionnel)').setRequired(false))
  );

export const allCommands = [lobbyCmd, profileCmd].map(c => c.toJSON());
