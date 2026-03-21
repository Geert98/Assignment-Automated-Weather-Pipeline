import os
import sqlite3
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

load_dotenv()

# ----------------------------
# Config
# ----------------------------

DB_PATH = "data/weather.db"
HTML_PATH = "docs/index.html"

# Replace these with your real locations
LOCATIONS = [
    {"name": "Place of Birth", "latitude": 57.0488, "longitude": 9.9217},
    {"name": "Last Residence Before Aalborg", "latitude": 55.4765, "longitude": 8.4594},
    {"name": "Aalborg", "latitude": 57.0488, "longitude": 9.9217},
]

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.3-70b-versatile"


# ----------------------------
# Helpers
# ----------------------------

def ensure_directories():
    os.makedirs("data", exist_ok=True)
    os.makedirs("docs", exist_ok=True)


def get_tomorrow_date():
    dk_now = datetime.now(ZoneInfo("Europe/Copenhagen"))
    tomorrow = dk_now.date() + timedelta(days=1)
    return tomorrow.isoformat()


def fetch_weather_for_location(location, target_date):
    params = {
        "latitude": location["latitude"],
        "longitude": location["longitude"],
        "timezone": "Europe/Copenhagen",
        "start_date": target_date,
        "end_date": target_date,
        "hourly": [
            "temperature_2m",
            "precipitation_probability",
            "precipitation",
            "wind_speed_10m",
            "cloud_cover",
            "relative_humidity_2m",
        ],
    }

    response = requests.get(OPEN_METEO_URL, params=params, timeout=60)
    response.raise_for_status()
    data = response.json()

    hourly = data["hourly"]

    temperatures = hourly["temperature_2m"]
    precipitation_probabilities = hourly["precipitation_probability"]
    precipitation = hourly["precipitation"]
    wind_speeds = hourly["wind_speed_10m"]
    cloud_cover = hourly["cloud_cover"]
    humidity = hourly["relative_humidity_2m"]

    return {
        "location_name": location["name"],
        "forecast_date": target_date,
        "temp_mean": round(sum(temperatures) / len(temperatures), 2),
        "temp_max": round(max(temperatures), 2),
        "temp_min": round(min(temperatures), 2),
        "precipitation_total": round(sum(precipitation), 2),
        "precipitation_probability_mean": round(
            sum(precipitation_probabilities) / len(precipitation_probabilities), 2
        ),
        "wind_speed_mean": round(sum(wind_speeds) / len(wind_speeds), 2),
        "cloud_cover_mean": round(sum(cloud_cover) / len(cloud_cover), 2),
        "humidity_mean": round(sum(humidity) / len(humidity), 2),
    }


# ----------------------------
# Database
# ----------------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS weather_forecasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_name TEXT NOT NULL,
            forecast_date TEXT NOT NULL,
            temp_mean REAL,
            temp_max REAL,
            temp_min REAL,
            precipitation_total REAL,
            precipitation_probability_mean REAL,
            wind_speed_mean REAL,
            cloud_cover_mean REAL,
            humidity_mean REAL,
            created_at TEXT NOT NULL,
            UNIQUE(location_name, forecast_date)
        )
    """)

    conn.commit()
    return conn


def save_forecast(conn, forecast_row):
    cur = conn.cursor()

    cur.execute("""
        INSERT OR REPLACE INTO weather_forecasts (
            location_name,
            forecast_date,
            temp_mean,
            temp_max,
            temp_min,
            precipitation_total,
            precipitation_probability_mean,
            wind_speed_mean,
            cloud_cover_mean,
            humidity_mean,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        forecast_row["location_name"],
        forecast_row["forecast_date"],
        forecast_row["temp_mean"],
        forecast_row["temp_max"],
        forecast_row["temp_min"],
        forecast_row["precipitation_total"],
        forecast_row["precipitation_probability_mean"],
        forecast_row["wind_speed_mean"],
        forecast_row["cloud_cover_mean"],
        forecast_row["humidity_mean"],
        datetime.now(ZoneInfo("Europe/Copenhagen")).isoformat()
    ))

    conn.commit()


# ----------------------------
# Poem logic
# ----------------------------

def score_location(row):
    # Higher score = nicer weather
    # Warm weather is rewarded, while rain/wind/cloud cover are penalized
    return (
        row["temp_mean"] * 1.5
        - row["precipitation_total"] * 2.0
        - row["wind_speed_mean"] * 0.4
        - row["cloud_cover_mean"] * 0.03
    )


def choose_best_location(rows):
    best = max(rows, key=score_location)
    return best["location_name"]


def build_weather_summary(rows):
    lines = []
    for row in rows:
        lines.append(
            f"{row['location_name']}: "
            f"mean temperature {row['temp_mean']}°C, "
            f"max {row['temp_max']}°C, "
            f"min {row['temp_min']}°C, "
            f"precipitation {row['precipitation_total']} mm, "
            f"precipitation probability {row['precipitation_probability_mean']}%, "
            f"wind {row['wind_speed_mean']} km/h, "
            f"cloud cover {row['cloud_cover_mean']}%, "
            f"humidity {row['humidity_mean']}%."
        )
    return "\n".join(lines)


def generate_fallback_poem(rows):
    best_location = choose_best_location(rows)

    return f"""English:
Three towns await tomorrow's sky,
One warm, one wet, one windswept high.
Through cloud and rain the forecast streams,
But {best_location} shines in softer dreams.

Dansk:
Tre steder møder morgendagens vejr,
med skyer og regn og vindens skær.
Men {best_location} ser bedst ud i morgen,
med dagens lys og mindre vejr-uro i borgen."""


def generate_poem_with_groq(rows):
    if not GROQ_API_KEY:
        return generate_fallback_poem(rows)

    best_location = choose_best_location(rows)
    weather_summary = build_weather_summary(rows)

    prompt = f"""
Write a short poem in two languages:
1. English
2. Danish

Requirements:
- Compare tomorrow's weather in the three locations
- Mention differences in temperature, rain, and wind
- Suggest where it would be nicest to be tomorrow
- Keep it short, vivid, and elegant
- Clearly label the English and Danish versions

Weather summary:
{weather_summary}

Based on the weather data, the nicest place to be tomorrow is probably: {best_location}
"""

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": GROQ_MODEL,
        "temperature": 0.7,
        "messages": [
            {
                "role": "system",
                "content": "You are a creative assistant who writes concise bilingual weather poems."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

    response = requests.post(GROQ_URL, headers=headers, json=payload, timeout=120)
    response.raise_for_status()
    data = response.json()

    return data["choices"][0]["message"]["content"]


# ----------------------------
# HTML generation
# ----------------------------

def build_html(rows, poem, forecast_date):
    table_rows = []
    for row in rows:
        table_rows.append(f"""
        <tr>
            <td>{row['location_name']}</td>
            <td>{row['temp_mean']} °C</td>
            <td>{row['temp_max']} °C</td>
            <td>{row['temp_min']} °C</td>
            <td>{row['precipitation_total']} mm</td>
            <td>{row['precipitation_probability_mean']} %</td>
            <td>{row['wind_speed_mean']} km/h</td>
            <td>{row['cloud_cover_mean']} %</td>
            <td>{row['humidity_mean']} %</td>
        </tr>
        """)

    poem_html = poem.replace("\n", "<br>")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Automated Weather Pipeline</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 950px;
            margin: 40px auto;
            padding: 20px;
            background: #f8fafc;
            color: #1e293b;
            line-height: 1.6;
        }}
        h1, h2 {{
            color: #0f172a;
        }}
        .card {{
            background: white;
            padding: 20px;
            border-radius: 14px;
            box-shadow: 0 4px 16px rgba(0,0,0,0.08);
            margin-bottom: 24px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 12px;
        }}
        th, td {{
            border: 1px solid #cbd5e1;
            padding: 10px;
            text-align: left;
        }}
        th {{
            background: #e2e8f0;
        }}
        .footer {{
            margin-top: 24px;
            font-size: 0.9rem;
            color: #475569;
        }}
    </style>
</head>
<body>
    <h1>Automated Weather Pipeline</h1>
    <p>Forecast for <strong>{forecast_date}</strong></p>

    <div class="card">
        <h2>Bilingual Weather Poem</h2>
        <p>{poem_html}</p>
    </div>

    <div class="card">
        <h2>Weather Summary</h2>
        <table>
            <thead>
                <tr>
                    <th>Location</th>
                    <th>Mean Temp</th>
                    <th>Max Temp</th>
                    <th>Min Temp</th>
                    <th>Total Rain</th>
                    <th>Rain Probability</th>
                    <th>Mean Wind</th>
                    <th>Cloud Cover</th>
                    <th>Humidity</th>
                </tr>
            </thead>
            <tbody>
                {''.join(table_rows)}
            </tbody>
        </table>
    </div>

    <div class="footer">
        Generated automatically using Open-Meteo, SQLite, Groq, GitHub Actions, and GitHub Pages.
    </div>
</body>
</html>
"""


# ----------------------------
# Main pipeline
# ----------------------------

def main():
    ensure_directories()
    target_date = get_tomorrow_date()

    forecasts = []
    for location in LOCATIONS:
        forecast = fetch_weather_for_location(location, target_date)
        forecasts.append(forecast)

    conn = init_db()
    for forecast in forecasts:
        save_forecast(conn, forecast)
    conn.close()

    poem = generate_poem_with_groq(forecasts)
    html = build_html(forecasts, poem, target_date)

    with open(HTML_PATH, "w", encoding="utf-8") as file:
        file.write(html)

    print("Pipeline completed successfully.")
    print(f"Database updated: {DB_PATH}")
    print(f"HTML updated: {HTML_PATH}")


if __name__ == "__main__":
    main()