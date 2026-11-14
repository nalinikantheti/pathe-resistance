"""Optional, lightweight inspection map; no frontend or hosted service required."""

import json


def save_map(edges, path, *, boundary=None, routes=None):
    """Write an HTML map. Tiles/JavaScript require internet when viewed."""
    try:
        import folium
    except ImportError as exc:
        raise ImportError("Install the map extra: pip install 'pathe-resistance[map]'") from exc
    data = edges.to_crs(4326).copy()
    fields = [c for c in ["u", "v", "key", "tree_cover", "baseline_s", "resistance_s"] if c in data]
    payload = json.loads(data[fields + ["geometry"]].to_json(na="null"))
    bounds = data.total_bounds
    view = folium.Map(
        location=[(bounds[1] + bounds[3]) / 2, (bounds[0] + bounds[2]) / 2],
        tiles="OpenStreetMap",
        prefer_canvas=True,
    )

    def style(feature):
        tree = feature["properties"].get("tree_cover")
        color = "#94a3b8" if tree is None else "#b45309" if tree < 0.5 else "#15803d"
        return {"color": color, "weight": 3, "opacity": 0.8}

    folium.GeoJson(
        payload,
        name="Walking graph · tree adjacency",
        style_function=style,
        tooltip=folium.GeoJsonTooltip(fields=fields),
    ).add_to(view)
    if boundary is not None:
        folium.GeoJson(
            json.loads(boundary.to_crs(4326).to_json()),
            name="Origin boundary",
            style_function=lambda _: {"color": "#7c3aed", "weight": 3, "fill": False},
        ).add_to(view)
    if routes is not None and len(routes):
        for label, color in [("baseline", "#2563eb"), ("resistance", "#db2777")]:
            subset = routes[routes.route == label].to_crs(4326)
            if len(subset):
                folium.GeoJson(
                    json.loads(subset.to_json()),
                    name=label,
                    style_function=lambda _, c=color: {"color": c, "weight": 6},
                    tooltip=folium.GeoJsonTooltip(fields=["route", "pair"]),
                ).add_to(view)
    folium.LayerControl().add_to(view)
    view.fit_bounds([[bounds[1], bounds[0]], [bounds[3], bounds[2]]])
    view.get_root().html.add_child(
        folium.Element(
            '<div style="position:fixed;bottom:20px;left:12px;background:white;padding:10px;z-index:9999">'
            "PathéResistance · green: more predicted trees; orange: fewer; gray: unknown.<br>"
            "Tree adjacency is not measured shade. Routes do not certify access or safety.<br>"
            "OSM-derived maps: © OpenStreetMap contributors</div>"
        )
    )
    view.save(str(path))
