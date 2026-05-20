"""
Visualisation 3D d'une solution de Bin Packing avec Plotly.
"""

import plotly.graph_objects as go
from typing import List
from .model import Item, Container

COLORS = [
    '#e6194b', '#3cb44b', '#4363d8', '#f58231', '#911eb4',
    '#42d4f4', '#f032e6', '#bfef45', '#469990', '#dcbeff',
    '#9A6324', '#800000', '#aaffc3', '#e6beff', '#fffac8',
]

# Indices de triangulation d'un cube (12 triangles, 6 faces)
# Sommets :
#   v0=(x0,y0,z0)  v1=(x1,y0,z0)  v2=(x1,y1,z0)  v3=(x0,y1,z0)
#   v4=(x0,y0,z1)  v5=(x1,y0,z1)  v6=(x1,y1,z1)  v7=(x0,y1,z1)
_BOX_I = [0, 0, 4, 4, 0, 0, 2, 2, 0, 0, 1, 1]
_BOX_J = [1, 2, 5, 6, 1, 5, 3, 7, 3, 7, 2, 6]
_BOX_K = [2, 3, 6, 7, 5, 4, 7, 6, 7, 4, 6, 5]


def _box_mesh(x0, y0, z0, w, d, h, color, name, opacity=0.65):
    x1, y1, z1 = x0 + w, y0 + d, z0 + h
    vx = [x0, x1, x1, x0, x0, x1, x1, x0]
    vy = [y0, y0, y1, y1, y0, y0, y1, y1]
    vz = [z0, z0, z0, z0, z1, z1, z1, z1]
    return go.Mesh3d(
        x=vx, y=vy, z=vz,
        i=_BOX_I, j=_BOX_J, k=_BOX_K,
        color=color,
        opacity=opacity,
        name=name,
        showlegend=True,
        flatshading=True,
    )


def _container_wireframe(W, D, H):
    """12 arêtes du conteneur sous forme de lignes."""
    corners = [
        (0,0,0),(W,0,0),(W,D,0),(0,D,0),
        (0,0,H),(W,0,H),(W,D,H),(0,D,H),
    ]
    edges = [
        (0,1),(1,2),(2,3),(3,0),  # bas
        (4,5),(5,6),(6,7),(7,4),  # haut
        (0,4),(1,5),(2,6),(3,7),  # verticales
    ]
    xs, ys, zs = [], [], []
    for a, b in edges:
        xs += [corners[a][0], corners[b][0], None]
        ys += [corners[a][1], corners[b][1], None]
        zs += [corners[a][2], corners[b][2], None]
    return go.Scatter3d(
        x=xs, y=ys, z=zs,
        mode='lines',
        line=dict(color='black', width=3),
        name='Conteneur',
        showlegend=False,
    )


def plot_bin(items: List[Item], result: dict, bin_idx: int, container: Container):
    """Affiche le contenu d'un seul conteneur en 3D (retourne une Figure)."""
    fig = go.Figure()
    fig.add_trace(_container_wireframe(container.W, container.D, container.H))

    item_count = 0
    for i, (item, b) in enumerate(zip(items, result['assignment'])):
        if b != bin_idx:
            continue
        px, py, pz = result['positions'][i]
        color = COLORS[i % len(COLORS)]
        label = f'Objet {i} ({item.w}×{item.d}×{item.h})'
        fig.add_trace(_box_mesh(px, py, pz, item.w, item.d, item.h, color, label))
        item_count += 1

    fig.update_layout(
        title=f'Conteneur {bin_idx} — {item_count} objet(s)',
        scene=dict(
            xaxis=dict(range=[0, container.W], title='X (largeur)'),
            yaxis=dict(range=[0, container.D], title='Y (profondeur)'),
            zaxis=dict(range=[0, container.H], title='Z (hauteur)'),
            aspectmode='manual',
            aspectratio=dict(x=container.W, y=container.D, z=container.H),
        ),
        margin=dict(l=0, r=0, t=50, b=0),
    )
    return fig


def plot_all_bins(items: List[Item], result: dict, container: Container):
    """Retourne une liste de figures, une par conteneur utilisé."""
    return [plot_bin(items, result, b, container) for b in range(result['num_bins'])]


def summary_table(items: List[Item], result: dict, container: Container) -> dict:
    """Résumé statistique de la solution."""
    n_bins = result['num_bins']
    total_vol = sum(item.volume for item in items)
    container_vol = container.volume
    efficiency = total_vol / (n_bins * container_vol) * 100
    return {
        'num_items': len(items),
        'num_bins': n_bins,
        'total_item_volume': total_vol,
        'container_volume': container_vol,
        'space_efficiency_pct': round(efficiency, 1),
        'solve_time_s': round(result.get('solve_time', 0), 3),
        'status': result.get('status', ''),
    }
