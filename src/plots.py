import sys
import os

sys.path.append("..")
sys.path.append("../src")
import utils
import loader
import model.simulator as simulator

# Plotting
import plotly
import plotly.graph_objs as go
import pandas as pd
import numpy as np

# Setting cufflinks
import textwrap
import cufflinks as cf

cf.go_offline()
cf.set_config_file(offline=False, world_readable=True)

# Centering and fixing title
def iplottitle(title, width=40):
    return "<br>".join(textwrap.wrap(title, width))


import yaml

config = yaml.load(open("configs/config.yaml", "r"), Loader=yaml.FullLoader)


# ANALYSIS PAGE
def plot_heatmap(df, x, y, z, title, colorscale="oranges"):

    return df.pivot(columns=y, index=x, values=z).iplot(
        kind="heatmap", theme="custom", colorscale=colorscale, title=title
    )


# FAROLCOVID INDICATOR: RT
def plot_rt(t, title=""):
    # TODO: put dicts in config
    rt_classification = {
        "Risco médio: Uma pessoa infecta em média mais 1.2 outras": {
            "threshold": 1.2,
            "color": "#F02C2E",
            "fill": None,
            "width": 3,
        },

        "Risco alto: Uma pessoa infecta em média outras 1.0-1.2": {
            "threshold": 1,
            "color": "#F77800",
            "fill": None,
            "width": 3,
        },
        "Risco moderado: Uma pessoa infecta em média outras 0.5-1": {
            "threshold": 0.5,
            "color": "#F7B500",
            "fill": None,
            "width": 3,
        },
    }

    ic_layout = {
        "Rt_high_95": {
            "fill": "tonexty",
            "showlegend": False,
            "name": None,
            "layout": {"color": "#E5E5E5", "width": 2},
        },
        "Rt_low_95": {
            "fill": "tonexty",
            "showlegend": True,
            "name": "Intervalo de confiança - 95%",
            "layout": {"color": "#E5E5E5", "width": 2},
        },
        "Rt_most_likely": {
            "fill": None,
            "showlegend": True,
            "name": "<b>Valor médio em {}={}</b>".format(
                t["last_updated"].max().strftime("%d/%m"), round(t["Rt_most_likely"].iloc[-1], 2)
            ),
            "layout": {"color": "rgba(63, 61, 87, 0.8)", "width": 3},
        },
    }

    fig = go.Figure()

    # Intervalos de confianca
    for bound in ic_layout.keys():

        fig.add_scattergl(
            x=t["last_updated"],
            y=t[bound],
            line=ic_layout[bound]["layout"],
            fill=ic_layout[bound]["fill"],
            mode="lines",
            showlegend=ic_layout[bound]["showlegend"],
            name=ic_layout[bound]["name"],
        )

    # Areas de risco
    for bound in rt_classification.keys():

        fig.add_trace(
            go.Scatter(
                x=t["last_updated"],
                y=[rt_classification[bound]["threshold"] for i in t["last_updated"]],
                line={
                    "color": rt_classification[bound]["color"],
                    "width": rt_classification[bound]["width"],
                    "dash": "dash",
                },  # 0
                fill=rt_classification[bound]["fill"],
                name=bound,
                showlegend=[False if bound == "zero" else True][0],
            )
        )

    fig.layout.yaxis.rangemode = "tozero"
    fig.layout.yaxis.range = [0, 5]

    fig.update_layout(template="plotly_white", title=title)
    return fig


def plot_rt_wrapper(place_id, place_type):

    endpoints = {
        "state_num_id": "state",
        "health_region_id": "health_region",
        "city_id": "city",
    }

    data = (
        loader.read_data(
            "br", config, config["br"]["api"]["endpoints"]["rt"][endpoints[place_type]]
        )
        .query(f"{place_type} == {place_id}")
        .sort_values("last_updated")
    )

    if len(data) < 30:
        return None

    fig = plot_rt(data)
    fig.update_layout(xaxis=dict(tickformat="%d/%m"))
    fig.update_layout(margin=dict(l=50, r=50, b=100, t=20, pad=4))
    fig.update_yaxes(automargin=True)

    return fig


def get_alert_color(value):

    alert_colors = ["#0097A7", "#17A700", "#F2C94C", "#FF5F6B"]

    if value <= 0.50:  # critical
        return alert_colors[3]
    elif value <= 0.70:  # bad
        return alert_colors[2]
    else:
        return alert_colors[1]


# FAROLCOVID INDICATOR: INLOCO
def plot_inloco(place_id, df, decoration=False):

    fig = go.Figure()
    names = utils.Dictionary().get_place_names_by_id(place_id)
    state_id = int(str(place_id)[:2])

    # Add traces
    if place_id > 10000:  # city
        clean_df = (
            df.query('state_num_id == "%s"' % state_id)
            .query('city_name == "%s"' % names[0])
            .reset_index()
        )

        x_values = translate_dates(clean_df["dt"])
        # Redo this in case of isolated not being the index anymore
        if clean_df.index.name == "isolated":
            y_values = clean_df.index
        else:
            y_values = clean_df["isolated"]
        name = names[0] + f" ({names[2]})"

    else:  # state
        clean_df = df.query('state_num_id == "%s"' % state_id).reset_index()
        x_values = translate_dates(clean_df["dt"])
        y_values = clean_df["isolated"]
        name = names[0]

    # Generate fig
    fig.add_trace(go.Scatter(x=x_values, y=y_values, name=name))

    # Use alert color
    fig.update_traces(line={"color": get_alert_color(y_values.iloc[-1])})

    if decoration:
        fig.update_layout(updatemenus=[dict(active=0)])
    fig.update_layout(template="plotly_white")

    return fig


def moving_average(a, n=7):
    ret = np.cumsum(a, dtype=float)
    ret = [ret[i] for i in range(len(ret)) if i < n] + [
        ret[i] - ret[i - n] for i in range(len(ret)) if i >= n
    ]
    result = [ret_day / min(n, i + 1) for i, ret_day in enumerate(ret)]
    return result


def sort_by_x(x, y):
    data = [[x[i], y[i]] for i in range(len(x))]
    data.sort(key=lambda element: element[0])
    return zip(*data)


def gen_social_dist_plots_state_session_wrapper(
    session_state, in_height=700, set_height=False
):
    if session_state.city_id == None or session_state.city_id == False:
        return gen_social_dist_plots(session_state.state_num_id)
    else:
        return gen_social_dist_plots(session_state.city_id)


def gen_social_dist_plots(place_id, in_height=700, set_height=False):

    api_inloco = utils.get_inloco_url(config)

    if place_id > 10000:
        is_city = True
    else:
        is_city = False
    social_dist_plot = None

    if is_city:
        if gen_social_dist_plots.cities_df is None:  # As to only load once
            gen_social_dist_plots.cities_df = pd.read_csv(
                api_inloco["cities"], index_col=0
            )
        social_dist_df = gen_social_dist_plots.cities_df
        social_dist_plot = plot_inloco(place_id, social_dist_df)

    else:  # IS STATE
        if gen_social_dist_plots.states_df is None:  # Too to only load once
            gen_social_dist_plots.states_df = pd.read_csv(
                api_inloco["states"], index_col=0
            )

        social_dist_df = gen_social_dist_plots.states_df
        social_dist_plot = plot_inloco(place_id, social_dist_df)

    # Moving average dotted
    x_data = social_dist_plot.data[0]["x"]
    y_data = social_dist_plot.data[0]["y"]
    x_data, y_data = sort_by_x(x_data, y_data)
    final_y = moving_average(y_data, n=7)
    social_dist_plot.add_trace(
        go.Scatter(
            x=x_data,
            y=final_y,
            line={"color": "lightgrey", "dash": "dash",},  # 0
            name="Média móvel (últimos 7 dias)",
            showlegend=True,
        )
    )

    social_dist_plot.update_layout(
        {
            "xaxis": dict(tickformat="%d/%m"),
            "yaxis": dict(tickformat=",.0%"),
            "template": "plotly_white",
            "margin": dict(l=50, r=50, b=100, t=20, pad=4),
        }
    )

    if set_height:
        social_dist_plot.update_layout(height=in_height)

    return social_dist_plot, final_y


def translate_dates(df, simple=True, lang_frame="pt_BR.utf8"):
    if simple:
        return df
    else:
        import locale

        locale.setlocale(locale.LC_ALL, lang_frame)
        newdate = pd.to_datetime(df)
        newdate = [d.strftime("%d %b %y") for d in newdate]

        return newdate


gen_social_dist_plots.cities_df = None
gen_social_dist_plots.states_df = None


# SIMULACOVID
def plot_simulation(dfs, user_input):

    cols = {
        "I2": {
            "name": "Demanda por leitos",
            "color": "#F2C94C",
            "resource_name": "Capacidade de leitos",
            "capacity": user_input["number_beds"],
        },
        "I3": {
            "name": "Demanda por leitos UTI",
            "color": "#0097A7",
            "resource_name": "Capacidade de leitos UTI",
            "capacity": user_input["number_icu_beds"],
        },
    }

    # Create graph
    t = (
        dfs["best"][cols.keys()]
        .join(dfs["worst"][cols.keys()], lsuffix="_best", rsuffix="_worst")
        .sort_index(axis=1)
    )

    # Changing from number of days in the future to actual date in the future
    t["ddias"] = t.index
    t["ndias"] = t.apply(utils.convert_times_to_real, axis=1)
    t = t.set_index("ndias")
    t.index.rename("dias", inplace=True)
    t = t.drop("ddias", axis=1)

    fig = go.Figure()
    for col in t.columns:
        i_type = col.split("_")[0]

        if "best" in col:
            fig.add_trace(
                go.Scatter(
                    x=t.index,
                    y=t[col].astype(int),
                    name=cols[i_type]["name"],
                    showlegend=False,
                    fill=None,
                    hovertemplate=None,  #'%{y:.0f} no dia %{x}',
                    mode="lines",
                    line=dict(color=cols[i_type]["color"], width=3),
                )
            )

        else:
            fig.add_trace(
                go.Scatter(
                    x=t.index,
                    y=t[col].astype(int),
                    name=cols[i_type]["name"],
                    fill="tonexty",
                    hovertemplate=None,  #'%{y:.0f} no dia %{x}',
                    mode="lines",
                    line=dict(color=cols[i_type]["color"], width=3),
                )
            )

    for i_type in cols.keys():
        fig.add_trace(
            go.Scatter(
                x=t.index,
                y=[cols[i_type]["capacity"] for i in t.index],
                name=cols[i_type]["resource_name"],
                showlegend=True,
                hovertemplate=None,
                mode="lines",
                line=dict(color=cols[i_type]["color"], width=6, dash="dot"),
            )
        )

    fig.update_layout(  # title="<b>EVOLUÇÃO DIÁRIA DA DEMANDA HOSPITALAR</b>", titlefont=dict(size=24, family='Oswald, sans-serif'),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        legend_orientation="h",
        template="plotly_white",
        legend=dict(x=0, y=-0.2, font=dict(size=18, family="Oswald, sans-serif")),
        hovermode="x",
        autosize=True,
        # width=1000,
        height=800,
        margin={"l": 70, "r": 50},
        annotations=[
            dict(
                xref="paper",
                yref="paper",
                x=0.00,
                y=1.1,
                showarrow=False,
                text="<i>Como ler: As áreas coloridas mostram a<br>margem de erro da estimativa a cada dia<i>",
            )
        ],
    )

    fig.update_xaxes(
        title="dias",
        tickfont=dict(size=16, family="Oswald, sans-serif"),
        # titletext=dict(xref='paper', x=0),
        titlefont=dict(size=18, family="Oswald, sans-serif"),
        showline=True,
        linewidth=2,
        linecolor="black",
        showgrid=False,
        tickformat="%d/%m",
    )

    fig.update_yaxes(
        gridwidth=1,
        gridcolor="#d7d8d9",
        tickfont=dict(size=16, family="Oswald, sans-serif"),
        title="Demanda",
    )

    return fig


# DRAFTS
def plot_rt_bars(df, title, place_type="state"):

    df["color"] = np.where(
        df["Rt_most_likely"] > 1.2,
        "rgba(242,185,80,1)",
        np.where(df["Rt_most_likely"] > 1, "rgba(132,217,217,1)", "#0A96A6"),
    )

    fig = go.Figure(
        go.Bar(
            x=df[place_type],
            y=df["Rt_most_likely"],
            marker_color=df["color"],
            error_y=dict(
                type="data",
                symmetric=False,
                array=df["Rt_most_likely"] - df["Rt_low_95"],
                arrayminus=df["Rt_most_likely"] - df["Rt_low_95"],
            ),
        )
    )

    fig.add_shape(
        # Line Horizontal
        type="line",
        x0=-1,
        x1=len(df[place_type]),
        y0=1,
        y1=1,
        line=dict(color="#E5E5E5", width=2, dash="dash",),
    )

    fig.update_layout({"template": "plotly_white", "title": title})

    return fig
