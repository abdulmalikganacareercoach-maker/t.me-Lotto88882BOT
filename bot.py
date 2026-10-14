import os
import time
import random
import asyncio
import logging
from html import escape
from datetime import time as dtime

import feedparser
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

TOKEN = os.environ["BOT_TOKEN"]

# Public gaming news feeds. Check these URLs in a browser; replace any that stop working.
FEEDS = {
    "IGN": "https://feeds.feedburner.com/ign/all",
    "PC Gamer": "https://www.pcgamer.com/rss/",
    "Polygon": "https://www.polygon.com/rss/index.xml",
}

TIPS = [
    "Warm up before ranked or competitive matches. A few minutes in a practice mode helps your aim and reactions.",
    "Lower your sensitivity if your aim feels shaky. Smooth, controlled movement beats fast, wild movement.",
    "Review your own gameplay. Watching a replay of a loss shows mistakes you do not notice in the moment.",
    "Communicate with your team. Short, clear callouts win more games than silent skill.",
    "Take a break after a few lost games in a row. Playing while frustrated usually makes things worse.",
    "Learn one character, weapon or role well before trying everything. Depth beats variety at the start.",
    "Use headphones if you can. Good audio helps you hear footsteps and other important cues.",
    "Keep your drivers and game updated, and close background apps to get smoother performance.",
    "Lower graphics settings that you do not need, like shadows or effects, to gain extra frames per second.",
    "Stretch your wrists and hands, sit with good posture, and rest your eyes every hour.",
    "Set a play time limit for yourself. Gaming is more fun when it stays balanced with sleep and other things.",
    "Protect your accounts: use a strong password and turn on two-factor login.",
    "Be a good teammate. Staying positive keeps your squad focused and the game more enjoyable.",
]

FACTS = [
    "Nintendo was founded in 1889 as a company making playing cards.",
    "Pong, released by Atari in 1972, was one of the first commercially successful arcade games.",
    "Tetris was created by Alexey Pajitnov in 1984.",
    "Pac-Man was first released in 1980.",
    "Super Mario Bros. launched in 1985 and helped revive the home console market.",
    "Minecraft is the best-selling video game of all time.",
    "The Game Boy was released in 1989.",
    "The first Pokémon games were released in Japan in 1996.",
    "The Magnavox Odyssey, released in 1972, is considered the first home video game console.",
    "The Legend of Zelda first launched in 1986.",
]

# (question, [options], index of correct option)
QUIZ = [
    ("Which company started in 1889 as a playing card business?", ["Sony", "Nintendo", "Sega", "Atari"], 1),
    ("Who created Tetris?", ["Shigeru Miyamoto", "Alexey Pajitnov", "Hideo Kojima", "Gabe Newell"], 1),
    ("In which year was the original Pac-Man released?", ["1975", "1980", "1985", "1990"], 1),
    ("Which of these games came out first?", ["Super Mario Bros.", "Pac-Man", "Pong", "Tetris"], 2),
    ("What is the name of Mario's brother?", ["Wario", "Luigi", "Yoshi", "Toad"], 1),
    ("In which year was the Game Boy released?", ["1985", "1989", "1993", "1997"], 1),
]

MENU = InlineKeyboardMarkup([
    [InlineKeyboardButton("🎮 Gaming Tip", callback_data="tip"),
     InlineKeyboardButton("📰 Latest News", callback_data="news")],
    [InlineKeyboardButton("🧠 Quiz", callback_data="quiz"),
     InlineKeyboardButton("💡 Fun Fact", callback_data="fact")],
    [InlineKeyboardButton("🔔 Daily Tip", callback_data="subscribe")],
])


def tip_text():
    return f"🎮 *Gaming tip*\n\n{random.choice(TIPS)}"


def fact_text():
    return f"💡 *Gaming fact*\n\n{random.choice(FACTS)}"


# ---------- News (cached for 15 minutes) ----------
_news_cache = {"time": 0, "items": []}


def _fetch_news():
    items = []
    for source, url in FEEDS.items():
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]:
                title = entry.get("title")
                link = entry.get("link")
                if title and link:
                    items.append((source, title, link))
        except Exception as e:
            log.warning("Feed %s failed: %s", source, e)
    return items


async def news_text():
    if time.time() - _news_cache["time"] > 900 or not _news_cache["items"]:
        items = await asyncio.to_thread(_fetch_news)
        if items:
            _news_cache["items"] = items
            _news_cache["time"] = time.time()
    items = _news_cache["items"]
    if not items:
        return "Sorry, I could not load the news right now. Please try again later."
    lines = ["📰 <b>Latest gaming headlines</b>\n"]
    for source, title, link in items[:8]:
        lines.append(f'• <a href="{escape(link)}">{escape(title)}</a> ({escape(source)})')
    lines.append("\nHeadlines link to the original sites.")
    return "\n".join(lines)


async def send_news(message):
    text = await news_text()
    await message.reply_text(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=MENU)


# ---------- Commands ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "gamer"
    await update.message.reply_text(
        f"👋 Hi {name}! Welcome to your gaming corner.\n\n"
        "Get gaming tips, the latest headlines, fun facts and a quick quiz.\n\n"
        "Choose an option:",
        reply_markup=MENU,
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Commands:\n"
        "/start - Main menu\n"
        "/tip - Gaming tip\n"
        "/news - Latest gaming headlines\n"
        "/fact - Gaming fun fact\n"
        "/quiz - Gaming quiz question\n"
        "/subscribe - Get one tip every day\n"
        "/unsubscribe - Stop daily tips\n"
        "/about - About this bot"
    )


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "This bot shares free gaming tips, headlines from public gaming news "
        "sites, fun facts and quizzes. It is for fun and learning only."
    )


async def tip_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(tip_text(), parse_mode="Markdown", reply_markup=MENU)


async def fact_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(fact_text(), parse_mode="Markdown", reply_markup=MENU)


async def news_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_news(update.effective_message)


# ---------- Quiz ----------
def quiz_markup(qi):
    _, options, _ = QUIZ[qi]
    rows = [[InlineKeyboardButton(o, callback_data=f"ans:{qi}:{ci}")] for ci, o in enumerate(options)]
    return InlineKeyboardMarkup(rows)


async def quiz_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    qi = random.randrange(len(QUIZ))
    await update.effective_message.reply_text(
        f"🧠 *Quiz*\n\n{QUIZ[qi][0]}", parse_mode="Markdown", reply_markup=quiz_markup(qi)
    )


async def answer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    _, qi, ci = q.data.split(":")
    qi, ci = int(qi), int(ci)
    question, options, correct = QUIZ[qi]
    if ci == correct:
        result = "✅ Correct! Nice one."
    else:
        result = f"❌ Not quite. The answer is: {options[correct]}"
    next_markup = InlineKeyboardMarkup([
        [InlineKeyboardButton("➡️ Next question", callback_data="quiz")],
        [InlineKeyboardButton("🏠 Menu", callback_data="menu")],
    ])
    await q.edit_message_text(f"🧠 {question}\n\n{result}", reply_markup=next_markup)


# ---------- Daily tip subscriptions (in memory; resets on redeploy) ----------
SUBSCRIBERS = set()


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    SUBSCRIBERS.add(update.effective_chat.id)
    await update.effective_message.reply_text("🔔 Subscribed! You will get one gaming tip every day. Use /unsubscribe to stop.")


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    SUBSCRIBERS.discard(update.effective_chat.id)
    await update.message.reply_text("🔕 Unsubscribed. Come back any time with /subscribe.")


async def daily_job(context: ContextTypes.DEFAULT_TYPE):
    for chat_id in list(SUBSCRIBERS):
        try:
            await context.bot.send_message(chat_id, tip_text(), parse_mode="Markdown")
        except Exception as e:
            log.warning("Could not send to %s: %s", chat_id, e)
            SUBSCRIBERS.discard(chat_id)


async def button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data.startswith("ans:"):
        await answer(update, context)
    elif q.data == "tip":
        await q.message.reply_text(tip_text(), parse_mode="Markdown", reply_markup=MENU)
    elif q.data == "fact":
        await q.message.reply_text(fact_text(), parse_mode="Markdown", reply_markup=MENU)
    elif q.data == "news":
        await send_news(q.message)
    elif q.data == "quiz":
        await quiz_cmd(update, context)
    elif q.data == "menu":
        await q.message.reply_text("Choose an option:", reply_markup=MENU)
    elif q.data == "subscribe":
        await subscribe(update, context)


async def fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Use the buttons below or type /help.", reply_markup=MENU)


def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("tip", tip_cmd))
    app.add_handler(CommandHandler("fact", fact_cmd))
    app.add_handler(CommandHandler("news", news_cmd))
    app.add_handler(CommandHandler("quiz", quiz_cmd))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback))

    # Daily tip at 08:00 UTC
    app.job_queue.run_daily(daily_job, time=dtime(hour=8, minute=0))

    log.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
