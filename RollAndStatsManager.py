import discord
from discord import app_commands, ui
from discord.ext import commands
import io
import asyncio
import os
from flask import Flask
from threading import Thread

# ==========================================
# ⚙️ MINI WEB SZERVER AZ ÉBREN TARTÁSHOZ
# ==========================================
app = Flask('')

@app.route('/')
def home():
    return "A bot online!"

def run_web():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web)
    t.start()
# ==========================================

# ==========================================
# ⚙️ BEÁLLÍTÁSOK ÉS MINTÁK (AUTÓKER TICKETEKhEZ)
# ==========================================
ELADO_CHANNEL_ID = 1551543012956438609
KERESEK_CHANNEL_ID = 1551542857129660458
TICKET_CATEGORY_ID = 0

MINTA_ELADO = """Autó neve: xxx.xxx.xxx
Autó irányára: xxx.xxx.xxx $
Autó ár alja: xxx.xxx.xxx $
Telefonszám:"""

MINTA_KERESEK = """Keresett autó neve: xxx.xxx.xxx
Ajánlott keret: xxx.xxx.xxx $
Elvárt felszereltség / tuningok: xxx
Telefonszám:"""

# ==========================================
# ⚙️ ÚJ: BEÁLLÍTÁSOK (SEGÍTSÉGKÉRŐ TICKET)
# ==========================================
# Cseréld ki a 0-kat a megfelelő ID-kre!
HELP_TICKET_CATEGORY_ID = 0  # Ide nyílnak majd a segítség ticketek
MODERATOR_ROLE_ID = 0        # Aki ezt a rangot viseli, az látja a segítség ticketeket és le tudja zárni

# ==========================================
# ⚙️ BEÁLLÍTÁSOK (RANGOK ÉS SZABÁLYZAT)
# ==========================================
UJONC_ROLE_ID = 1551551419113541692
TAG_ROLE_ID = 1551605958927589407
SZABALYZAT_MESSAGE_ID = 1551604413066387619
# ==========================================

# -----------------------------------------------------
# AUTÓKERESKEDÉS TICKET RENDSZER (EREDETI)
# -----------------------------------------------------
class TicketControlView(ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=None)
        self.user_id = user_id

    async def process_submission(self, interaction: discord.Interaction, ticket_type: str):
        if interaction.user.id != self.user_id and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("Ezt a gombot csak az használhatja, aki a ticketet nyitotta!", ephemeral=True)
            return

        await interaction.response.defer()
        
        messages = [msg async for msg in interaction.channel.history(limit=30, oldest_first=True)]
        user_messages = [m for m in messages if m.author.id == self.user_id]

        if not user_messages:
            await interaction.followup.send("❌ Még nem írtál semmit! Kérlek töltsd ki a mintát, és csatolj képeket, mielőtt beküldöd.", ephemeral=True)
            return

        full_text = "\n".join([m.content for m in user_messages if m.content])
        attachments = []
        for m in user_messages:
            attachments.extend(m.attachments)

        if len(attachments) > 5:
            await interaction.followup.send("❌ Maximum 5 képet csatolhatsz! Kérlek törölj párat a chatből, majd nyomj újra a Beküldésre.", ephemeral=True)
            return

        target_id = ELADO_CHANNEL_ID if ticket_type == "elado" else KERESEK_CHANNEL_ID
        target_channel = interaction.guild.get_channel(target_id) or interaction.guild.get_thread(target_id)
        
        if not target_channel:
            await interaction.followup.send("❌ Hiba: A hirdetőcsatorna nem található. Szólj egy adminnak!", ephemeral=True)
            return

        color = discord.Color.green() if ticket_type == "elado" else discord.Color.blue()
        type_label = "🚗 ELADÓ JÁRMŰ" if ticket_type == "elado" else "🔍 JÁRMŰVET KERESEK"

        embed = discord.Embed(
            title=type_label,
            description=full_text if full_text else "Nincs további leírás megadva.",
            color=color,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(name="👤 Hirdető", value=interaction.user.mention, inline=False)
        embed.set_footer(text="HLV3 Autókereskedés Ticket System")

        files = []
        for att in attachments:
            file_bytes = await att.read()
            files.append(discord.File(fp=io.BytesIO(file_bytes), filename=att.filename))

        await target_channel.send(embed=embed, files=files)
        
        await interaction.followup.send("✅ Sikeres beküldés! A ticket 3 másodperc múlva törlődik.")
        await asyncio.sleep(3)
        await interaction.channel.delete(reason="Hirdetés beküldve a bot által")

    @ui.button(label="🚗 Eladás Beküldése", style=discord.ButtonStyle.success, custom_id="btn_submit_elado")
    async def btn_elado(self, interaction: discord.Interaction, button: ui.Button):
        await self.process_submission(interaction, "elado")

    @ui.button(label="🔍 Vásárlás Beküldése", style=discord.ButtonStyle.primary, custom_id="btn_submit_keresek")
    async def btn_vasarlas(self, interaction: discord.Interaction, button: ui.Button):
        await self.process_submission(interaction, "keresek")

class TicketPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🎫 Hirdetés feladása (Ticket nyitása)", style=discord.ButtonStyle.secondary, custom_id="btn_open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: ui.Button):
        guild = interaction.guild
        user = interaction.user
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }

        category = guild.get_channel(TICKET_CATEGORY_ID) if TICKET_CATEGORY_ID != 0 else interaction.channel.category
        
        try:
            ticket_channel = await guild.create_text_channel(
                name=f"hirdetés-{user.name}",
                category=category,
                overwrites=overwrites,
                reason="Autókereskedés Ticket nyitása"
            )
        except Exception as e:
            await interaction.response.send_message("❌ Nem sikerült létrehozni a szobát. Biztos van a botnak Csatornák Kezelése joga?", ephemeral=True)
            return

        await interaction.response.send_message(f"✅ Ticket megnyitva itt: {ticket_channel.mention}", ephemeral=True)
        
        minta_szoveg = (
            f"Üdvözöllek, {user.mention}!\n\n"
            "**Kérlek, az alábbi MINTA alapján írd meg az üzenetedet ide a szobába:**\n"
            "*(Ha eladásról vagy vételről van szó, írd át/töltsd ki ennek megfelelően)*\n\n"
            "**--- ELADÁSI MINTA ---**\n"
            f"```text\n{MINTA_ELADO}\n```\n"
            "**--- VÉTELI MINTA ---**\n"
            f"```text\n{MINTA_KERESEK}\n```\n\n"
            "**Fontos szabályok:**\n"
            "• Maximum **5 képet** csatolhatsz (a tuningokról szóló kép is beleszámít).\n"
            "• Ha mindent beírtál és feltöltöttél, **válaszd ki az alábbi gombok egyikét**, hogy hova szeretnéd beküldeni a hirdetést!\n"
        )
        
        await ticket_channel.send(minta_szoveg, view=TicketControlView(user_id=user.id))

# -----------------------------------------------------
# ÚJ: SEGÍTSÉGKÉRŐ TICKET RENDSZER
# -----------------------------------------------------
class HelpTicketControlView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="🔒 Ticket Lezárása", style=discord.ButtonStyle.danger, custom_id="btn_close_help_ticket")
    async def close_help_ticket(self, interaction: discord.Interaction, button: ui.Button):
        # Csak az zárhatja be, aki moderátor, vagy akinek van csatornakezelési joga
        moderator_role = interaction.guild.get_role(MODERATOR_ROLE_ID)
        is_mod = (moderator_role in interaction.user.roles) if moderator_role else False
        has_perms = interaction.user.guild_permissions.manage_channels

        if not (is_mod or has_perms):
            await interaction.response.send_message("❌ Ezt a gombot csak a vezetőség használhatja!", ephemeral=True)
            return

        await interaction.response.send_message("✅ A ticket lezárásra került. A szoba 5 másodperc múlva törlődik...")
        await asyncio.sleep(5)
        await interaction.channel.delete(reason="Segítségkérő ticket lezárva a moderátor által")


class HelpTicketPanelView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="📩 Segítségkérés (Ticket Nyitása)", style=discord.ButtonStyle.primary, custom_id="btn_open_help_ticket")
    async def open_help_ticket(self, interaction: discord.Interaction, button: ui.Button):
        # ELŐRE JELEZZÜK A DISCORDNAK, HOGY FOLYAMATBAN VAN (Megelőzi az időtúllépési hibát)
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        user = interaction.user
        
        # Alap jogosultságok: mindenki elől elrejtve, a nyitónak és a botnak látható
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, read_message_history=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }

        # Ha be van állítva moderátor rang, ők is látni fogják
        moderator_role = guild.get_role(MODERATOR_ROLE_ID)
        if moderator_role:
            overwrites[moderator_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True)

        category = guild.get_channel(HELP_TICKET_CATEGORY_ID) if HELP_TICKET_CATEGORY_ID != 0 else interaction.channel.category
        
        try:
            ticket_channel = await guild.create_text_channel(
                name=f"ticket-{user.name}",
                category=category,
                overwrites=overwrites,
                reason="Segítségkérő ticket nyitása"
            )
        except Exception as e:
            await interaction.followup.send("❌ Nem sikerült létrehozni a szobát. Biztos van a botnak Csatornák Kezelése joga?", ephemeral=True)
            return

        await interaction.followup.send(f"✅ Segítségkérő ticket megnyitva itt: {ticket_channel.mention}", ephemeral=True)
        
        embed = discord.Embed(
            title="🛠️ Segítségkérés",
            description=(
                f"Üdvözöllek {user.mention}!\n\n"
                "Kérlek, írd le ide részletesen a problémádat vagy kérdésedet. A vezetőség (moderátorok/tulajdonosok) amint tudnak, válaszolni fognak neked ebben a szobában.\n\n"
                "*(Ezt a szobát csak te és a vezetőség látja. Amikor a probléma megoldódott, a vezetőség fogja lezárni a lenti gombbal.)*"
            ),
            color=discord.Color.blue()
        )
        
        await ticket_channel.send(content=f"{user.mention}", embed=embed, view=HelpTicketControlView())


class AutoKeresBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True # <--- FONTOS: Ez engedélyezi, hogy lássa az új belépőket!
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Itt regisztráljuk be a gombokat, hogy újraindítás után is működjenek
        self.add_view(TicketPanelView())
        self.add_view(HelpTicketPanelView())
        self.add_view(HelpTicketControlView())
        await self.tree.sync()

bot = AutoKeresBot()

@bot.event
async def on_ready():
    print(f"✅ Bot sikeresen elindult mint: {bot.user}")

# --- RANGADÓ RENDSZER ---
@bot.event
async def on_member_join(member):
    """Amikor valaki belép a szerverre, megkapja az Újonc rangot."""
    ujonc_role = member.guild.get_role(UJONC_ROLE_ID)
    if ujonc_role:
        await member.add_roles(ujonc_role)
        print(f"✅ {member.name} megkapta az Újonc rangot!")

@bot.event
async def on_raw_reaction_add(payload):
    """Amikor valaki reagál a szabályzat üzenetre."""
    if payload.message_id == SZABALYZAT_MESSAGE_ID:
        if str(payload.emoji) == "✅":  # Ha a pipa emojit nyomja meg
            guild = bot.get_guild(payload.guild_id)
            member = guild.get_member(payload.user_id)
            
            if member and not member.bot:
                tag_role = guild.get_role(TAG_ROLE_ID)
                ujonc_role = guild.get_role(UJONC_ROLE_ID)
                
                # Ráadjuk a Tag rangot
                if tag_role:
                    await member.add_roles(tag_role)
                # Levesszük az Újonc rangot
                if ujonc_role:
                    await member.remove_roles(ujonc_role)
                
                print(f"✅ {member.name} elfogadta a szabályzatot!")

# --- PARANCSOK ---

# Eredeti Autóker panel parancs
@bot.tree.command(name="panel", description="Hirdetésfeladó ticket panel kiküldése")
@app_commands.checks.has_permissions(administrator=True)
async def send_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="🚘 HLV3 - Autókereskedés Ticket Rendszer",
        description="Kattints az alábbi gombra egy hirdetésfeladó szoba (ticket) nyitásához!\n\nA szobában lehetőséged lesz képeket feltölteni, megírni a hirdetésed, majd eldönteni, hogy az **Eladás** vagy a **Vásárlás** részlegre küldöd-e be.",
        color=discord.Color.gold()
    )
    await interaction.channel.send(embed=embed, view=TicketPanelView())
    await interaction.response.send_message("Autóker panel kiküldve!", ephemeral=True)

# ÚJ: Segítségkérő panel parancs
@bot.tree.command(name="segitseg_panel", description="Segítségkérő ticket panel kiküldése")
@app_commands.checks.has_permissions(administrator=True)
async def send_help_panel(interaction: discord.Interaction):
    embed = discord.Embed(
        title="📩 Segítségkérés",
        description="Ha kérdésed van, elakadtál, vagy adminisztrátori segítségre van szükséged, kattints az alábbi gombra!\n\nEz létrehoz számodra egy privát szobát, amit csak te és a vezetőség lát, így nyugodtan leírhatod a problémádat.",
        color=discord.Color.blue()
    )
    await interaction.channel.send(embed=embed, view=HelpTicketPanelView())
    await interaction.response.send_message("Segítségkérő panel kiküldve!", ephemeral=True)


if __name__ == "__main__":
    keep_alive()
    bot.run(os.getenv("TOKEN"))
