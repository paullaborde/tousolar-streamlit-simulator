"""
Simulateur Tousolar sur Streamlit

Simuler sa production solaire vs sa consommation réelle extraite d'Enedis

https://tousolar.com

v0.3
18 Juin 2024

Author:
    paullaborde@laposte.net
"""

import streamlit as st
import pandas as pd
from io import StringIO
import requests

# ------------------------------------------------------
# Init
# ------------------------------------------------------

st.set_page_config(
     page_title='Simulateur Tousolar',
     layout="wide",
     initial_sidebar_state="expanded",
)

st.title(':blue[Tousolar]')
st.logo('icon.webp')

data = pd.DataFrame([{'datetime':0, 'production_1kwc':0, 'production_3kwc':0,'production_6kwc':0, 'production_9kwc':0, 'consommation':0}])

# ------------------------------------------------------
# 1. Conso
# ------------------------------------------------------
st.header('1. Consommation réelle', divider='rainbow')

uploaded_file = st.file_uploader("Chargez votre consommation réelle depuis https://mon-compte-particulier.enedis.fr/")
if uploaded_file is not None:
    tmp_conso = pd.read_csv(uploaded_file, sep=';', header=2)
    tmp_conso['dt_noz'] = tmp_conso.Horodate.str[:-6]
    tmp_conso['datetime'] = pd.to_datetime(tmp_conso['dt_noz'], format='%Y-%m-%dT%H:%M:%S')
    tmp_conso['year'] = pd.DatetimeIndex(tmp_conso['datetime']).year
    tmp_conso['month'] = pd.DatetimeIndex(tmp_conso['datetime']).month
    tmp_conso['day'] = pd.DatetimeIndex(tmp_conso['datetime']).day
    tmp_conso['hour'] = pd.DatetimeIndex(tmp_conso['datetime']).hour
    tmp_conso['minute'] = pd.DatetimeIndex(tmp_conso['datetime']).minute
    
    tmp_conso.rename(columns={'Valeur': 'consumption'}, inplace=True)
    tmp_conso.drop(columns=['datetime', 'dt_noz', 'Horodate'], inplace=True)

    grouped = tmp_conso.groupby(['year', 'month', 'day', 'hour']).sum()/2 # 30MIN data is an average, when summed it needs to be averaged on hour
    sum = grouped.to_dict()
    df_conso = pd.DataFrame([{'year':x[0], 'month':x[1], 'day':x[2], 'hour':x[3], 'consommation':sum['consumption'][x]} for x in sum['consumption']])

# ------------------------------------------------------
# 2. Address
# ------------------------------------------------------
st.header('2. Emplacement projet solaire', divider='rainbow')

address = st.text_input("Indiquez l'adresse du projet")

url_geocoding = f'https://api.mapbox.com/geocoding/v5/mapbox.places/{address}.json?&access_token={st.secrets["mapbox_token"]}'
r = requests.get(url_geocoding)
results = r.json()

if len(results['features']) >0:
    feature = results['features'][0]
    tmp_lat = feature["center"][1]
    tmp_lng = feature["center"][0]

    url_insight = f'https://solar.googleapis.com/v1/buildingInsights:findClosest?location.latitude={tmp_lat}&location.longitude={tmp_lng}&requiredQuality=HIGH&key={st.secrets["google_solarapi_key"]}'

    r = requests.get(url_insight)
    results = r.json()

    if 'solarPotential' in results:
        roof_segments = len(results['solarPotential']['roofSegmentStats'])
        tmp_pitch = results['solarPotential']['roofSegmentStats'][0]['pitchDegrees']
        tmp_azimuth = results['solarPotential']['roofSegmentStats'][0]['azimuthDegrees']

        st.markdown(f"- Adresse identifiée : **:red[{feature['place_name']}]**" )
        st.markdown(f'- Nombre de pan de toiture exploitables : **:red[{roof_segments}]**')
        st.markdown(f'- Pente du pan principal : **:red[{int(tmp_pitch)}°]**')
        st.markdown(f'- Orientation du pan principal : **:red[{int(tmp_azimuth)}°]**')


        data_map = pd.DataFrame({
            'latitude': [tmp_lat],
            'longitude': [tmp_lng]
        })
        
        st.map(data_map, zoom=17)

    else:
        st.write('Erreur de récupération des informations solaire à cette adresse')

# ------------------------------------------------------
# 3. Production
# ------------------------------------------------------
st.header('3. Simuler la production solaire', divider='rainbow')

if st.button("Lancer la simulation"):
    with st.status("Simulation production ...", expanded=True) as status:
        st.write(f'Requête PVGIS sur {tmp_lat}/{tmp_lng}')
        url = f"https://re.jrc.ec.europa.eu/api/v5_2/seriescalc?lat={tmp_lat}&lon={tmp_lng}&raddatabase=PVGIS-SARAH&pvcalculation=1&peakpower=1.0&loss=14.0&angle={tmp_pitch}&aspect={tmp_azimuth}&outputformat=json"
        r = requests.get(url)
        result = r.json()
        
        # Mean per hour on years
        st.write('Mise en forme des données')
        tmp_pvgis = pd.DataFrame(result['outputs']['hourly'])            
        tmp_pvgis['datetime'] = pd.to_datetime(tmp_pvgis['time'], format='%Y%m%d:%H%M')
        tmp_pvgis['month'] = pd.DatetimeIndex(tmp_pvgis['datetime']).month
        tmp_pvgis['day'] = pd.DatetimeIndex(tmp_pvgis['datetime']).day
        tmp_pvgis['hour'] = pd.DatetimeIndex(tmp_pvgis['datetime']).hour
        tmp_pvgis['minute'] = pd.DatetimeIndex(tmp_pvgis['datetime']).minute

        # mean power over years
        tmp_pvgis.drop(columns=['time', 'G(i)', 'H_sun', 'T2m', 'WS10m', 'Int'], inplace=True)
        tmp_pvgis.rename(columns={'P': 'production'}, inplace=True)
        mean = tmp_pvgis.groupby(['month', 'day', 'hour', 'minute']).mean().to_dict()
        df_prod = pd.DataFrame([{'month':x[0], 'day':x[1], 'hour':x[2], 'minute':x[3], 'production_1kwc':mean['production'][x]} for x in mean['production']])

        data = pd.merge(df_conso, df_prod, 'left')
        data['dt_txt'] = data.year.astype(str) + '/' + data.month.astype(str) + '/' + data.day.astype(str) + ' ' + data.hour.astype(str) + ':' + data.minute.astype(str)
        data['datetime'] = pd.to_datetime(data['dt_txt'], format='%Y/%m/%d %H:%M')
        data.drop(columns=['year', 'month', 'day', 'hour', 'minute', 'dt_txt'], inplace=True)

        for i in [3,6,9]:
            data[f'production_{i}kwc'] = data['production_1kwc'] * i

        status.update(label="Données de production prêtes", state="complete", expanded=False)

# ------------------------------------------------------
# 4. Results
# ------------------------------------------------------
st.header('4. Résultat', divider='rainbow')

st.line_chart(data, x='datetime', y=['production_1kwc', 'production_3kwc', 'production_6kwc', 'production_9kwc', 'consommation'], color=["#FFFF00", "#FFAA00", "#FF5500", "#FF0000", "#4D4DFF"])

st.write('Données brutes :')
st.write(data)