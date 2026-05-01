from backend.utils.simulator_utils import interpolate_along_line, cumulative_distances


def test_cumulative_and_interpolate():
    # simple two-point line: (lon,lat)
    coords = [(0.0, 0.0), (0.0, 0.009)]  # ~1km north
    cum = cumulative_distances(coords)
    assert len(cum) == 2
    total = cum[-1]
    assert total > 900 and total < 1100

    # halfway should be near the midpoint
    mid = interpolate_along_line(coords, total / 2)
    assert abs(mid[0] - 0.0) < 1e-6
    assert abs(mid[1] - 0.0045) < 0.001
