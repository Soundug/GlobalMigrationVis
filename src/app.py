import pandas as pd
import geopandas as gpd
import streamlit as st
import pydeck as pdk
import plotly.express as px
import plotly.graph_objects as go

# --- LOAD & CLEAN DATA ---
@st.cache_data
def load_migration_data():
    migration_csv = r'C:\PROJECTS\Global Migration Vis\static\data\migrant-stock-total.csv'
    df = pd.read_csv(migration_csv)
    df_wide = df.pivot(index="Entity", columns="Year", values="Total number of international immigrants")
    df_wide = df_wide.dropna(thresh=5)
    df_wide = df_wide.interpolate(axis=1).bfill(axis=1).ffill(axis=1)
    aggregates = [
        'Africa', 'Americas', 'Asia', 'Europe', 'European Union', 'High income',
        'Low income', 'Lower middle income', 'Upper middle income', 'Oceania',
        'World', 'North America', 'South America', 'Sub-Saharan Africa', 'Middle East'
    ]
    df_wide = df_wide[~df_wide.index.isin(aggregates)]
    fix_names = {
        "United States": "United States of America",
        "Czechia": "Czech Republic",
        "Democratic Republic of Congo": "Democratic Republic of the Congo",
        "Republic of Congo": "Republic of the Congo",
        "Eswatini": "Swaziland",
        "Timor": "Timor-Leste",
        "Myanmar": "Burma",
        "North Macedonia": "Macedonia",
        "South Sudan": "Sudan",
        "Laos": "Lao PDR",
    }
    df_wide.rename(index=fix_names, inplace=True)
    return df_wide

@st.cache_data
def load_geometries():
    shapefile_path = r'C:\PROJECTS\Global Migration Vis\static\data\ne_110m_admin_0_countries\ne_110m_admin_0_countries.shp'
    world = gpd.read_file(shapefile_path)
    world = world.rename(columns={'ADMIN': 'Entity'})
    return world

df_wide = load_migration_data()
world = load_geometries()

# --- MERGE DATA ---
merged = world.merge(df_wide, on='Entity', how='inner')
merged['centroid_lon'] = merged['geometry'].centroid.x
merged['centroid_lat'] = merged['geometry'].centroid.y

years = sorted([int(y) for y in df_wide.columns])
default_year = max(years)

# --- SIDEBAR ---
with st.sidebar:
    st.markdown("#### About this App")
    st.markdown("""
    Visualizing global migration patterns with a 3D globe, maps, and a Sankey diagram.
    **Data:** UN DESA 2024, Natural Earth  
    **Author:** Soundarya Goski
    """)

# --- MAIN HEADER ---
st.title("🌍 Global Migration Patterns")

# --- SELECTORS ---
year = st.slider("Select Year", min_value=min(years), max_value=max(years), value=default_year, step=5)
country_options = sorted(merged['Entity'].unique())
selected_dest = st.selectbox("Destination Country (for Globe & Sankey)", country_options, index=0)

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["Choropleth Map", "3D Globe", "Sankey Diagram"])

# --- CHOROPLETH MAP TAB ---
with tab1:
    st.header(f"Migrant Stock by Country: {year}")
    fig_map = px.choropleth(
        merged,
        geojson=merged.geometry,
        locations=merged.index,
        color=year,
        hover_name="Entity",
        projection="natural earth",
        labels={year: "Migrants"},
        title=f"Total International Migrants ({year})"
    )
    fig_map.update_geos(fitbounds="locations", visible=False)
    fig_map.update_layout(margin={"r":0,"t":30,"l":0,"b":0})
    st.plotly_chart(fig_map, use_container_width=True)

# --- 3D GLOBE TAB ---
with tab2:
    st.header("3D Migration Globe (to Selected Destination)")
    dest_row = merged[merged['Entity'] == selected_dest].iloc[0]
    flows = []
    for src_idx, src_row in merged.iterrows():
        if src_row['Entity'] != selected_dest:
            flows.append({
                'from_lon': src_row['centroid_lon'],
                'from_lat': src_row['centroid_lat'],
                'to_lon': dest_row['centroid_lon'],
                'to_lat': dest_row['centroid_lat'],
                'migrants': src_row[year]
            })
    flows_df = pd.DataFrame(flows)

    arc_layer = pdk.Layer(
        "ArcLayer",
        data=flows_df,
        get_source_position=["from_lon", "from_lat"],
        get_target_position=["to_lon", "to_lat"],
        get_width="migrants/1e6",
        get_source_color=[0, 128, 200, 120],
        get_target_color=[200, 30, 80, 180],
        pickable=True,
        auto_highlight=True
    )

    view_state = pdk.ViewState(latitude=0, longitude=0, zoom=0, min_zoom=0, max_zoom=5, pitch=30, bearing=0)

    globe = pdk.Deck(
        layers=[arc_layer],
        initial_view_state=view_state,
        views=[pdk.View(type="GlobeView")],
        tooltip={"text": "Migrants: {migrants:.0f}"}
    )

    st.pydeck_chart(globe)
    st.caption(f"Showing flows to: {selected_dest} ({year}) — Note: Flows are based on migrant stock, not actual flows.")

# --- SANKEY DIAGRAM TAB ---
with tab3:
    st.header("Sankey Diagram (Top 10 Sources to Selected Destination)")

    # Top N sources to selected_dest in given year
    # We'll pick the top N sources (countries with the largest stocks) for the diagram
    N = 10
    sources_df = merged[merged['Entity'] != selected_dest][[year]].copy()
    sources_df['Entity'] = merged[merged['Entity'] != selected_dest]['Entity']
    top_sources = sources_df.nlargest(N, year)

    labels = list(top_sources['Entity']) + [selected_dest]
    source_indices = list(range(N))
    target_index = N  # selected_dest is the last label

    sankey_source = []
    sankey_target = []
    sankey_value = []

    for idx, row in top_sources.iterrows():
        sankey_source.append(labels.index(row['Entity']))
        sankey_target.append(target_index)
        sankey_value.append(row[year])

    sankey_fig = go.Figure(go.Sankey(
        node = dict(
            pad = 15,
            thickness = 20,
            line = dict(color = "black", width = 0.5),
            label = labels
        ),
        link = dict(
            source = sankey_source,
            target = sankey_target,
            value = sankey_value,
            color = "rgba(150,200,250,0.5)"
        )
    ))
    sankey_fig.update_layout(title_text=f"Top 10 Source Countries to {selected_dest} ({year})", font_size=12)
    st.plotly_chart(sankey_fig, use_container_width=True)
    st.caption("Note: The Sankey diagram uses migration stock as a proxy for flow.")

# --- Optionally, add time series or other features as more tabs ---
