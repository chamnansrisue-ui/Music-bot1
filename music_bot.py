# ====================================
#  Discord Music Bot
#  คำสั่ง: N!p play / skip / stop / pause / resume / queue
# ====================================
# ติดตั้งก่อนรัน:
#   pip install discord.py yt-dlp PyNaCl
# ====================================

import discord
import yt_dlp
import asyncio
from collections import deque

TOKEN = "MTUyMDU4MDk0ODkyNjY2NDgwNA.GgJh2G.nToWEog-s5Tp9bfDQCnnSNk-tztFucztSPfoIg"

YDL_OPTIONS = {
    "format": "bestaudio/best",
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "noplaylist": True,
    "socket_timeout": 10,
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

song_cache = {}
queues = {}
current_ctx = {}

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


async def fetch_song(query):
    if query in song_cache:
        return song_cache[query]

    def _search():
        with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
            try:
                if query.startswith("http"):
                    info = ydl.extract_info(query, download=False)
                    if "entries" in info:
                        info = info["entries"][0]
                else:
                    info = ydl.extract_info(f"ytsearch:{query}", download=False)
                    if info and "entries" in info and info["entries"]:
                        info = info["entries"][0]
                    else:
                        return None
                return {
                    "url": info["url"],
                    "title": info.get("title", "ไม่ทราบชื่อ"),
                }
            except Exception as e:
                print(f"[error] {e}")
                return None

    result = await asyncio.get_event_loop().run_in_executor(None, _search)
    if result:
        song_cache[query] = result
    return result


def play_next(guild_id, vc):
    if queues.get(guild_id):
        song = queues[guild_id].popleft()
        source = discord.FFmpegPCMAudio(song["url"], **FFMPEG_OPTIONS)
        vc.play(source, after=lambda e: play_next(guild_id, vc))
        ctx = current_ctx.get(guild_id)
        if ctx:
            asyncio.run_coroutine_threadsafe(
                ctx.channel.send(f"🎵 กำลังเล่น: **{song['title']}**"),
                client.loop
            )


@client.event
async def on_ready():
    print(f"✅ บอทพร้อมแล้ว! เข้าสู่ระบบในชื่อ: {client.user}")
    await client.change_presence(activity=discord.Game(name="N!p play"))


@client.event
async def on_message(message):
    if message.author.bot:
        return

    content = message.content.strip()

    # เช็คว่าเริ่มต้นด้วย N!p (ไม่สนเว้นวรรค)
    if not content.lower().startswith("n!p"):
        return

    # ตัด prefix ออก แล้วแยก args
    rest = content[3:].strip()  # ตัด "N!p" ออก
    parts = rest.split(None, 1)
    if not parts:
        return

    cmd = parts[0].lower()
    arg = parts[1] if len(parts) > 1 else ""
    guild_id = message.guild.id

    print(f"[CMD] {cmd} | arg: {arg}")

    # ── play ──────────────────────────────────────
    if cmd == "play" or cmd == "p":
        if not message.author.voice:
            return await message.channel.send("❌ เข้าห้องเสียงก่อนนะครับ!")
        if not arg:
            return await message.channel.send("❌ ระบุชื่อเพลงหรือ URL ด้วยครับ เช่น `N!p play เพลง`")

        channel = message.author.voice.channel
        vc = message.guild.voice_client

        if vc is None:
            vc = await channel.connect()
        elif vc.channel != channel:
            await vc.move_to(channel)

        current_ctx[guild_id] = message

        await message.channel.send(f"🔍 กำลังค้นหา: **{arg}**...")
        song = await fetch_song(arg)
        if not song:
            return await message.channel.send("❌ ไม่พบเพลงนั้นครับ")

        if guild_id not in queues:
            queues[guild_id] = deque()

        if vc.is_playing() or vc.is_paused():
            queues[guild_id].append(song)
            await message.channel.send(f"➕ เพิ่มเข้าคิว: **{song['title']}** (ลำดับที่ {len(queues[guild_id])})")
        else:
            source = discord.FFmpegPCMAudio(song["url"], **FFMPEG_OPTIONS)
            vc.play(source, after=lambda e: play_next(guild_id, vc))
            await message.channel.send(f"🎵 กำลังเล่น: **{song['title']}**")

    # ── skip ──────────────────────────────────────
    elif cmd == "skip" or cmd == "s":
        vc = message.guild.voice_client
        if vc and vc.is_playing():
            vc.stop()
            await message.channel.send("⏭️ ข้ามเพลงแล้วครับ!")
        else:
            await message.channel.send("❌ ไม่มีเพลงเล่นอยู่ครับ")

    # ── stop ──────────────────────────────────────
    elif cmd == "stop":
        if guild_id in queues:
            queues[guild_id].clear()
        vc = message.guild.voice_client
        if vc and vc.is_connected():
            vc.stop()
            await vc.disconnect()
            await message.channel.send("⏹️ หยุดและออกจากห้องเสียงแล้วครับ")
        else:
            await message.channel.send("❌ บอทไม่ได้อยู่ในห้องเสียงครับ")

    # ── pause ─────────────────────────────────────
    elif cmd == "pause":
        vc = message.guild.voice_client
        if vc and vc.is_playing():
            vc.pause()
            await message.channel.send("⏸️ หยุดพักชั่วคราวครับ")
        else:
            await message.channel.send("❌ ไม่มีเพลงเล่นอยู่ครับ")

    # ── resume ────────────────────────────────────
    elif cmd == "resume" or cmd == "r":
        vc = message.guild.voice_client
        if vc and vc.is_paused():
            vc.resume()
            await message.channel.send("▶️ เล่นต่อแล้วครับ!")
        else:
            await message.channel.send("❌ เพลงไม่ได้หยุดพักอยู่ครับ")

    # ── queue ─────────────────────────────────────
    elif cmd == "queue" or cmd == "q":
        q = queues.get(guild_id)
        if not q:
            return await message.channel.send("📭 คิวว่างอยู่ครับ")
        lines = [f"`{i+1}.` {song['title']}" for i, song in enumerate(q)]
        await message.channel.send("🎶 **คิวเพลงตอนนี้:**\n" + "\n".join(lines))

    # ── help ──────────────────────────────────────
    elif cmd == "help" or cmd == "h":
        embed = discord.Embed(title="🎵 คำสั่งบอทเพลง", color=0x5865F2)
        embed.add_field(name="N!p play <เพลง/URL>", value="เปิดเพลง / เพิ่มเข้าคิว", inline=False)
        embed.add_field(name="N!p skip", value="ข้ามเพลง", inline=False)
        embed.add_field(name="N!p pause", value="หยุดพักชั่วคราว", inline=False)
        embed.add_field(name="N!p resume", value="เล่นต่อ", inline=False)
        embed.add_field(name="N!p stop", value="หยุดและออกจากห้องเสียง", inline=False)
        embed.add_field(name="N!p queue", value="ดูคิวเพลง", inline=False)
        await message.channel.send(embed=embed)


client.run(TOKEN)
