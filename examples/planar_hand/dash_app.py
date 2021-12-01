import os
import json
import pickle

import meshcat
import numpy as np
import dash
from dash import dcc, html
import dash_bootstrap_components as dbc
import pandas as pd

from dash.dependencies import Input, Output, State
import plotly.graph_objects as go

from qsim.simulator import (QuasistaticSimulator, QuasistaticSimParameters)
from qsim.system import cpp_params_from_py_params
from quasistatic_simulator_py import (QuasistaticSimulatorCpp)
from planar_hand_setup import (model_directive_path, h,
                               robot_stiffness_dict, object_sdf_dict,
                               robot_l_name, robot_r_name, object_name)

from irs_lqr.quasistatic_dynamics import QuasistaticDynamics
from rrt.utils import set_orthographic_camera_yz



# %% quasistatic dynamics
sim_params = QuasistaticSimParameters()
q_sim_py = QuasistaticSimulator(
    model_directive_path=model_directive_path,
    robot_stiffness_dict=robot_stiffness_dict,
    object_sdf_paths=object_sdf_dict,
    sim_params=sim_params,
    internal_vis=True)

# construct C++ backend.
sim_params_cpp = cpp_params_from_py_params(sim_params)
q_sim_cpp = QuasistaticSimulatorCpp(
    model_directive_path=model_directive_path,
    robot_stiffness_str=robot_stiffness_dict,
    object_sdf_paths=object_sdf_dict,
    sim_params=sim_params_cpp)

q_dynamics = QuasistaticDynamics(h=h, q_sim_py=q_sim_py, q_sim=q_sim_cpp)

model_a_l = q_sim_py.plant.GetModelInstanceByName(robot_l_name)
model_a_r = q_sim_py.plant.GetModelInstanceByName(robot_r_name)
model_u = q_sim_py.plant.GetModelInstanceByName(object_name)

# %% meshcat
vis = q_sim_py.viz.vis
set_orthographic_camera_yz(vis)

# goal
vis["goal/cylinder"].set_object(
    meshcat.geometry.Cylinder(height=0.001, radius=0.25),
    meshcat.geometry.MeshLambertMaterial(color=0xdeb948, reflectivity=0.8))
vis['goal/box'].set_object(
    meshcat.geometry.Box([0.02, 0.005, 0.25]),
    meshcat.geometry.MeshLambertMaterial(color=0x00ff00, reflectivity=0.8))
vis['goal/box'].set_transform(
    meshcat.transformations.translation_matrix([0, 0, 0.125]))

# rotate cylinder so that it faces the x-axis.
X_WG0 = meshcat.transformations.rotation_matrix(np.pi/2, [0, 0, 1])
vis['goal'].set_transform(X_WG0)


# %% load data from disk and format data.
'''
data format
name: reachability_trj_opt_xx.pkl
{# key: item
    'qu_0': (3,) array, initial pose of the sphere.
    'reachable_set_radius': float, radius of the box from which 1 step reachable set 
        commands are sampled.
    'trj_data': List[Dict], where Dict is
        {
            'cost': {'Qu': float, 'Qu_f': float, 'Qa': float, 'Qa_f': float, 'R': float,
                     'all': float},
            'x_trj': (T+1, n_q) array.
            'u_trj': (T, n_a) array.
            'dqu_goal': (3,) array. dqu_goal + qu_0 gives the goal which this x_trj and 
                u_trj tries to reach.
        }
    'reachable_set_data': # samples used to generate 1-step or multi-step reachable sets.
    {
        'du': (n_samples, n_a) array,
        'qa_l': {'1_step': (n_samples, 2) array, 'multi_step': (n_samples, 2) array.},
        'qa_r': {'1_step': (n_samples, 2) array, 'multi_step': (n_samples, 2) array.},
        'qu': {'1_step': (n_samples, 3) array, 'multi_step': (n_samples, 3) array.}
    }
}
'''

with open('./data/reachability_trj_opt_01.pkl', 'rb') as f:
    reachability_trj_opt = pickle.load(f)

du = reachability_trj_opt['reachable_set_data']['du']
qa_l = reachability_trj_opt['reachable_set_data']['qa_l']
qa_r = reachability_trj_opt['reachable_set_data']['qa_r']
qu = reachability_trj_opt['reachable_set_data']['qu']

# the first row in all trajectories have the same initial object pose.
q_u0 = reachability_trj_opt['qu_0']
trj_data = reachability_trj_opt['trj_data']
dqu_goal = np.array([result['dqu_goal'] for result in trj_data])

#%% PCA of 1-step reachable set.
qu_1 = qu['1_step']
qu_1_mean = qu_1.mean(axis=0)
U, sigma, Vh = np.linalg.svd(qu_1 - qu_1_mean)
r = 0.5
principal_points = np.zeros((3, 2, 3))
for i in range(3):
    principal_points[i, 0] = qu_1_mean - Vh[i] * sigma[i] / sigma[0] * r
    principal_points[i, 1] = qu_1_mean + Vh[i] * sigma[i] / sigma[0] * r


# %%
hovertemplate = (
    '<i>y</i>: %{x:.4f}<br>' +
    '<i>z</i>: %{y:.4f}<br>' +
    '<i>theta</i>: %{z:.4f}')

hovertemplate_reachability = (hovertemplate +
                              '<br><i>cost</i>: %{marker.color:.4f}')

plot_1_step = go.Scatter3d(x=qu['1_step'][:, 0],
                           y=qu['1_step'][:, 1],
                           z=qu['1_step'][:, 2],
                           name='1_step',
                           mode='markers',
                           hovertemplate=hovertemplate,
                           marker=dict(size=2))
plot_multi = go.Scatter3d(x=qu['multi_step'][:, 0],
                          y=qu['multi_step'][:, 1],
                          z=qu['multi_step'][:, 2],
                          name='multi_step',
                          mode='markers',
                          hovertemplate=hovertemplate,
                          marker=dict(size=2))

plot_trj = go.Scatter3d(
    x=q_u0[0] + dqu_goal[:, 0],
    y=q_u0[1] + dqu_goal[:, 1],
    z=q_u0[2] + dqu_goal[:, 2],
    name='reachability',
    mode='markers',
    hovertemplate=hovertemplate_reachability,
    marker=dict(size=5,
                color=[result['cost']['Qu_f'] for result in trj_data],
                colorscale='jet',
                showscale=True,
                opacity=0.8))


# PCA lines
colors = ['red', 'green', 'blue']
pca_names = 'xyz'
principal_axes_plots = []
for i in range(3):
    principal_axes_plots.append(
        go.Scatter3d(
            x=principal_points[i, :, 0],
            y=principal_points[i, :, 1],
            z=principal_points[i, :, 2],
            name=f'pca_{pca_names[i]}',
            mode='lines',
            line=dict(color=colors[i], width=4)
        )
    )


layout = go.Layout(autosize=True, height=1200,
                   legend=dict(orientation="h"),
                   margin=dict(l=0, r=0, b=0, t=0))
fig = go.Figure(data=[plot_1_step, plot_multi, plot_trj] + principal_axes_plots,
                layout=layout)
fig.update_layout(coloraxis_colorbar=dict(yanchor="top", x=3, ticks="outside"))
fig.update_scenes(camera_projection_type='orthographic',
                  xaxis_title_text='y',
                  yaxis_title_text='z',
                  zaxis_title_text='theta',
                  aspectmode='data',
                  aspectratio=dict(x=1.0, y=1.0, z=1.0))

# %%
app = dash.Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

styles = {
    'pre': {
        'border': 'thin lightgrey solid',
        'overflowX': 'scroll'
    }
}

app.layout = dbc.Container([
    dbc.Row([
        dbc.Col(
            dcc.Graph(
                id='reachable-sets',
                figure=fig),
            width={'size': 6, 'offset': 0, 'order': 0},
        ),
        dbc.Col(
            html.Iframe(src='http://127.0.0.1:7000/static/',
                        height=800, width=1000),
            width={'size': 6, 'offset': 0, 'order': 0},
        )
    ]),
    dbc.Row([
        dbc.Col([
            dcc.Markdown("""
                **Hover Data**

                Mouse over values in the graph.
            """),
            html.Pre(id='hover-data', style=styles['pre'])],
            width={'size': 3, 'offset': 0, 'order': 0}
        ),
        dbc.Col([
            dcc.Markdown("""
                **Click Data**

                Click on points in the graph.
            """),
            html.Pre(id='click-data', style=styles['pre'])],
            width={'size': 3, 'offset': 0, 'order': 0}
        ),
        dbc.Col([
            dcc.Markdown("""
                **Selection Data**

                Choose the lasso or rectangle tool in the graph's menu
                bar and then select points in the graph.

                Note that if `layout.clickmode = 'event+select'`, selection data also
                accumulates (or un-accumulates) selected data if you hold down the shift
                button while clicking.
            """),
            html.Pre(id='selected-data', style=styles['pre'])],
            width={'size': 3, 'offset': 0, 'order': 0}
        ),
        dbc.Col([
            dcc.Markdown("""
                **Zoom and Relayout Data**

                Click and drag on the graph to zoom or click on the zoom
                buttons in the graph's menu bar.
                Clicking on legend items will also fire
                this event.
            """),
            html.Pre(id='relayout-data', style=styles['pre'])],
            width={'size': 3, 'offset': 0, 'order': 0}
        )
    ])
], fluid=True)


@app.callback(
    Output('hover-data', 'children'),
    Input('reachable-sets', 'hoverData'),
    State('reachable-sets', 'figure'))
def display_hover_data(hoverData, figure):
    hover_data_json = json.dumps(hoverData, indent=2)
    if hoverData is None:
        return hover_data_json
    point = hoverData['points'][0]
    idx_fig = point['curveNumber']
    name = figure['data'][idx_fig]['name']
    idx = point["pointNumber"]

    if name == 'reachability':
        p_WG = np.array([point['x'], 0, point['y']])
        theta = point['z']
        X_G0G = (meshcat.transformations.translation_matrix(p_WG) @
                 meshcat.transformations.rotation_matrix(-theta, [0, 1, 0]))
        vis['goal'].set_transform(X_WG0 @ X_G0G)
    elif name.startswith('pca'):
        return hover_data_json
    else:
        q_dict = {
            model_u: qu[name][idx],
            model_a_l: qa_l[name][idx],
            model_a_r: qa_r[name][idx]}

        q_sim_py.update_mbp_positions(q_dict)
        q_sim_py.draw_current_configuration()

    return hover_data_json


@app.callback(
    Output('click-data', 'children'),
    Input('reachable-sets', 'clickData'),
    State('reachable-sets', 'figure'))
def display_click_data(click_data, figure):
    click_data_json = json.dumps(click_data, indent=2)
    if click_data is None:
        return click_data_json
    point = click_data['points'][0]
    idx_fig = point['curveNumber']
    name = figure['data'][idx_fig]['name']
    idx = point["pointNumber"]

    if name == 'reachability':
        q_dynamics.publish_trajectory(trj_data[idx]['x_trj'])

    return click_data_json


@app.callback(
    Output('selected-data', 'children'),
    Input('reachable-sets', 'selectedData'))
def display_selected_data(selectedData):
    return json.dumps(selectedData, indent=2)


@app.callback(
    Output('relayout-data', 'children'),
    Input('reachable-sets', 'relayoutData'))
def display_relayout_data(relayoutData):
    return json.dumps(relayoutData, indent=2)


if __name__ == '__main__':
    app.run_server(debug=True)
