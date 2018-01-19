import telebot
from telebot import types
from kinopoisk.movie import Movie

# BOT TOKEN GOES HERE
access_token = "TOKEN"
bot = telebot.TeleBot(access_token)


@bot.inline_handler(func=lambda query: len(query.query) > 0)
def query_text(query):
    articles = []
    try:
        movie_list = Movie.objects.search(query.query)
        articles = movie_list_to_query_results(movie_list)
    except Exception as e:
        print("{!s}\n{!s}".format(type(e), str(e)))

    try:
        bot.answer_inline_query(query.id, articles, cache_time=1000)
    except Exception as e:
        print("{!s}\n{!s}".format(type(e), str(e)))


def movie_list_to_query_results(movie_list):
    articles = []
    for movie in movie_list:
        result = types.InlineQueryResultArticle(
            id=movie.id,
            title=f"{movie.title} ({movie.year})",
            description=f"⭐{movie.rating}" if movie.rating != None else "Рейтинг неизвестен",
            input_message_content=types.InputTextMessageContent(
                message_text=f"{movie.title} ({movie.year})\nСсылка: https://www.kinopoisk.ru/film/{movie.id}"
            ),
            thumb_url=f"https://www.kinopoisk.ru/images/film_big/{movie.id}.jpg",
            thumb_height=120, thumb_width=80
        )
        articles.append(result)
    return articles


if __name__ == '__main__':
    bot.polling(none_stop=True)
