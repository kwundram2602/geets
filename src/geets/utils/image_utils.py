from __future__ import annotations

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
