from flask import Flask, render_template, request, jsonify
import numpy as np
import requests
import math
import folium
from folium.plugins import MarkerCluster
import json

app = Flask(__name__)

# Configuration
TOMORROW_API_KEY = "c5aYu8Y6ED2HRQX3SedtGfaWByzPQEpS"

def get_location_coordinates(location_name):
    url = "https://nominatim.openstreetmap.org/search"
    params = {
        "q": location_name,
        "format": "json",
        "limit": 1
    }
    headers = {
        "User-Agent": "FlaskApp-Geocoder/1.0 (pravakshay@gmail.com)"
    }
    
    try:
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            data = response.json()
            if data:
                return float(data[0]["lat"]), float(data[0]["lon"])
        return None
    except Exception as e:
        print(f"Error getting coordinates: {e}")
        return None

def get_weather_data(coordinates):
    url = "https://api.tomorrow.io/v4/weather/forecast"
    params = {
        "location": f"{coordinates[0]},{coordinates[1]}",
        "apikey": TOMORROW_API_KEY
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            return response.json()
        return None
    except Exception as e:
        print(f"Error getting weather data: {e}")
        return None

def calculate_seeding_probability(T, S_w, rho, N_IN, N_aerosol, D_ice, D_crit, k):
    # Constants
    T_opt = -10
    sigma_T = 5
    b = 2
    TinK = T + 273.15
    
    # Temperature-dependent nucleation efficiency
    if T > -4 or T < -20:
        f_T = 0
    else:
        f_T = math.exp(-((T - T_opt) ** 2) / (sigma_T ** 2))
    
    # Supersaturation effect
    if S_w < 0.01:
        g_Sw = 0
    else:
        g_Sw = S_w ** b
    
    # Ice crystal number concentration
    N_ice = N_IN * f_T * g_Sw
    
    # Maximum potential ice crystal concentration
    N_max = N_aerosol * min(S_w, 1.5)
    
    # Seeding probability
    if N_max == 0 or D_crit == 0:
        P_seed = 0
    else:
        P_seed = (N_ice * D_ice) / (N_max * D_crit) * k
    
    return {
        'f_T': f_T,
        'g_Sw': g_Sw,
        'N_ice': N_ice,
        'N_max': N_max,
        'P_seed': P_seed
    }

def create_map(coordinates, results):
    m = folium.Map(location=coordinates, zoom_start=10)
    marker_cluster = MarkerCluster().add_to(m)
    
    # Add marker with results
    color = 'red'
    if results['P_seed'] >= 0.7:
        color = 'blue'
    elif results['P_seed'] >= 0.5:
        color = 'green'
    elif results['P_seed'] >= 0.3:
        color = 'yellow'
    elif results['P_seed'] >= 0.1:
        color = 'orange'
    
    popup_content = f"""
        Cloud Seeding Probability: {results['P_seed']:.4f}<br>
        Nucleation efficiency: {results['f_T']:.4f}<br>
        Supersaturation effect: {results['g_Sw']:.4f}<br>
        Ice crystal concentration: {results['N_ice']:.2f} per m³<br>
        Maximum ice crystal potential: {results['N_max']:.2f} per m³
    """
    
    folium.CircleMarker(
        location=coordinates,
        radius=8,
        color=color,
        fill=True,
        fill_color=color,
        fill_opacity=0.6,
        popup=popup_content
    ).add_to(marker_cluster)
    
    return m._repr_html_()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    location = data.get('location')
    
    # Get coordinates
    coordinates = get_location_coordinates(location)
    if not coordinates:
        return jsonify({'error': 'Location not found'}), 404
    
    # Get weather data
    weather_data = get_weather_data(coordinates)
    if not weather_data:
        return jsonify({'error': 'Weather data not available'}), 404
    
    # Calculate seeding probability
    calculation_params = {
        'T': float(data.get('temperature', 0)),
        'S_w': float(data.get('supersaturation', 0.02)),
        'rho': float(data.get('airDensity', 1.225)),
        'N_IN': float(data.get('iceNuclei', 1000)),
        'N_aerosol': float(data.get('aerosolConc', 10000)),
        'D_ice': float(data.get('iceDiameter', 50)),
        'D_crit': float(data.get('criticalDiameter', 20)),
        'k': float(data.get('calibration', 1.0))
    }
    
    results = calculate_seeding_probability(**calculation_params)
    
    # Create map HTML
    map_html = create_map(coordinates, results)
    
    return jsonify({
        'coordinates': coordinates,
        'weather_data': weather_data,
        'results': results,
        'map_html': map_html
    })

if __name__ == '__main__':
    app.run(debug=True)