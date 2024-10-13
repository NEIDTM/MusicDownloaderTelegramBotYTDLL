import os
import re
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# Путь к папке для загрузки музыки
DOWNLOADS_DIR = os.path.join(os.path.expanduser('~'), 'Desktop', 'Music_Downloads')

# Создаём папку, если она не существует
os.makedirs(DOWNLOADS_DIR, exist_ok=True)

def clean_filename(filename: str) -> str:
    cleaned = re.sub(r'[<>:"/\\|?*]+', '', filename)
    cleaned = re.sub(r'[ \-+=,./]', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()

def format_duration(duration: float) -> str:
    duration = int(duration)
    minutes = duration // 60
    seconds = duration % 60
    return f"{minutes}:{seconds:02d}"

async def search_music(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Удаляем сообщение с командой /music
    await update.message.delete()
    
    # Удаляем ответ на /start, если он есть
    if 'start_message_id' in context.user_data:
        await update.message.chat.delete_message(context.user_data['start_message_id'])
        del context.user_data['start_message_id']

    query_message = await update.message.reply_text('Пожалуйста, введите название песни, которую вы хотите найти.')
    context.user_data['waiting_for_query'] = True
    context.user_data['query_message_id'] = query_message.message_id  # Сохраняем ID сообщения для удаления

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if 'waiting_for_query' in context.user_data:
        query = update.message.text
        if not query:
            await update.message.reply_text('Пожалуйста, введите название песни.')
            return
        
        # Удаляем сообщение с запросом
        await update.message.chat.delete_message(context.user_data['query_message_id'])

        ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'noplaylist': True,
            'extract_flat': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                info_dict = ydl.extract_info(f"ytsearch5:{query} audio", download=False)
                songs = info_dict['entries']
            except Exception as e:
                await update.message.reply_text(f"Произошла ошибка при поиске: {str(e)}")
                return

        music_options = []
        for i, song in enumerate(songs):
            title = song['title']
            duration = format_duration(song['duration']) if 'duration' in song else 'N/A'
            uploader = song.get('uploader', 'Unknown')
            music_options.append(f"{i + 1}. {title} by {uploader} | Длительность: {duration}")

        reply_text = "Выберите номер песни:\n" + "\n".join(music_options)
        reply_message = await update.message.reply_text(reply_text)

        context.user_data['waiting_for_selection'] = True
        context.user_data['songs'] = songs
        context.user_data['reply_message_id'] = reply_message.message_id  # Сохраняем ID сообщения для удаления
        context.user_data['last_query_message_id'] = update.message.message_id  # Сохраняем ID запроса на песню
        del context.user_data['waiting_for_query']
    elif 'waiting_for_selection' in context.user_data:
        await handle_selection(update, context)

async def handle_selection(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    selected_number = update.message.text
    if selected_number.isdigit() and 1 <= int(selected_number) <= 5:
        song_info = context.user_data['songs'][int(selected_number) - 1]
        song_title = song_info['title']
        song_url = song_info['url']
        
        # Уведомление о скачивании
        download_message = await update.message.reply_text(f"Скачивание {song_title}...")

        cleaned_title = clean_filename(song_title)
        output_filename = os.path.join(DOWNLOADS_DIR, f"{cleaned_title}.mp3")

        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_filename,
            'quiet': True,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([song_url])
            except Exception as e:
                await update.message.reply_text(f"Произошла ошибка при скачивании: {str(e)}")
                return

        await update.message.reply_audio(audio=open(output_filename, 'rb'))

        # Удаляем скачанный файл после отправки
        os.remove(output_filename)

        # Удаляем сообщения после завершения
        await update.message.chat.delete_message(context.user_data['reply_message_id'])
        await update.message.chat.delete_message(context.user_data['last_query_message_id'])
        await download_message.delete()  # Удаляем сообщение о скачивании
        await update.message.delete()  # Удаляем сообщение с номером

        del context.user_data['waiting_for_selection']
        del context.user_data['songs']
        del context.user_data['reply_message_id']
        del context.user_data['last_query_message_id']
    else:
        await update.message.reply_text("Пожалуйста, выберите номер от 1 до 5.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # Удаляем сообщение с командой /start
    await update.message.delete()
    
    # Отправляем приветственное сообщение
    start_message = await update.message.reply_text('Привет! Используйте команду /music, чтобы искать музыку.')
    
    # Сохраняем ID ответа на команду /start
    context.user_data['start_message_id'] = start_message.message_id

def main() -> None:
    application = ApplicationBuilder().token("").build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("music", search_music))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()
