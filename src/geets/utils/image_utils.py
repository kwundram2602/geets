from __future__ import annotations

from collections.abc import Iterator, Sequence

import ee


def get_image_with_least_cc(
    collection: ee.ImageCollection,
    cloud_property: str = "CLOUDY_PIXEL_PERCENTAGE",
) -> ee.Image:
    """Return the image with the lowest cloud cover from a collection.

    Parameters
    ----------
    collection     : pre-filtered ee.ImageCollection
    cloud_property : image property to sort by (default "CLOUDY_PIXEL_PERCENTAGE")

    Raises
    ------
    ValueError if the collection is empty.
    """
    n = collection.size().getInfo()
    if n == 0:
        raise ValueError(
            "[geets.image_utils] Collection is empty – "
            "cannot select least-cloudy image. Check your filters."
        )
    print(
        f"[geets.image_utils] Selecting least-cloudy image from {n} candidates "
        f"(property: '{cloud_property}')"
    )
    return collection.sort(cloud_property).first()

def get_image_i(collection: ee.ImageCollection, index: int) -> ee.Image:
    """Get the image at the specified index from an ImageCollection."""
    return ee.Image(collection.toList(collection.size()).get(index))


def add_hour_utc(img: ee.Image) -> ee.Image:
    """Add a UTC hour property (hour_utc) derived from system:time_start."""
    hour = ee.Date(img.get("system:time_start")).get("hour")
    return img.set("hour_utc", hour)


def add_time_start_utc(
    img: ee.Image,
    *,
    fmt: str = "YYYY-MM-dd HH:mm:ss",
) -> ee.Image:
    """Add a UTC timestamp string (time_start_utc) from system:time_start."""
    timestamp = ee.Date(img.get("system:time_start")).format(fmt)
    return img.set("time_start_utc", timestamp)


def iterate_coll(
    collection: ee.ImageCollection,
    *,
    max_images: int | None = None,
) -> Iterator[ee.Image]:
    """Yield images from an ImageCollection on the client side.

    Notes
    -----
    This uses getInfo() to obtain the collection size and then materializes
    a list of images. For large collections, pass max_images to limit the
    number of client-side items.
    """
    if max_images is not None and max_images < 1:
        raise ValueError("max_images must be >= 1")

    count = collection.size().getInfo()
    if not count:
        return

    if max_images is not None:
        count = min(count, max_images)
        collection = collection.limit(count)

    images = collection.toList(count)
    for index in range(count):
        yield ee.Image(images.get(index))


def add_collection_layers(
    m: "geemap.Map",
    collection: ee.ImageCollection,
    *,
    name_prefix: str = "img",
    max_images: int | None = None,
    name_attrs: Sequence[str] | None = None,
    vis_params: dict[str, object] | None = None,
) -> None:
    """Add each image in a collection as a separate layer on a geemap.Map.

    Notes
    -----
    This performs a client-side getInfo to read the collection size. For
    large collections, pass max_images to limit the number of layers.
    If name_attrs is provided, attribute values are fetched client-side to
    build layer names.
    """
    if max_images is not None and max_images < 1:
        raise ValueError("max_images must be >= 1")

    count = collection.size().getInfo()
    if count == 0:
        print("Collection is empty; no layers added.")
        return

    if max_images is not None:
        count = min(count, max_images)
        collection = collection.limit(count)

    images = collection.toList(count)
    attr_names = list(name_attrs or [])
    if attr_names and not all(isinstance(name, str) for name in attr_names):
        raise ValueError("name_attrs items must be strings")
    values_by_attr = (
        {name: collection.aggregate_array(name).getInfo() or [] for name in attr_names}
        if attr_names
        else {}
    )
    for index in range(count):
        img = ee.Image(images.get(index))
        layer_name = f"{name_prefix}_{index}"
        if attr_names:
            parts = []
            for name in attr_names:
                values = values_by_attr.get(name, [])
                value = values[index] if index < len(values) else None
                parts.append(f"{name}={value}")
            layer_name = f"{layer_name} | {', '.join(parts)}"
        m.addLayer(img, vis_params, layer_name)


def print_imagecoll_attrs(
    collection: ee.ImageCollection,
    attr: str | Sequence[str],
    *,
    max_images: int | None = None,
) -> None:
    """Print one or more property values for each image in a collection.

    Notes
    -----
    This performs a client-side request via getInfo; keep max_images small
    for large collections to avoid long requests.
    """
    if max_images is not None and max_images < 1:
        raise ValueError("max_images must be >= 1")

    attrs = [attr] if isinstance(attr, str) else list(attr)
    if not attrs:
        raise ValueError("attr must contain at least one property name")
    if not all(isinstance(name, str) for name in attrs):
        raise ValueError("attr items must be strings")

    subset = collection if max_images is None else collection.limit(max_images)
    values_by_attr = {name: subset.aggregate_array(name).getInfo() or [] for name in attrs}
    max_len = max((len(values) for values in values_by_attr.values()), default=0)
    if max_len == 0:
        print(f"No values found for attribute(s): {', '.join(attrs)}")
        return

    for index in range(max_len):
        parts = []
        for name in attrs:
            values = values_by_attr[name]
            value = values[index] if index < len(values) else None
            parts.append(f"{name}={value}")
        print(f"{index}: {', '.join(parts)}")
        
        
def sort_by_nodata(
    collection: ee.ImageCollection,
    geometry: ee.Geometry,
    *,
    scale: int = 100,
    max_pixels: int = 1e8,
) -> ee.ImageCollection:
    """Sort a collection ascending by nodata fraction (least nodata first).

    Computes the fraction of masked pixels within *geometry* for each image,
    attaches it as the ``nodata_fraction`` property, then sorts ascending so
    that ``collection.first()`` is the image with the least nodata.

    Parameters
    ----------
    collection  : input ImageCollection
    geometry    : region over which to measure nodata
    scale       : pixel resolution in metres for the reduction (default 100)
    max_pixels  : maximum number of pixels for reduceRegion (default 1e8)
    """

    def _add_nodata_fraction(img: ee.Image) -> ee.Image:
        valid_mask = img.mask().reduce(ee.Reducer.min())
        stats = valid_mask.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geometry,
            scale=scale,
            maxPixels=max_pixels,
            bestEffort=True,
        )
        valid_frac = ee.Number(stats.get("min", 0))
        nodata_frac = ee.Number(1).subtract(valid_frac)
        return img.set("nodata_fraction", nodata_frac)

    return collection.map(_add_nodata_fraction).sort("nodata_fraction")


def get_band_stats(
    img: ee.Image,
    geometry: ee.Geometry,
    reducer: ee.Reducer | None = None,
    scale: int = 30,
    max_pixels: int = 1e6,
) -> dict[str, float]:
    if reducer is None:
        reducer = ee.Reducer.minMax()
    stats = img.reduceRegion(
    reducer=reducer,
    geometry=geometry,
    scale=scale,
    maxPixels=max_pixels
    )
    return stats
