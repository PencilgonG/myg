// src/bot/interactions/register.ts

/**
 * Enregistre /lobby et /profil (set/view) dans le GUILD_DEV_ID.
 * Utilise le token bot pour appeler l'API Discord.
 */
export async function registerSlashCommands(
  applicationId: string,
  botToken: string,
  guildId?: string | null
) {
  if (!botToken) throw new Error("Bot token manquant.");
  if (!guildId) throw new Error("GUILD_DEV_ID manquant.");

  const url = `https://discord.com/api/v10/applications/${applicationId}/guilds/${guildId}/commands`;

  const body = [
    // /lobby
    {
      name: "lobby",
      description: "Créer et gérer un lobby d'inhouse",
      type: 1, // CHAT_INPUT
    },
    // /profil
    {
      name: "profil",
      description: "Gérer ton profil joueur",
      type: 1,
      options: [
        {
          type: 1, // SUBCOMMAND
          name: "set",
          description: "Définir/mettre à jour ton profil",
          options: [
            {
              type: 3, // STRING
              name: "summoner",
              description: "Pseudo LoL (Nom#Tag)",
              required: false,
            },
            {
              type: 3, // STRING
              name: "mainrole",
              description: "Rôle principal",
              required: false,
              choices: [
                { name: "TOP", value: "TOP" },
                { name: "JUNGLE", value: "JUNGLE" },
                { name: "MID", value: "MID" },
                { name: "ADC", value: "ADC" },
                { name: "SUPPORT", value: "SUPPORT" },
                { name: "FLEX", value: "FLEX" },
              ],
            },
            {
              type: 3, // STRING
              name: "opgg",
              description: "Lien OP.GG",
              required: false,
            },
            {
              type: 3, // STRING
              name: "dpm",
              description: "Lien DPM",
              required: false,
            },
            // 👇 NOUVEAU : region
            {
              type: 3, // STRING
              name: "region",
              description: "Serveur LoL (EUW/EUNE/NA/KR/...)",
              required: false,
              choices: [
                { name: "EUW", value: "EUW" },
                { name: "EUNE", value: "EUNE" },
                { name: "NA", value: "NA" },
                { name: "KR", value: "KR" },
                { name: "JP", value: "JP" },
                { name: "OCE", value: "OCE" },
                { name: "BR", value: "BR" },
                { name: "LAN", value: "LAN" },
                { name: "LAS", value: "LAS" },
                { name: "TR", value: "TR" },
                { name: "RU", value: "RU" },
              ],
            },
          ],
        },
        {
          type: 1, // SUBCOMMAND
          name: "view",
          description: "Afficher ton profil",
        },
      ],
    },
  ];

  const resp = await fetch(url, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bot ${botToken}`,
    },
    body: JSON.stringify(body),
  });

  if (!resp.ok) {
    const txt = await resp.text();
    throw new Error(`Register slash failed: ${resp.status} ${txt}`);
  }
}
