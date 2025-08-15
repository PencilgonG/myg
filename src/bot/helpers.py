# src/bot/helpers.py
import discord

async def safe_defer(interaction: discord.Interaction, *, update: bool = False) -> None:
    """Acquitte TOUJOURS l'interaction sans lever.
    - update=True => defer_update() si possible (pour edit du message).
    - sinon => defer() standard.
    """
    try:
        if interaction.response.is_done():
            return
        if update and getattr(interaction, "message", None) is not None:
            await interaction.response.defer_update()
        else:
            await interaction.response.defer()
    except Exception:
        # on ignore totalement (mieux vaut avoir déjà acquitté ailleurs)
        pass


async def first_response_or_followup(
    interaction: discord.Interaction,
    *,
    content: str | None = None,
    embed: discord.Embed | None = None,
    view: discord.ui.View | None = None,
    ephemeral: bool = False,
):
    """Envoie une réponse même si l'interaction a déjà été acquittée.
    - Si response pas fait -> send_message
    - Sinon -> followup.send
    - Si le followup échoue (Unknown Webhook), fallback en channel.send (non éphémère).
    """
    try:
        if not interaction.response.is_done():
            return await interaction.response.send_message(
                content=content, embed=embed, view=view, ephemeral=ephemeral
            )
        try:
            return await interaction.followup.send(
                content=content, embed=embed, view=view, ephemeral=ephemeral
            )
        except discord.NotFound:
            # Webhook inconnu (message trop ancien, etc.) -> on envoie dans le salon
            if interaction.channel:
                return await interaction.channel.send(content=content, embed=embed, view=view)
    except Exception:
        # on n'échoue jamais pour ne pas faire apparaître la bannière rouge
        pass
