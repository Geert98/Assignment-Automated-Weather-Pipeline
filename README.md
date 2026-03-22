# Assignment-Automated-Weather-Pipeline

This project is a small end-to-end automated data pipeline built for Assignment 1.

It collects tomorrow’s weather forecast for three locations using the Open-Meteo API, stores the results in a local SQLite database, generates a short bilingual poem using the Groq API, and publishes the output as a GitHub Pages website.

## Features

- Fetches weather forecast data for three locations
- Uses multiple weather variables such as temperature, precipitation, wind speed, cloud cover, and humidity
- Stores forecast summaries in a SQLite database
- Generates a bilingual poem based on the weather data
- Updates a GitHub Pages site automatically
- Runs daily using GitHub Actions

## Technologies Used

- Python
- Open-Meteo API
- SQLite
- Groq API
- GitHub Actions
- GitHub Pages

## Project Structure

```text
.github/workflows/weather.yml   # GitHub Actions workflow
data/weather.db                 # SQLite database
docs/index.html                 # Generated GitHub Pages site
fetch.py                        # Main pipeline script
requirements.txt                # Python dependencies
README.md                       # Project description
