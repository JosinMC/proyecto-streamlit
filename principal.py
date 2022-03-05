# Aplicación desarrollada en Streamlit para visualización de la red vial costarricense
# Autor: Josin Madrigal Corrales - B43939
# Fecha de creación: 2022-03-04


import pandas as pd

import matplotlib.pyplot as plt

import plotly.express as px
import plotly.graph_objects as go

import geopandas as gpd
from pyproj import Geod

import folium

import streamlit as st
from streamlit_folium import folium_static


#
# Configuración de la página
#
st.set_page_config(layout='wide')

#
# TÍTULO Y DESCRIPCIÓN DE LA APLICACIÓN
#

st.title('Proyecto - Desarrollo de tablero de datos en Streamlit')
st.markdown('**Universidad de Costa Rica**')
st.markdown('**PF3311 - Ciencia de datos geoespaciales**')
st.markdown('**Josin Madrigal Corrales - B43939**')

st.markdown('Este trabajo presenta un análisis de la red vial costarricense usando salidas tabulares, gráficas y geoespaciales. Para esto se emplean los paquetes pandas, plotly, geopandas y folium de Python.')

st.markdown('El codigo fuente está disponible en Github: https://github.com/JosinMC/proyecto-streamlit')


st.subheader('Fuente de datos')

st.markdown('- Capas geoespaciales de Costa Rica agrupadas por el Sistema Nacional de Información Territorial (SNIT).')
st.markdown('Las capas descargadas del SNIT son las siguientes:')

st.markdown('- Capa de límite cantonal (IGN_5:limitecantonal_5k)')
st.markdown('- Capa red vial (IGN_200:redvial_200k)')
st.markdown('Estas fueron previamente descargadas en archivos geojson y se hicieron disponibles en el repositorio de Github para facilidad de manipulación. El CRS de las capas es EPSG:4326.')

st.subheader('Referencias')
st.markdown('Este código está basado en el siguiente notebook: https://github.com/mfvargas/visualizacion-biodiversidad-streamlit (mfvargas)')

#
# ENTRADAS
#

# Carga de datos
st.subheader('Carga de datos')
st.markdown('Las capas de límite cantonal y red vial se cargan del [repositorio en Github] (https://github.com/JosinMC/proyecto-streamlit/tree/main/data)')

# Definicion del geoide que se usara para calcular areas y longitudes
geod = Geod(ellps="WGS84")

#
# Red vial
# Carga de red vial desde un archivo geojson a un geodataframe
vias = gpd.read_file("data/red_vial.geojson")
# Seleccion de columnas necesarias
vias = vias.loc[:, ['categoria', 'codigo', 'geometry']]

#
# Cantones
# Carga de cantones desde un archivo geojson a un geodataframe
cantones = gpd.read_file("data/limite_cantonal.geojson")
# Seleccion de columnas necesarias
cantones = cantones.loc[:, ['id', 'canton', 'provincia', 'geometry']]
# Calculo del area cantonal en km2
area_f = lambda x: abs(geod.geometry_area_perimeter(x)[0])
cantones['area'] = cantones.geometry.apply(area_f) / 1e6 # m2 a km2


# Especificación de filtros
lista_categorias = vias['categoria'].unique().tolist()
lista_categorias.sort()
filtro_categoria = st.sidebar.selectbox('Seleccione la categoría de vía', lista_categorias)
filtro_categoria_str = filtro_categoria.lower()


#
# PROCESAMIENTO
#

# Filtrado
vias = vias[vias['categoria'] == filtro_categoria]

# Join espacial y cálculo de la densidad de la red vial

# La funcion overlay retorna las geometrias resultantes de aplicar el predicado de interseccion
# entre cada via y cada canton
cantones_vias = vias.overlay(cantones, how='intersection')#, keep_geom_type=False)
cantones_vias['longitud'] = cantones_vias.geometry.apply(geod.geometry_length) / 1e3 # m a km

por_categoria = cantones_vias.groupby(['canton','categoria'], as_index=False).agg(
    area=('area', 'first'),
    longitud=('longitud', 'sum')
    )

por_canton = cantones_vias.dissolve(
    by='canton',
    aggfunc={
        'id': 'first',
        'area': 'first',
        'longitud': 'sum'
        }
    )
por_canton['densidad'] = por_canton['longitud'] / por_canton['area']



# ---------------------------------------------------------------------------------------------
# SALIDAS
# ---------------------------------------------------------------------------------------------

# Tabla
st.header('Tabla de vías tipo ' + filtro_categoria_str)
tabla = por_categoria.pivot(index='canton', columns='categoria', values='longitud').fillna('--')
tabla = pd.concat([tabla, por_canton['densidad']], join='inner', axis='columns')
# Opcion de pandas para permitir que se muestren mas filas en tablas html
pd.set_option('display.max_rows', 90)
tabla.reset_index(inplace=True)
tabla.rename(columns={"canton": "cantón"}, inplace=True)
tabla.columns = tabla.columns.str.title()

st.dataframe(tabla.round(4))
st.markdown('Se muestra la densidad y la longitud de la red vial en Km para la categoría seleccionada.')

# Definición de columnas
col1, col2 = st.columns(2)

with col1:
    # Gráfico de barras
    st.header('Gráfico de barras para vías tipo ' + filtro_categoria_str)
    # Seleccion de los 15 cantones con mayor longitud total
    top_15 = por_canton.nlargest(15, 'longitud')['longitud']
    top_15_por_categoria = por_categoria.join(top_15, on='canton', how='inner', rsuffix='_canton')

    fig = px.bar(
        top_15_por_categoria.sort_values('longitud_canton', ascending=False),
        x="canton",
        y="longitud",
        labels={"canton": "Cantón",  "longitud": "Longitud (Km)"},
        title=f"Longitud de vías para los 15 cantones con mayor longitud de red vial"
        )
    st.plotly_chart(fig)
    st.markdown('Se muestra la longitud para los 15 cantones con mayor longitud de red vial según la categoría seleccionada.')

with col2:
    # Grafico de pastel
    st.header('Gráfico de pastel para vías tipo ' + filtro_categoria_str)
    # Se añade la categoria 'Otros' para todos los cantones despues de los 15 con mayor longitud
    por_canton_pie = por_canton.sort_values('longitud', ascending=False).reset_index()
    por_canton_pie.loc[por_canton_pie.index >= 15, 'canton'] = 'Otros cantones'

    fig = px.pie(por_canton_pie, values='longitud', names='canton', title='Longitud de vías por cantón',
                labels={"canton": "Cantón",  "longitud": "Longitud (Km)"},)
                
    st.plotly_chart(fig)
    st.markdown('Se muestra la proporción de longitud de vias de los 15 cantones con mayor longitud total, con respecto a la longitud de la red vial en todo el país.')


# Mapa de coropletas de registros de presencia en ASP
st.header('Mapa de coropletas para vías tipo ' + filtro_categoria_str)
  
# Mover cantones a una columna
por_canton_mapa = por_canton.reset_index()
# Creación del mapa base con escala
m = folium.Map(location=[9.8, -84], tiles='CartoDB positron', zoom_start=8, control_scale=True)

# Capa de coropletas
l1 = folium.Choropleth(
    name="Densidad de la red vial en cantón",
    geo_data=cantones,
    data=por_canton_mapa,
    columns=['id', 'densidad'],
    bins=7,
    key_on='feature.properties.id',
    fill_color='Reds', 
    fill_opacity=0.9, 
    line_opacity=1,
    legend_name='Densidad de la red vial',
    smooth_factor=0).add_to(m)

# Capa de red vial
l2 = folium.GeoJson(
    por_canton_mapa,
    name="Red vial",
    style_function=lambda x: {'color': '#000000', 'opacity':0.8, 'weight': 0.5}).add_to(m)

# Asegura que la capa de cantones siempre se mantenga detras de la de vias
# aun al usar el layer control
m.keep_in_front(l1,l2)

# Control de capas
folium.LayerControl().add_to(m)

# Despliegue del mapa
folium_static(m)
st.markdown('Este mapa muestra la densidad de la red vial en el país por cada cantón, con los cantones con mayor densidad coloreados con rojo más intenso. La red vial se muestra sobre los cantones como líneas negras. Los cantones sombreados en negro representan cantones donde no existe el tipo de vía seleccionada.')
