(function (global) {
  const SAMPLE_DATA = {
    routes: [
      {
        id: 'urn:ngsi-ld:GtfsRoute:route-1',
        routeShortName: '1',
        routeLongName: 'Praza de Pontevedra - Campus',
        routeColor: '0B74DE',
        routeTextColor: 'FFFFFF',
        path: [
          [-8.4047, 43.3704],
          [-8.4026, 43.3687],
          [-8.4010, 43.3668],
          [-8.3992, 43.3649],
        ],
        tripIds: ['urn:ngsi-ld:GtfsTrip:trip-1'],
        stopIds: ['urn:ngsi-ld:GtfsStop:stop-1', 'urn:ngsi-ld:GtfsStop:stop-2'],
      },
    ],
    stops: [
      {
        id: 'urn:ngsi-ld:GtfsStop:stop-1',
        stopName: 'Praza de Pontevedra',
        stopCode: '0101',
        location: [-8.4047, 43.3704],
      },
      {
        id: 'urn:ngsi-ld:GtfsStop:stop-2',
        stopName: 'Campus Sur',
        stopCode: '0214',
        location: [-8.3997, 43.3649],
      },
    ],
    vehicles: [
      {
        id: 'urn:ngsi-ld:VehicleState:bus-17',
        vehicleId: 'bus-17',
        tripId: 'urn:ngsi-ld:GtfsTrip:trip-1',
        currentStopId: 'urn:ngsi-ld:GtfsStop:stop-1',
        currentPosition: [-8.4029, 43.3680],
        delaySeconds: 45,
        occupancy: 62,
        speedKmh: 26,
        heading: 128,
        status: 'in_transit',
        nextStopName: 'Campus Sur',
        predictedArrivalTime: '2026-05-02T12:08:00Z',
      },
    ],
  };

  function cloneData(data) {
    return JSON.parse(JSON.stringify(data));
  }

  async function fetchJson(path) {
    const response = await fetch(path, {
      headers: {
        Accept: 'application/json',
      },
    });

    if (!response.ok) {
      throw new Error(`Request failed for ${path}: ${response.status}`);
    }

    return response.json();
  }

  async function loadMapData() {
    try {
      const [routesResponse, stopsResponse, vehiclesResponse] = await Promise.all([
        fetchJson('/api/routes'),
        fetchJson('/api/stops'),
        fetchJson('/api/vehicles/current'),
      ]);

      const data = {
        routes: Array.isArray(routesResponse.routes) ? routesResponse.routes : [],
        stops: Array.isArray(stopsResponse.stops) ? stopsResponse.stops : [],
        vehicles: Array.isArray(vehiclesResponse.vehicles) ? vehiclesResponse.vehicles : [],
      };

      if (!data.routes.length && !data.stops.length && !data.vehicles.length) {
        return cloneData(SAMPLE_DATA);
      }

      return data;
    } catch (error) {
      console.warn('Falling back to sample map data:', error);
      return cloneData(SAMPLE_DATA);
    }
  }

  global.MapApiClient = {
    loadMapData,
    sampleData: () => cloneData(SAMPLE_DATA),
  };
})(window);