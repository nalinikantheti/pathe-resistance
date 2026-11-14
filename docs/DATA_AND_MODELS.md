# Code, data and model rights

The MIT license applies to this repository's code. It does not change the terms of dependencies, model weights, imagery or generated databases derived from licensed sources. The offline demo contains only synthetic geometries and pixels authored for this repository.

## OpenStreetMap

OSM data is licensed under ODbL and requires attribution. Preserve © OpenStreetMap contributors and review the [OSM copyright and license page](https://www.openstreetmap.org/copyright) before distributing a derived database. The pipeline adds OSM attribution to downloaded graphs. For a supplied graph, preserve its real source/attribution rather than assuming it is OSM.

Use the [OSMnx documentation](https://osmnx.readthedocs.io/en/stable/) and public-service usage guidance when downloading. This toolkit does not bypass API limits. A local input GraphML avoids repeated API requests.

## GeoAI checkpoints

This package bundles no checkpoint. `segment` requires a caller-chosen model and, for remote repositories, a pinned commit. The adapter disables remote-code execution and requests safetensors weights. Model class labels and input expectations remain your responsibility.

The [Restor TCD SegFormer model card](https://huggingface.co/restor/tcd-segformer-mit-b0) used by the EmPath research describes NVIDIA research-license terms and training imagery with noncommercial terms. Do not assume that an open-source inference adapter grants commercial rights to that checkpoint. Its training resolution is 10 cm/pixel; applying it to coarser imagery is a transfer requiring local accuracy review. A permissively licensed alternative can be supplied without changing the core sampler or router.

## Imagery and environmental layers

Supply your own georeferenced imagery/predictions. Preserve provider, acquisition date, spatial resolution, CRS, NoData, processing method, model revision and any required attribution. This release does not redistribute NAIP, Texas statewide canopy, Landsat, Census, traffic data, private addresses, authentication tokens or EmPath's generated datasets.

Predicted tree adjacency is not measured time-specific shade. Land surface temperature is not air temperature. Traffic proximity is not a calibrated pedestrian risk estimate. Resistance coefficients are explicit preferences; none of these outputs certify real-world access, safety or medical benefit.
