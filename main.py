import os
import yt_dlp 
import discord
import asyncio
from discord.ext import commands
from asyncio import Lock, to_thread
from keep_alive import keep_alive

DISCORD_TOKEN = os.environ['discordkey']
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

# Fonte YTDL
class YTDLSource(discord.PCMVolumeTransformer):
    YTDL_OPTS = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'default_search': 'auto',
        'source_address': '127.0.0.1',  # Melhor para host externo tipo Render
        'force-ipv4': True,
        'prefer_ffmpeg': True,
    }

    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def create(cls, search: str):
        await asyncio.sleep(2)  # previne rate limiting
        try:
            def extract():
                with yt_dlp.YoutubeDL(cls.YTDL_OPTS) as ydl:
                    return ydl.extract_info(search, download=False)
            info = await to_thread(extract)
            if 'entries' in info:
                info = info['entries'][0]
            source = discord.FFmpegPCMAudio(info['url'], executable=FFMPEG_PATH)
            return cls(source, data=info)
        except Exception as e:
            raise Exception(f"Falha ao extrair info com yt_dlp: {e}")

# Módulo de Música
class MusicPlayer(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queues = {}
        self.lock = Lock()

    async def ensure_queue(self, guild_id):
        self.queues.setdefault(guild_id, [])

    async def kill_ffmpeg(self, vc):
        try:
            ffmpeg_process = getattr(vc.source, "_process", None)
            if ffmpeg_process and ffmpeg_process.poll() is None:
                ffmpeg_process.kill()
        except Exception as e:
            print(f"Erro ao matar ffmpeg: {e}")

    async def play_next(self, ctx):
        await self.ensure_queue(ctx.guild.id)
        queue = self.queues[ctx.guild.id]
        if not queue:
            return

        source = queue.pop(0)

        def after_play(err):
            if err:
                print(f"Erro ao tocar a música: {err}")
            ctx.bot.loop.create_task(self.play_next(ctx))

        try:
            await self.kill_ffmpeg(ctx.voice_client)
            ctx.voice_client.play(source, after=after_play)
            await ctx.send(f"▶️ A tocar esta merda: **{source.title}**")
        except Exception as e:
            await ctx.send(f"❌ Erro ao tentar tocar a próxima: {e}")

    @commands.command(name="join")
    async def cmd_join(self, ctx):
        if not ctx.author.voice:
            return await ctx.send("❌ Conecte-se a uma chamada burro.")
        await ctx.author.voice.channel.connect()
        await ctx.send(f"🔊 Boas putas como tamos? estou na sala: **{ctx.author.voice.channel}**")

    @commands.command(name="disconnect")
    async def cmd_leave(self, ctx):
        vc = ctx.voice_client
        if not vc:
            return await ctx.send("❌ Não estou em nenhuma chamada otário do caralho.")
        await self.kill_ffmpeg(vc)
        await vc.disconnect()
        await ctx.send("👋 Fui com as putas bro.")

    @commands.command(name="play")
    async def cmd_play(self, ctx, *, query: str):
        if not ctx.voice_client:
            return await ctx.send("❌ Usa `-join` antes. Burro de merda")

        await ctx.send("🔍 A procurar essa merda...")
        try:
            source = await YTDLSource.create(query)
        except Exception as e:
            return await ctx.send(f"❌ Erro ao encontrar essa música de merda: {e}")

        async with self.lock:
            await self.ensure_queue(ctx.guild.id)
            queue = self.queues[ctx.guild.id]
            if ctx.voice_client.is_playing() or queue:
                if len(queue) >= 10:
                    return await ctx.send("❌ A fila está cheia (máx. 10). CARALHO")
                queue.append(source)
                return await ctx.send(f"✅ Adicionado à fila: **{source.title}**")

            def _after(err):
                if err:
                    print(f"Erro no _after: {err}")
                ctx.bot.loop.create_task(self.play_next(ctx))

            ctx.voice_client.play(source, after=_after)
            await ctx.send(f"▶️ A tocar esta merda: **{source.title}**")

    @commands.command(name="skip")
    async def cmd_skip(self, ctx):
        vc = ctx.voice_client
        if not vc or not vc.is_playing():
            return await ctx.send("❌ Nem estou a cantar nada caralho deixa-me estar foda-se.")
        await self.kill_ffmpeg(vc)
        vc.stop()
        await ctx.send("⏭️ Skip nessa merda.")

    @commands.command(name="queue")
    async def cmd_queue(self, ctx):
        await self.ensure_queue(ctx.guild.id)
        queue = self.queues[ctx.guild.id]
        if not queue:
            return await ctx.send("A fila está vazia. Burro de merda.")
        msg = "\n".join(f"{i+1}. {song.title}" for i, song in enumerate(queue))
        await ctx.send(f"🎶 **Fila atual:**\n{msg}")

    @commands.command(name="pause")
    async def cmd_pause(self, ctx):
        vc = ctx.voice_client
        if not vc or not vc.is_playing():
            return await ctx.send("❌ Nada para pausar oh surdo do caralho.")
        vc.pause()
        await ctx.send("⏸️ Pause nessa merda.")

    @commands.command(name="resume")
    async def cmd_resume(self, ctx):
        vc = ctx.voice_client
        if not vc or not vc.is_paused():
            return await ctx.send("❌ Nada para retomar otário.")
        vc.resume()
        await ctx.send("▶️ Recomecei esta merda caralho.")

# Bot principal
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="-", intents=intents)

    async def setup_hook(self):
        await self.add_cog(MusicPlayer(self))

bot = MyBot()

@bot.event
async def on_ready():
    print(f"{bot.user} está online!")

keep_alive()
bot.run(DISCORD_TOKEN)
