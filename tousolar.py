"""
Simulateur Tousolar sur Streamlit

Simuler sa production solaire vs sa consommation réelle extraite d'Enedis

https://tousolar.com

v0.2
15 Juin 2024

Author:
    paul.laborde@laposte.net
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

# ------------------------------------------------------
# 1. Conso
# ------------------------------------------------------
st.text('1. Consommation réelle')

uploaded_file = st.file_uploader("Chargez votre consommation réelle depuis https://mon-compte-particulier.enedis.fr/")
if uploaded_file is not None:
    
    # WORK ON conso data need to be linearized from 30 min to 1h, year can be kept

    df_conso = pd.read_csv(uploaded_file, sep=';', header=2)
    df_conso['datetime'] = pd.to_datetime(df_conso['Horodate'], format='%Y-%m-%dT%H:%M:%S%z', utc=True) # CHECK utc parameter !
    df_conso.drop(columns=['Horodate'], inplace=True)
    df_conso.rename(columns={'Valeur': 'consommation'}, inplace=True)

    st.write(df_conso)

# ------------------------------------------------------
# 2. Address
# ------------------------------------------------------
st.text('2. Emplacement projet solaire')

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

    roof_segments = len(results['solarPotential']['roofSegmentStats'])
    tmp_pitch = results['solarPotential']['roofSegmentStats'][0]['pitchDegrees']
    tmp_azimuth = results['solarPotential']['roofSegmentStats'][0]['azimuthDegrees']

    st.write('Adresse trouvée :', feature['place_name'])
    st.write(f'Nombre de pan de toiture exploitables : {roof_segments}')
    st.write(f'Pente du pan principal : {int(tmp_pitch)}°')
    st.write(f'Orientation du pan principal : {int(tmp_azimuth)}°')


    data = pd.DataFrame({
        'latitude': [tmp_lat],
        'longitude': [tmp_lng]
    })
    
    st.map(data, zoom=17)


# ------------------------------------------------------
# 3. Production
# ------------------------------------------------------
    st.button("Calculer la production ici", type="primary")

    if st.button("Calculer la production ici"):

        with st.status("Simulation production ...", expanded=True) as status:
            st.write(f'Requête PVGIS sur {tmp_lat}/{tmp_lng}')
            url = f"https://re.jrc.ec.europa.eu/api/v5_2/seriescalc?lat={tmp_lat}&lon={tmp_lng}&raddatabase=PVGIS-SARAH&pvcalculation=1&peakpower=1.0&loss=14.0&angle={tmp_pitch}&aspect={tmp_azimuth}&outputformat=json"
            r = requests.get(url)
            result = r.json()

            #  WORK ON Production data --> data over years need to be meaned and year remove from data set
            
            # Mean per hour on years
            st.write('Mise en forme des données')
            df_prod = pd.DataFrame(result['outputs']['hourly'])            
            df_prod['datetime'] = pd.to_datetime(df_prod['time'], format='%Y%m%d:%H%M', utc=True)
            # tmp_pvgis['month'] = pd.DatetimeIndex(tmp_pvgis['datetime']).month
            # tmp_pvgis['day'] = pd.DatetimeIndex(tmp_pvgis['datetime']).day
            # tmp_pvgis['hour'] = pd.DatetimeIndex(tmp_pvgis['datetime']).hour
            # tmp_pvgis['minute'] = pd.DatetimeIndex(tmp_pvgis['datetime']).minute

            # mean power over years
            df_prod.drop(columns=['time', 'G(i)', 'H_sun', 'T2m', 'WS10m', 'Int'], inplace=True)
            df_prod.rename(columns={'P': 'production'}, inplace=True)
            df_prod.resample('60min', on='datetime').sum()

            # mean = tmp_pvgis.groupby(['month', 'day', 'hour', 'minute']).mean().to_dict()
            # df_prod = pd.DataFrame([{'month':x[0], 'day':x[1], 'hour':x[2], 'minute':x[3], 'power':mean['production'][x]} for x in mean['production']])

            data = pd.merge(df_conso, df_prod, 'left') # could be ok with right dataframes

            status.update(label="Données de production prêtes", state="complete", expanded=False)
        st.write('3. Simulation de production par heure pour 1 panneau')
        st.write(data)