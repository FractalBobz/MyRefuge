from unidecode import unidecode

from django.contrib.gis.db import models as gis_models
from django.contrib.gis import geos, measure

from common.geo import (address_to_location, location_to_latlon, location_to_city,
                        location_to_country)


def normalize_name(name):
    """
    convert to ascii lower case no white space only
    """
    return unidecode(name).lower().replace(' ', '')


class CitizenSpaceManager(gis_models.GeoManager):

    # TODO(hoatle): improve this, speed it up
    # this could help: http://www.rkblog.rk.edu.pl/w/p/shops-near-you-geographic-features-geodjango/
    # sort by distance
    def search(self, address, date_range, guests, distance=20000, **kwargs):
        """Search spaces basing on the address, date_range, guests, etc
        :param address the raw address
        :date_range the sequence of 2 dates: start and end date
        :guests the number of guests that a space could accommodate
        :distance the meters from the raw address to look for, default: 20 km
        """
        start_date, end_date = date_range
        query = self.filter(guests__gte=guests)

        if start_date:
            query = query.filter(daterange__start_date__lte=start_date)

        if end_date:
            query = query.filter(daterange__end_date__gte=end_date)

        # TODO(hoatle): this takes lot of time, need to improve this
        if address.raw:
            location = address_to_location(address.raw)
        else:
            location = address_to_location(address)

        address_lat, address_lon = location_to_latlon(location)
        city = location_to_city(location)
        if city is not None:
            city = normalize_name(city)
            query = query.filter(city=city)
        else:
            country = location_to_country(location)
            if country is not None:
                country = normalize_name(country)
                query = query.filter(country=country)
        current_point = geos.fromstr('POINT(%s %s)' % (address_lon, address_lat))
        distance_from_point = {'m': distance}
        query = query.filter(location__distance_lte=(current_point,
                                                     measure.D(**distance_from_point)))
        return query.distance(current_point).order_by('distance')