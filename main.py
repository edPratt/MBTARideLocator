# -*- coding: utf-8 -*-
"""

Given a latitude and a longitude coordinate, this module finds nearest and soonest
MBTA trips using the MBTA V3 API.

Example:
        $ python main.py
        Then enter the latitude as prompted (ex: 42.308308)
        Then enter the longitude as prompted (ex: 71.113116)
"""

import json
import requests
import datetime
from geopy.distance import geodesic
import sys

class NextRideLocator:
  """

  Note:
    ...

  Args:
      latitude (string): Number for the first coordinate
      longitude (string): Number for the first coordinate

  .. todo: Implement abstract class NextRideLocator that can be used by something like LeaveGreaterBoston
  .. todo: Finish documentation of class and methods
  .. todo: Clean up docstrings
  .. todo: Refactor so that return is always a dict of either successful data or relevant error(s)
  .. todo: Handle bad input

  """

  API_ROOT = 'https://api-v3.mbta.com'

  ALLOWED_DIRECTIONS = ['Outbound', 'Northbound', 'Southbound']

  def __init__(self, latitude, longitude):

    self.latitude = latitude
    self.longitude = longitude
    self.LOCATION = (latitude, longitude)

    self.stop_data = json.loads(requests.get(
      self.API_ROOT + '/stops?filter%5Blatitude%5D={0}&filter%5Blongitude%5D={1}&filter%5Bradius%5D=0.01'.format(
        *self.LOCATION)).text)

    if 'errors' in self.stop_data:
      sys.stderr.write('Errors in stop_data')
      sys.exit()

    self.nearest_stop = self.getNearestStop()

    if not self.nearest_stop:
      sys.stderr.write('Unable to get nearest_stop from given latitude/longitude')
      sys.exit()

    if self.nearest_stop and 'id' in self.nearest_stop:
      self.nearest_stop_id = self.nearest_stop['id']
    else:
      sys.stderr.write('Unable to get nearest_stop_id from nearest_stop')
      sys.exit()

    if self.nearest_stop:
      if 'name' in self.nearest_stop:
        self.nearest_stop_name = self.nearest_stop['name']


    if self.nearest_stop_id:
      self.predictions = self.getPredictionsForStopId(self.nearest_stop_id)
      if self.predictions:
        if 'data' in self.predictions:
          if not len(self.predictions['data']):
            sys.stderr.write('There are no Predictions for stop_id: {0}'.format(self.nearest_stop_id))
            sys.exit()

    self.allowed_trips = self.getAllowedTrips(self.predictions, NextRideLocator.ALLOWED_DIRECTIONS)

    self.soonest_leaving = self.getSoonestLeaving(self.allowed_trips)



  def getNearestStop(self):
    """
    Gets the nearest stop from the Class's stop_data and LOCATION

    :return: a dictionary containing the longitude, latitude, name, and id of the closest stop to LOCATION
    :rtype: dict

    .. todo:: Rewrite this function in a more efficient and reusable way
    .. todo:: Noticed sometimes there is a slightly closer stop on Google Maps: Investigate
    .. todo:: Check pagination to make sure not missing data
    .. todo:: Implement rate limit functionality
    .. todo:: Only return needed data
    """

    data = {}

    for item in self.stop_data['data']:
      try:
        distance_to_x = geodesic(self.LOCATION, (item['attributes']['latitude'], item['attributes']['longitude'])).miles
        parent_station = item['relationships']['parent_station']['data']
      except:
        sys.stderr.write('Unable to find distance and/or parent station.')


      if parent_station:
        id = parent_station['id']
      else:
        id = item['id']

      data[distance_to_x] = {
                              'latitude': item['attributes']['latitude'],
                              'longitude': item['attributes']['longitude'],
                              'name' : item['attributes']['name'],
                              'id': id
                            }

      closest_stop_to_x = data[min(data)]
      return closest_stop_to_x


  def getPredictionsForStopId(self, stop_id):
    """
    Gets the predictions filtered by stop_id

    :param stop_id: string
    :return: a list that should contain all of the predictions for the given stop_id
    :rtype: list or list of dict

    .. todo:: Make more abstract: Refactor to handle predictions and schedule
    """
    if stop_id:
      prediction_data = json.loads(requests.get(self.API_ROOT + '/predictions?filter%5Bstop%5D={0}'.format(
      stop_id)).text)
      return prediction_data


  def getAllowedTrips(self, trip_data, allowed_directions):
    """
    Gets the predictions that conform to the allowed_directions provided by NextRideLocator

    :param trip_data: dict
    :param allowed_directions: array
    :return: a list that should contain dictionaries of allowed trips
    :rtype: list

    .. todo:: Better exception handling
    .. todo:: Clarify return types (i.e :return: list of dict or json etc.)
    .. todo:: Make more abstract: refactor to handle schedule and prediction data
    """

    result = []

    for item in trip_data['data']:
      try:
        direction_index = item['attributes']['direction_id']
        route_id = item['relationships']['route']['data']['id']
      except:
        pass
      try:
        route_data = json.loads(requests.get(self.API_ROOT + '/routes/{0}'.format(
          route_id)).text)
        route_direction_list = route_data['data']['attributes']['direction_names']
        route_direction = route_direction_list[direction_index]
        if route_direction in allowed_directions:
          result.append(item)
      except:
        pass
    return result


  def getSoonestLeaving(self, trips):
    """
    Gets the soonest leaving trip from a list of trips

    :return: the soonest leaving trip
    :rtype: dict

    .. todo:: Store data on Class itself
    .. todo:: Verify :return: type
    .. todo:: Delays in incoming data on bigger stations (Back Bay), so need to check negative time deltas
    .. todo:: Only return needed data
    """

    if trips:
      info = {}
      for trip in trips:
        date = trip['attributes']['departure_time']
        info[date] = trip
      soonest_leaving = info[min(info)]

      return soonest_leaving


  def timeUntilArrival(self, trip, current_time):
    if trip:
      return self.formatDate(trip['attributes']['departure_time']) - current_time


  def tripId(self, trip):
    """

    :param trip: dict
    :param current_time: datetime
    :return: The trip id of a trip
    :rtype: string
    """
    if trip:
      if 'relationships' in trip:
        return trip['relationships']['trip']['data']['id']


  def formatDate(self, date_string):
    return datetime.datetime.strptime(date_string.split('-04:00')[0], "%Y-%m-%dT%H:%M:%S")


  def leaveNow(self):
    """
    Acts as entry point for the program. Calls all necessary functions to return the nearest and soonest trip info

    :return: Information about the nearest and soonest trip
    :rtype: dict

    .. :todo If there are no trips at the nearby stop, try to find trips at next nearby stops until one is found
    """

    if self.predictions:

      if self.allowed_trips:
        current_time = datetime.datetime.now()
        return {
          'trip_id': self.tripId(self.soonest_leaving),
          'time_until_arrival': str(self.timeUntilArrival(self.soonest_leaving, current_time))
        }
    return {'error': 'No available trips at this time'}


if __name__ == "__main__":

  try:
    latitude = float(input('Please input the latitude of your position (ex: 42.308216): '))
    longitude = float(input('Please input the latitude of your longitude (ex: -71.072487): '))
  except:
    sys.stderr.write('Invalid entry type')
    sys.exit()

  leave_location = NextRideLocator(latitude, longitude)
  result = leave_location.leaveNow()
  print(result)
