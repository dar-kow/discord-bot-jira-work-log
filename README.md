# Discord JIRA Time Tracker Bot

[Polska wersja instrukcji](#discord-bot-do-śledzenia-czasu-w-jira)

A Discord bot that automatically tracks time spent in voice channels and logs it to JIRA tasks.

## Features

- Automatic time tracking when users join/leave voice channels
- Integration with JIRA for logging work time
- Support for two different logging methods:
  - Direct JIRA time logging
  - Tempo API integration for advanced time tracking
- User mapping between Discord and JIRA accounts
- Command-based management of tasks and voice channels
- RESTful webhook endpoints for external integrations

## Available Versions

1. **Standard JIRA Time Tracker** (`bot-jira-time-tracker.py`) - Uses standard JIRA API for work logging
2. **JIRA with Tempo** (`bot.py`) - Uses Tempo API for more advanced time tracking features

## Setup Instructions

### Prerequisites

- Python 3.8+
- Discord Bot Token
- JIRA Account with API access
- Tempo API Token (only for the Tempo version)

### Installation

1. Clone this repository
2. Install the required packages:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the root directory with the following content:
   ```
   DISCORD_BOT_TOKEN=your_discord_bot_token
   JIRA_SERVER=https://your_domain.atlassian.net
   JIRA_EMAIL=your_email@example.com
   JIRA_API_TOKEN=your_jira_api_token
   TEMPO_API_TOKEN=your_tempo_api_token
   TEMPO_API_BASE=https://api.tempo.io/api
   ```

### Running the Bot

#### Standard JIRA Version
```bash
python bot-jira-time-tracker.py
```

#### Tempo Version
```bash
python bot.py
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `!set_task <channel_id> <project> <issue>` | Map a voice channel to a JIRA task |
| `!show_tasks` | Show all channel-task mappings |
| `!remove_task <channel_id>` | Remove a channel-task mapping |
| `!map_user <@discord_user> <jira_account_id>` | Map a Discord user to a JIRA account |
| `!show_mappings` | Show all user mappings |
| `!reload_config` | Reload configuration from files |
| `!test_jira` | Test JIRA connectivity |
| `!get_account_id` | Get your JIRA Account ID |
| `!find_jira_account_id <search_term>` | Find a JIRA user's Account ID |
| `!test_tempo_connection` | Test Tempo API connectivity (Tempo version only) |

## How It Works

1. The bot listens for users joining/leaving voice channels
2. When a user joins a mapped channel, tracking begins
3. When the user leaves, the time spent is calculated and logged to the appropriate JIRA task
4. If user mapping exists, time is logged as the specific JIRA user

## Configuration Files

- **config.json** - Contains user mappings between Discord and JIRA accounts
- **tasks.json** - Contains mappings between Discord voice channels and JIRA tasks

---

# Discord Bot do śledzenia czasu w JIRA

Bot Discord, który automatycznie śledzi czas spędzony na kanałach głosowych i loguje go do zadań w JIRA.

## Funkcje

- Automatyczne śledzenie czasu, gdy użytkownicy dołączają/opuszczają kanały głosowe
- Integracja z JIRA do logowania czasu pracy
- Obsługa dwóch różnych metod logowania:
  - Bezpośrednie logowanie czasu w JIRA
  - Integracja z API Tempo dla zaawansowanego śledzenia czasu
- Mapowanie użytkowników między kontami Discord i JIRA
- Zarządzanie zadaniami i kanałami głosowymi za pomocą komend
- Endpointy webhook RESTful dla integracji zewnętrznych

## Dostępne wersje

1. **Standardowy tracker czasu JIRA** (`bot-jira-time-tracker.py`) - Używa standardowego API JIRA do logowania pracy
2. **JIRA z Tempo** (`bot.py`) - Używa API Tempo dla bardziej zaawansowanych funkcji śledzenia czasu

## Instrukcja instalacji

### Wymagania wstępne

- Python 3.8+
- Token bota Discord
- Konto JIRA z dostępem do API
- Token API Tempo (tylko dla wersji Tempo)

### Instalacja

1. Sklonuj to repozytorium
2. Zainstaluj wymagane pakiety:
   ```bash
   pip install -r requirements.txt
   ```
3. Utwórz plik `.env` w głównym katalogu z następującą zawartością:
   ```
   DISCORD_BOT_TOKEN=twój_token_bota_discord
   JIRA_SERVER=https://twoja_domena.atlassian.net
   JIRA_EMAIL=twój_email@example.com
   JIRA_API_TOKEN=twój_token_api_jira
   TEMPO_API_TOKEN=twój_token_api_tempo
   TEMPO_API_BASE=https://api.tempo.io/api
   ```

### Uruchamianie bota

#### Wersja standardowa JIRA
```bash
python bot-jira-time-tracker.py
```

#### Wersja z Tempo
```bash
python bot.py
```

## Komendy bota

| Komenda | Opis |
|---------|------|
| `!set_task <id_kanału> <projekt> <zadanie>` | Przypisz kanał głosowy do zadania JIRA |
| `!show_tasks` | Pokaż wszystkie mapowania kanałów do zadań |
| `!remove_task <id_kanału>` | Usuń mapowanie kanału do zadania |
| `!map_user <@użytkownik_discord> <id_konta_jira>` | Przypisz użytkownika Discord do konta JIRA |
| `!show_mappings` | Pokaż wszystkie mapowania użytkowników |
| `!reload_config` | Przeładuj konfigurację z plików |
| `!test_jira` | Przetestuj połączenie z JIRA |
| `!get_account_id` | Pobierz swoje ID konta JIRA |
| `!find_jira_account_id <termin_wyszukiwania>` | Znajdź ID konta użytkownika JIRA |
| `!test_tempo_connection` | Przetestuj połączenie z API Tempo (tylko wersja Tempo) |

## Jak to działa

1. Bot nasłuchuje użytkowników dołączających/opuszczających kanały głosowe
2. Gdy użytkownik dołącza do zmapowanego kanału, rozpoczyna się śledzenie
3. Gdy użytkownik opuszcza kanał, obliczany jest spędzony czas i logowany do odpowiedniego zadania JIRA
4. Jeśli istnieje mapowanie użytkownika, czas jest logowany jako określony użytkownik JIRA

## Pliki konfiguracyjne

- **config.json** - Zawiera mapowania użytkowników między kontami Discord i JIRA
- **tasks.json** - Zawiera mapowania między kanałami głosowymi Discord a zadaniami JIRA