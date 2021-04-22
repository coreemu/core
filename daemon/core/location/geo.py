"""
Provides conversions from x,y,z to lon,lat,alt.
"""

import logging
from typing import Tuple

import pyproj
from pyproj import Transformer

from core.emulator.enumerations import RegisterTlvs

logger = logging.getLogger(__name__)
SCALE_FACTOR: float = 100.0
CRS_WGS84: int = 4326
CRS_PROJ: int = 3857


class GeoLocation:
    """
    Provides logic to convert x,y,z coordinates to lon,lat,alt using
    defined projections.
    """

    name: str = "location"
    config_type: RegisterTlvs = RegisterTlvs.UTILITY

    def __init__(self) -> None:
        """
        Creates a GeoLocation instance.
        """
        self.to_pixels: Transformer = pyproj.Transformer.from_crs(
            CRS_WGS84, CRS_PROJ, always_xy=True
        )
        self.to_geo: Transformer = pyproj.Transformer.from_crs(
            CRS_PROJ, CRS_WGS84, always_xy=True
        )
        self.refproj: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.refgeo: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.refxyz: Tuple[float, float, float] = (0.0, 0.0, 0.0)
        self.refscale: float = 1.0

    def setrefgeo(self, lat: float, lon: float, alt: float) -> None:
        """
        Set the geospatial reference point.

        :param lat: latitude reference
        :param lon: longitude reference
        :param alt: altitude reference
        :return: nothing
        """
        self.refgeo = (lat, lon, alt)
        px, py = self.to_pixels.transform(lon, lat)
        self.refproj = (px, py, alt)

    def reset(self) -> None:
        """
        Reset reference data to default values.

        :return: nothing
        """
        self.refxyz = (0.0, 0.0, 0.0)
        self.refgeo = (0.0, 0.0, 0.0)
        self.refscale = 1.0
        self.refproj = self.to_pixels.transform(*self.refgeo)

    def pixels2meters(self, value: float) -> float:
        """
        Provides conversion from pixels to meters.

        :param value: pixels value
        :return: pixels value in meters
        """
        return (value / SCALE_FACTOR) * self.refscale

    def meters2pixels(self, value: float) -> float:
        """
        Provides conversion from meters to pixels.

        :param value: meters value
        :return: meters value in pixels
        """
        if self.refscale == 0.0:
            return 0.0
        return SCALE_FACTOR * (value / self.refscale)

    def getxyz(self, lat: float, lon: float, alt: float) -> Tuple[float, float, float]:
        """
        Convert provided lon,lat,alt to x,y,z.

        :param lat: latitude value
        :param lon: longitude value
        :param alt: altitude value
        :return: x,y,z representation of provided values
        """
        logger.debug("input lon,lat,alt(%s, %s, %s)", lon, lat, alt)
        px, py = self.to_pixels.transform(lon, lat)
        px -= self.refproj[0]
        py -= self.refproj[1]
        pz = alt - self.refproj[2]
        x = self.meters2pixels(px) + self.refxyz[0]
        y = -(self.meters2pixels(py) + self.refxyz[1])
        z = self.meters2pixels(pz) + self.refxyz[2]
        logger.debug("result x,y,z(%s, %s, %s)", x, y, z)
        return x, y, z

    def getgeo(self, x: float, y: float, z: float) -> Tuple[float, float, float]:
        """
        Convert provided x,y,z to lon,lat,alt.

        :param x: x value
        :param y: y value
        :param z: z value
        :return: lat,lon,alt representation of provided values
        """
        logger.debug("input x,y(%s, %s)", x, y)
        x -= self.refxyz[0]
        y = -(y - self.refxyz[1])
        if z is None:
            z = self.refxyz[2]
        else:
            z -= self.refxyz[2]
        px = self.refproj[0] + self.pixels2meters(x)
        py = self.refproj[1] + self.pixels2meters(y)
        lon, lat = self.to_geo.transform(px, py)
        alt = self.refgeo[2] + self.pixels2meters(z)
        logger.debug("result lon,lat,alt(%s, %s, %s)", lon, lat, alt)
        return lat, lon, alt
