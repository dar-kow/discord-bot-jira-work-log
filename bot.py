import discord
from discord.ext import commands
import json
import os
from datetime import datetime, timedelta
import requests
from jira import JIRA
from flask import Flask, request, jsonify
import threading

# Konfiguracja bota Discord
BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN', 'your_discord_bot_token')

# Ustaw wszystkie wymagane intencje
intents = discord.Intents.default()
intents.members = True
intents.voice_states = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Konfiguracja JIRA i Tempo
JIRA_SERVER = os.getenv('JIRA_SERVER', 'https://your_domain.atlassian.net')
JIRA_ADMIN_EMAIL = os.getenv('JIRA_EMAIL', 'your_email@example.com')
JIRA_ADMIN_TOKEN = os.getenv('JIRA_API_TOKEN', 'your_jira_api_token')

# Konfiguracja Tempo API
TEMPO_API_TOKEN = os.getenv('TEMPO_API_TOKEN', 'your_tempo_api_token')
# Wybierz odpowiedni region lub użyj domyślnego
TEMPO_API_BASE = os.getenv('TEMPO_API_BASE', 'https://api.tempo.io')

# Nazwa plików konfiguracyjnych
TASKS_FILE = "tasks.json"
CONFIG_FILE = "config.json"

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


# Nowa funkcja do rejestrowania czasu przez Tempo API
def log_time_via_tempo(issue_key, worker_account_id, time_spent_seconds, start_time, description):
    """
    Rejestruj czas pracy przez Tempo REST API

    :param issue_key: Klucz zadania JIRA (np. 'MBA-7')
    :param worker_account_id: Account ID lub nazwa użytkownika JIRA
    :param time_spent_seconds: Czas spędzony w sekundach
    :param start_time: Rzeczywisty czas rozpoczęcia (obiekt datetime)
    :param description: Opis rejestrowanego czasu
    """
    try:
        # Pobierz ID zadania z JIRA
        issue = jira.issue(issue_key)
        issue_id = issue.id

        # Endpoint Tempo API dla worklogów
        tempo_api_url = f"{TEMPO_API_BASE}/4/worklogs"

        # Formatuj datę i czas rozpoczęcia z przekazanego obiektu datetime
        start_date = start_time.strftime("%Y-%m-%d")
        start_time_str = start_time.strftime("%H:%M:%S")

        # Dane dla API Tempo używające rzeczywistego czasu startu
        worklog_data = {
            "issueId": issue_id,
            "timeSpentSeconds": time_spent_seconds,
            "startDate": start_date,
            "startTime": start_time_str,
            "authorAccountId": worker_account_id,
            "description": description
        }

        headers = {
            "Authorization": f"Bearer {TEMPO_API_TOKEN}",
            "Content-Type": "application/json"
        }

        # Debug - wypisz dokładne dane wysyłane do API
        print(f"Wysyłanie danych do API Tempo: {worklog_data}")

        # Wykonaj żądanie do API Tempo
        response = requests.post(
            tempo_api_url,
            json=worklog_data,
            headers=headers
        )

        if response.status_code in [200, 201]:
            print(f"Czas zarejestrowany pomyślnie przez Tempo dla {worker_account_id}")
            return response.json()
        else:
            print(f"Błąd rejestracji czasu przez Tempo: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Wyjątek podczas rejestrowania czasu przez Tempo: {e}")
        return None

# Komenda do testowania połączenia z Tempo API
@bot.command(name='test_tempo_connection')
async def test_tempo_connection(ctx):
    """Test połączenia z Tempo API"""
    tempo_api_url = f"{TEMPO_API_BASE}/4/worklogs"

    headers = {
        "Authorization": f"Bearer {TEMPO_API_TOKEN}",
        "Content-Type": "application/json"
    }

    try:
        # Próba pobrania informacji o worklogach (tylko sprawdzenie połączenia)
        response = requests.get(
            f"{tempo_api_url}/search",
            headers=headers,
            params={"from": datetime.now().strftime("%Y-%m-%d")}
        )

        if response.status_code == 200:
            await ctx.send(f"Połączenie z Tempo API działa! Kod odpowiedzi: {response.status_code}")
        else:
            await ctx.send(f"Błąd połączenia z Tempo API. Kod: {response.status_code}, Treść: {response.text}")
    except Exception as e:
        await ctx.send(f"Wyjątek podczas testowania Tempo API: {str(e)}")


@bot.command(name='get_account_id')
async def get_account_id(ctx):
    """Pobierz swoje Atlassian Account ID"""
    try:
        # Pobierz informacje o aktualnie zalogowanym użytkowniku
        myself = jira.myself()
        account_id = myself['accountId']

        await ctx.send(f"Twoje Atlassian Account ID: `{account_id}`\n"
                       f"To jest wartość, którą powinieneś używać w mapowaniu użytkowników.")
    except Exception as e:
        await ctx.send(f"Błąd podczas pobierania Account ID: {str(e)}")


@bot.command(name='find_jira_account_id')
async def find_jira_account_id(ctx, search_term: str):
    """Znajdź Account ID użytkownika JIRA na podstawie nazwy, emaila lub innego identyfikatora"""
    try:
        # Wyszukaj użytkowników w JIRA
        users = jira.search_users(search_term)

        if not users:
            await ctx.send(f"Nie znaleziono użytkowników pasujących do '{search_term}' w JIRA.")
            return

        # Pokaż informacje o znalezionych użytkownikach
        message = f"Znalezieni użytkownicy JIRA dla zapytania '{search_term}':\n"
        for user in users:
            message += f"- Nazwa: {user.displayName}\n"
            message += f"  Email: {user.emailAddress if hasattr(user, 'emailAddress') else 'Brak'}\n"
            message += f"  Account ID: `{user.accountId}`\n\n"

        await ctx.send(message)
    except Exception as e:
        await ctx.send(f"Błąd podczas wyszukiwania użytkowników: {str(e)}")


@bot.command(name='map_user')
async def map_user(ctx, discord_user: discord.Member, jira_account_id: str):
    """Mapuj użytkownika Discord na Account ID użytkownika JIRA"""
    global user_mappings

    # Zapisz mapowanie
    user_mappings[str(discord_user.id)] = jira_account_id
    save_config({"user_mappings": user_mappings})

    await ctx.send(f"Pomyślnie zmapowano użytkownika Discord {discord_user.name} na Account ID JIRA: {jira_account_id}")


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
            start_time = session['start_time']  # Rzeczywisty czas rozpoczęcia
            end_time = datetime.now()
            duration = end_time - start_time
            duration_seconds = int(duration.total_seconds())
            duration_minutes = round(duration.total_seconds() / 60, 2)

            print(
                f"Czas spędzony: {duration_minutes} minut, od {start_time.strftime('%H:%M:%S')} do {end_time.strftime('%H:%M:%S')}")

            # Zapisz czas w JIRA przez Tempo
            if duration_minutes >= 0.1:  # Zmniejszamy próg do 0.1 min dla testów
                task_info = session['task_info']
                discord_id = str(member.id)

                # Formatowanie czasu dla powiadomienia użytkownika
                hours = int(duration_minutes // 60)
                minutes = int(duration_minutes % 60)

                time_spent_text = ""
                if hours > 0:
                    time_spent_text += f"{hours}h "
                if minutes > 0 or time_spent_text == "":
                    time_spent_text += f"{minutes}m"

                # Sprawdź, czy użytkownik Discord ma mapowanie do użytkownika JIRA
                jira_account_id = None
                if discord_id in user_mappings:
                    jira_account_id = user_mappings[discord_id]

                if jira_account_id:
                    print(
                        f"Próba dodania czasu: {time_spent_text} do zadania {task_info['zadanie']} jako {jira_account_id}")

                    # Opis z rzeczywistym czasem
                    description = f"Auto log Discord - kanał: {before.channel.name} ({start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')})"

                    # Loguj czas przez Tempo API z rzeczywistym czasem startu
                    result = log_time_via_tempo(
                        task_info['zadanie'],
                        jira_account_id,
                        duration_seconds,
                        start_time,  # Przekazujemy rzeczywisty czas startu
                        description
                    )

                    if result:
                        # Powiadom użytkownika o sukcesie
                        await member.send(
                            f"Zarejestrowano {time_spent_text} w zadaniu {task_info['zadanie']} projektu {task_info['projekt']} "
                            f"({start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')})"
                        )
                    else:
                        # Próba alternatywna - standardowe API JIRA
                        try:
                            # Ustaw rzeczywisty czas startu
                            started = start_time.strftime("%Y-%m-%d %H:%M:%S")

                            worklog = jira.add_worklog(
                                issue=task_info['zadanie'],
                                timeSpent=time_spent_text,
                                started=started,  # Używamy rzeczywistego czasu startu
                                comment=f"Auto log Discord dla {member.name} - kanał: {before.channel.name} ({start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')})"
                            )

                            print(f"Dodano worklog do JIRA z komentarzem o użytkowniku {member.name}")

                            await member.send(
                                f"Zarejestrowano {time_spent_text} w zadaniu {task_info['zadanie']} projektu {task_info['projekt']} "
                                f"({start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}) - "
                                f"rejestracja przez standardowe API z informacją o tobie w komentarzu"
                            )
                        except Exception as e:
                            await member.send(
                                f"Nie udało się zalogować czasu: {str(e)}"
                            )
                else:
                    # Użytkownik nie ma mapowania do JIRA
                    try:
                        # Ustaw rzeczywisty czas startu
                        started = start_time.strftime("%Y-%m-%d %H:%M:%S")

                        worklog = jira.add_worklog(
                            issue=task_info['zadanie'],
                            timeSpent=time_spent_text,
                            started=started,  # Używamy rzeczywistego czasu startu
                            comment=f"Auto log Discord dla {member.name} - kanał: {before.channel.name} ({start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')})"
                        )

                        print(f"Dodano worklog do JIRA z komentarzem o użytkowniku Discord {member.name}")

                        # Powiadom użytkownika
                        await member.send(
                            f"Zarejestrowano {time_spent_text} w zadaniu {task_info['zadanie']} projektu {task_info['projekt']} "
                            f"({start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')}). "
                            f"Nie znaleziono mapowania twojego konta Discord do konta JIRA."
                        )
                    except Exception as e:
                        error_message = f"Błąd rejestracji czasu w JIRA: {str(e)}"
                        print(error_message)
                        await member.send(error_message)
            else:
                print(f"Nie dodano worklogu: czas zbyt krótki ({duration_minutes} min)")

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
    for discord_id, jira_account_id in user_mappings.items():
        # Spróbuj znaleźć użytkownika Discord
        discord_name = "Nieznany"
        for guild in bot.guilds:
            user = guild.get_member(int(discord_id))
            if user:
                discord_name = user.name
                break

        message += f"- Discord: {discord_name} ({discord_id}), JIRA Account ID: {jira_account_id}\n"

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


# Inicjalizacja serwera Flask
app = Flask(__name__)


# Zaktualizowana obsługa webhooków
@app.route('/webhook/voice-activity', methods=['POST'])
def voice_activity_webhook():
    data = request.json

    user_id = data.get('user_id')
    channel_id = data.get('channel_id')
    duration_minutes = data.get('duration_minutes')

    # Sprawdź czy mamy mapowanie dla tego kanału
    if channel_id in channel_tasks:
        task_info = channel_tasks[channel_id]
        duration_seconds = int(duration_minutes * 60)

        # Oblicz przybliżony czas rozpoczęcia (teraz - czas trwania)
        start_time = datetime.now() - timedelta(minutes=duration_minutes)
        end_time = datetime.now()

        # Próba użycia standardowego API JIRA (fallback)
        try:
            # Formatowanie czasu dla JIRA
            time_spent = f"{duration_minutes}m"

            # Używamy rzeczywistego czasu startu
            started = start_time.strftime("%Y-%m-%d %H:%M:%S")

            # Dodajemy informacje o czasie
            description = f"Auto log Discord - kanał: {data.get('channel_name', 'Kanał Discord')} ({start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')})"

            jira.add_worklog(
                issue=task_info['zadanie'],
                timeSpent=time_spent,
                started=started,  # Używamy obliczonego czasu startu
                comment=description
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