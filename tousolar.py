import streamlit as st
import pandas as pd
from io import StringIO


# https://mon-compte-particulier.enedis.fr/



uploaded_file = st.file_uploader("Enedis real conso file")
if uploaded_file is not None:
    df = pd.read_csv(uploaded_file, sep=';')

    st.write(df)