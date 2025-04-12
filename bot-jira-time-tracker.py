import discord
from discord.ext import commands
import json
import os
from datetime import datetime
from jira import JIRA
from flask import Flask, request, jsonify
import threading

# Konfiguracja bota Discord
BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN', 'your_discord_bot_token_here')

# Ustaw wszystkie wymagane intencje
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Konfiguracja JIRA
JIRA_SERVER = os.getenv('JIRA_SERVER', 'https://your_domain.atlassian.net')
JIRA_ADMIN_EMAIL = os.getenv('JIRA_EMAIL', 'your_email@example.com')
JIRA_ADMIN_TOKEN = os.getenv('JIRA_API_TOKEN', 'your_jira_api_token_here')

# Nazwa plików konfiguracyjnych
TASKS_FILE = "tasks.json"
CONFIG_FILE = "config.json"

# Struktura pliku config.json:
# {
#   "user_mappings": {
#     "discord_user_id_1": "jira_username_1",
#     "discord_user_id_2": "jira_username_2"
#   }
# }

# Inicjalizacja głównej instancji JIRA
jira = None
try:
    jira = JIRA(server=JIRA_SERVER, basic_auth=(JIRA_ADMIN_EMAIL, JIRA_ADMIN_TOKEN))
    print("Połączono z JIRA (admin)")
except Exception as e:
    print(f"Błąd połączenia z JIRA (admin): {e}")

# Dane o aktywnych sesjach użytkowników
active_sessions = {}


# Funkcje pomocnicze
def load_config():
    """Wczytaj konfigurację z pliku"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"user_mappings": {}}
    except Exception as e:
        print(f"Błąd wczytywania konfiguracji: {e}")
        return {"user_mappings": {}}


def save_config(config):
    """Zapisz konfigurację do pliku"""
    try:
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Błąd zapisywania konfiguracji: {e}")


def load_tasks():
    """Wczytaj mapowanie kanałów i zadań"""
    try:
        if os.path.exists(TASKS_FILE):
            with open(TASKS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        print(f"Błąd wczytywania zadań: {e}")
        return {}


def save_tasks(tasks):
    """Zapisz mapowanie kanałów i zadań"""
    try:
        with open(TASKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, ensure_ascii=False, indent=4)
    except Exception as e:
        print(f"Błąd zapisywania zadań: {e}")


# Wczytaj dane
config = load_config()
channel_tasks = load_tasks()
user_mappings = config.get("user_mappings", {})


# Event handlery bota Discord
@bot.event
async def on_ready():
    print(f'{bot.user} połączony z Discord!')


@bot.event
async def on_voice_state_update(member, before, after):
    # Ignoruj zmiany statusu bota
    if member.bot:
        return

    print(f"Zmiana stanu głosowego: {member.name}")
    print(f"Przed: {before.channel.name if before.channel else 'None'}")
    print(f"Po: {after.channel.name if after.channel else 'None'}")

    # Dołączenie do kanału głosowego
    if before.channel is None and after.channel is not None:
        channel_id = str(after.channel.id)
        if channel_id in channel_tasks:
            # Rozpocznij śledzenie czasu
            task_info = channel_tasks[channel_id]
            active_sessions[member.id] = {
                'channel_id': channel_id,
                'start_time': datetime.now(),
                'task_info': task_info
            }

            try:
                # Powiadom użytkownika o rozpoczęciu śledzenia
                await member.send(
                    f"Rozpoczęto śledzenie czasu na kanale {after.channel.name} "
                    f"dla zadania {task_info['zadanie']} w projekcie {task_info['projekt']}"
                )
                print(f"Użytkownik {member.name} rozpoczął śledzenie na kanale {after.channel.name}")
            except Exception as e:
                print(f"Nie można wysłać wiadomości do {member.name}: {e}")

    # Opuszczenie kanału głosowego
    if before.channel is not None and (after.channel is None or before.channel.id != after.channel.id):
        print(f"Użytkownik {member.name} opuścił kanał {before.channel.name}")

        if member.id in active_sessions:
            print(f"Znaleziono aktywną sesję dla {member.name}")
            session = active_sessions[member.id]
            channel_id = session['channel_id']

            # Oblicz czas spędzony na kanale
            start_time = session['start_time']
            end_time = datetime.now()
            duration = end_time - start_time
            duration_minutes = round(duration.total_seconds() / 60, 2)

            print(f"Czas spędzony: {duration_minutes} minut")

            # Zapisz czas w JIRA
            if duration_minutes >= 0.1 and jira is not None:  # Zmniejszamy próg do 0.1 min dla testów
                task_info = session['task_info']
                discord_id = str(member.id)

                # Formatowanie czasu dla JIRA (np. "2h 30m")
                hours = int(duration_minutes // 60)
                minutes = int(duration_minutes % 60)

                time_spent = ""
                if hours > 0:
                    time_spent += f"{hours}h "
                if minutes > 0 or time_spent == "":
                    time_spent += f"{minutes}m"

                # Sprawdź, czy użytkownik Discord ma mapowanie do użytkownika JIRA
                jira_username = None
                if discord_id in user_mappings:
                    jira_username = user_mappings[discord_id]

                if jira_username:
                    print(f"Próba dodania czasu: {time_spent} do zadania {task_info['zadanie']} jako {jira_username}")

                    try:
                        # Próba 1: Bezpośrednie użycie parametru user w add_worklog
                        try:
                            worklog = jira.add_worklog(
                                issue=task_info['zadanie'],
                                timeSpent=time_spent,
                                comment=f"Automatyczny log czasu z Discord - kanał: {before.channel.name}",
                                adjustEstimate=None,
                                newEstimate=None,
                                reduceBy=None,
                                started=None,
                                user=jira_username
                            )

                            print(f"Dodano worklog do JIRA jako {jira_username}")

                            # Powiadom użytkownika
                            await member.send(
                                f"Zarejestrowano {time_spent} w zadaniu {task_info['zadanie']} projektu {task_info['projekt']} "
                                f"jako użytkownik JIRA: {jira_username}"
                            )

                        except Exception as e:
                            print(f"Nie udało się użyć parametru user: {e}")

                            # Próba 2: Użycie REST API bezpośrednio
                            try:
                                # Przygotuj dane worklogu
                                worklog_data = {
                                    'timeSpent': time_spent,
                                    'comment': f"Automatyczny log czasu z Discord - kanał: {before.channel.name}",
                                    'author': {'name': jira_username}
                                }

                                # Wykonaj żądanie REST API
                                url = f"{JIRA_SERVER}/rest/api/2/issue/{task_info['zadanie']}/worklog"
                                response = jira._session.post(url, json=worklog_data)

                                if response.status_code == 201:
                                    print(f"Dodano worklog do JIRA jako {jira_username} przez REST API")

                                    # Powiadom użytkownika
                                    await member.send(
                                        f"Zarejestrowano {time_spent} w zadaniu {task_info['zadanie']} projektu {task_info['projekt']} "
                                        f"jako użytkownik JIRA: {jira_username}"
                                    )
                                else:
                                    raise Exception(f"Błąd REST API: {response.status_code} - {response.text}")

                            except Exception as e2:
                                print(f"Nie udało się użyć REST API: {e2}")

                                # Próba 3: Standardowy worklog z informacją w komentarzu
                                worklog = jira.add_worklog(
                                    issue=task_info['zadanie'],
                                    timeSpent=time_spent,
                                    comment=f"Automatyczny log czasu z Discord dla użytkownika {jira_username} - kanał: {before.channel.name}"
                                )

                                print(f"Dodano worklog do JIRA z komentarzem o użytkowniku {jira_username}")

                                # Powiadom użytkownika
                                await member.send(
                                    f"Zarejestrowano {time_spent} w zadaniu {task_info['zadanie']} projektu {task_info['projekt']} "
                                    f"(nie udało się zalogować bezpośrednio jako {jira_username}, czas został zalogowany przez bota z informacją o tobie w komentarzu)"
                                )

                    except Exception as e:
                        error_message = f"Nie udało się zalogować czasu: {str(e)}"
                        print(error_message)
                        await member.send(error_message)
                else:
                    # Użytkownik nie ma mapowania do JIRA
                    try:
                        # Standardowy worklog z informacją o użytkowniku Discord
                        worklog = jira.add_worklog(
                            issue=task_info['zadanie'],
                            timeSpent=time_spent,
                            comment=f"Automatyczny log czasu z Discord dla użytkownika {member.name} - kanał: {before.channel.name}"
                        )

                        print(f"Dodano worklog do JIRA z komentarzem o użytkowniku Discord {member.name}")

                        # Powiadom użytkownika
                        await member.send(
                            f"Zarejestrowano {time_spent} w zadaniu {task_info['zadanie']} projektu {task_info['projekt']}. "
                            f"Nie znaleziono mapowania twojego konta Discord do konta JIRA."
                        )
                    except Exception as e:
                        error_message = f"Błąd rejestracji czasu w JIRA: {str(e)}"
                        print(error_message)
                        await member.send(error_message)
            else:
                print(f"Nie dodano worklogu: czas zbyt krótki ({duration_minutes} min) lub brak połączenia z JIRA")

            # Usuń sesję
            del active_sessions[member.id]
        else:
            print(f"Nie znaleziono aktywnej sesji dla {member.name}")


# Komendy do zarządzania mapowaniami użytkowników
@bot.command(name='reload_config')
async def reload_config(ctx):
    """Przeładuj konfigurację z pliku"""
    global config, user_mappings

    config = load_config()
    user_mappings = config.get("user_mappings", {})

    await ctx.send("Konfiguracja została przeładowana.")


@bot.command(name='show_mappings')
async def show_mappings(ctx):
    """Pokaż wszystkie mapowania użytkowników Discord do JIRA"""
    if not user_mappings:
        await ctx.send("Brak zapisanych mapowań użytkowników.")
        return

    message = "Mapowania użytkowników Discord do JIRA:\n"
    for discord_id, jira_username in user_mappings.items():
        # Spróbuj znaleźć użytkownika Discord
        discord_name = "Nieznany"
        for guild in bot.guilds:
            user = guild.get_member(int(discord_id))
            if user:
                discord_name = user.name
                break

        message += f"- Discord: {discord_name} ({discord_id}), JIRA: {jira_username}\n"

    await ctx.send(message)


# Komendy do zarządzania zadaniami
@bot.command(name='set_task')
async def set_task(ctx, channel_id: str, projekt: str, zadanie: str):
    """Przypisz zadanie JIRA do kanału głosowego"""
    # Sprawdź czy kanał istnieje
    try:
        channel = bot.get_channel(int(channel_id))
        if not channel:
            await ctx.send(f"Nie znaleziono kanału o ID {channel_id}")
            return

        # Sprawdź czy zadanie istnieje w JIRA
        if jira:
            try:
                issue = jira.issue(zadanie)
            except Exception:
                await ctx.send(f"Nie znaleziono zadania {zadanie} w JIRA. Sprawdź poprawność kodu zadania.")
                return

        # Zapisz mapowanie
        channel_tasks[channel_id] = {
            'projekt': projekt,
            'zadanie': zadanie
        }
        save_tasks(channel_tasks)

        await ctx.send(
            f"Ustawiono śledzenie czasu na kanale {channel.name} dla zadania {zadanie} w projekcie {projekt}")
    except ValueError:
        await ctx.send("Nieprawidłowe ID kanału. Upewnij się, że podałeś poprawny numer.")


@bot.command(name='show_tasks')
async def show_tasks(ctx):
    """Pokaż wszystkie przypisane zadania"""
    if not channel_tasks:
        await ctx.send("Nie ma żadnych przypisanych zadań.")
        return

    message = "Twoje ustawione zadania:\n"
    for channel_id, task_info in channel_tasks.items():
        channel = bot.get_channel(int(channel_id))
        channel_name = channel.name if channel else f"Nieznany kanał ({channel_id})"
        message += f"- Kanał: {channel_name}, Projekt: {task_info['projekt']}, Zadanie: {task_info['zadanie']}\n"

    await ctx.send(message)


@bot.command(name='remove_task')
async def remove_task(ctx, channel_id: str):
    """Usuń przypisanie zadania z kanału"""
    if channel_id in channel_tasks:
        channel = bot.get_channel(int(channel_id))
        channel_name = channel.name if channel else f"Nieznany kanał ({channel_id})"

        del channel_tasks[channel_id]
        save_tasks(channel_tasks)

        await ctx.send(f"Usunięto zadanie dla kanału {channel_name}")
    else:
        await ctx.send("Nie znaleziono przypisania zadania dla tego kanału.")


@bot.command(name='test_jira')
async def test_jira(ctx):
    """Test połączenia z JIRA"""
    if jira:
        try:
            # Spróbuj pobrać bieżącego użytkownika jako test
            myself = jira.myself()
            await ctx.send(f"Połączenie z JIRA działa! Zalogowany jako: {myself['displayName']}")

            # Spróbuj wyświetlić szczegóły projektu
            await ctx.send("Próba wyświetlenia projektów...")

            projects = jira.projects()
            project_list = ", ".join([project.key for project in projects])
            await ctx.send(f"Dostępne projekty: {project_list}")

        except Exception as e:
            await ctx.send(f"Błąd podczas testowania JIRA: {str(e)}")
    else:
        await ctx.send("Brak połączenia z JIRA.")


@bot.command(name='add_worklog')
async def add_worklog(ctx, zadanie: str, czas: str, *, komentarz: str = "Ręcznie dodany czas"):
    """Ręcznie dodaj worklog do JIRA (np. !add_worklog PROJ-123 30m Praca nad funkcją X)"""
    if jira is None:
        await ctx.send("Nie ma połączenia z JIRA.")
        return

    discord_id = str(ctx.author.id)

    try:
        # Sprawdź czy użytkownik ma mapowanie do JIRA
        if discord_id in user_mappings:
            jira_username = user_mappings[discord_id]

            try:
                # Próba dodania worklogu jako użytkownik
                worklog = jira.add_worklog(
                    issue=zadanie,
                    timeSpent=czas,
                    comment=komentarz,
                    adjustEstimate=None,
                    newEstimate=None,
                    reduceBy=None,
                    started=None,
                    user=jira_username
                )

                await ctx.send(
                    f"Dodano worklog do zadania {zadanie} jako {jira_username}. Czas: {czas}, Komentarz: {komentarz}")
                return
            except Exception as e:
                print(f"Błąd przy dodawaniu worklogu jako {jira_username}: {e}")
                # Kontynuuj do standardowej metody

        # Standardowa metoda jako admin
        worklog = jira.add_worklog(
            issue=zadanie,
            timeSpent=czas,
            comment=komentarz
        )

        await ctx.send(f"Dodano worklog do zadania {zadanie}. Czas: {czas}, Komentarz: {komentarz}")
    except Exception as e:
        await ctx.send(f"Błąd podczas dodawania worklogu: {str(e)}")


# Inicjalizacja serwera Flask
app = Flask(__name__)


@app.route('/webhook/voice-activity', methods=['POST'])
def voice_activity_webhook():
    data = request.json

    user_id = data.get('user_id')
    channel_id = data.get('channel_id')
    duration_minutes = data.get('duration_minutes')

    # Sprawdź czy mamy mapowanie dla tego kanału
    if channel_id in channel_tasks:
        task_info = channel_tasks[channel_id]

        # Formatowanie czasu dla JIRA
        time_spent = f"{duration_minutes}m"

        try:
            # Jeśli znamy użytkownika Discord, spróbuj użyć jego mapowania do JIRA
            if user_id and user_id in user_mappings:
                jira_username = user_mappings[user_id]

                try:
                    # Próba dodania worklogu jako użytkownik
                    worklog = jira.add_worklog(
                        issue=task_info['zadanie'],
                        timeSpent=time_spent,
                        comment=f"Automatyczny log czasu z Discord - kanał: {data.get('channel_name', 'Kanał Discord')}",
                        adjustEstimate=None,
                        newEstimate=None,
                        reduceBy=None,
                        started=None,
                        user=jira_username
                    )

                    return jsonify({'status': 'success'})
                except Exception as e:
                    print(f"Błąd przy dodawaniu worklogu jako {jira_username}: {e}")
                    # Kontynuuj do standardowej metody

            # Standardowa metoda jako admin
            jira.add_worklog(
                issue=task_info['zadanie'],
                timeSpent=time_spent,
                comment=f"Automatyczny log czasu z Discord - kanał: {data.get('channel_name', 'Kanał Discord')}"
            )
            return jsonify({'status': 'success'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': str(e)}), 500
    else:
        return jsonify({'status': 'error', 'message': 'Kanał nie ma przypisanego zadania'}), 400


# Funkcja uruchamiająca serwer Flask
def run_flask():
    app.run(host='0.0.0.0', port=5000)


# Główna funkcja
def main():
    # Uruchom Flask w osobnym wątku
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True  # Wątek zostanie zamknięty po zamknięciu głównego programu
    flask_thread.start()

    print("Serwer Flask uruchomiony!")

    # Uruchom bota Discord w głównym wątku
    bot.run(BOT_TOKEN)


if __name__ == '__main__':
    main()