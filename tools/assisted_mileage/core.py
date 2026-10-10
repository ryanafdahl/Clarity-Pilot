"""Conservative distance integration, independent of openpilot or device access."""
import math

METERS_PER_MILE = 1609.344
MAX_SAMPLE_GAP = 0.25
CONTROL_FRESHNESS = 0.25
METHOD_VERSION = 1


class DistanceCounter:
  """Integrate valid speeds; split intervals at control changes and expiry.

  Input events must be in monotonic order. No interval spans a segment boundary.
  Control state is piecewise constant; speed is linear between carState samples.
  """

  def __init__(self):
    self.previous_speed = None
    self.controls = []
    self.last_control = None
    self.total_meters = 0.0
    self.assisted_meters = 0.0
    self.observed_seconds = 0.0
    self.assisted_seconds = 0.0
    self.skipped_intervals = 0
    self.speed_samples = 0
    self.control_samples = 0

  def control(self, timestamp, lateral, longitudinal, valid=True):
    self.control_samples += 1
    state = (timestamp, bool(valid and (lateral or longitudinal)))
    self.controls.append(state)
    self.last_control = state

  def speed(self, timestamp, speed, valid=True, standstill=False):
    self.speed_samples += 1
    speed = 0.0 if standstill else speed
    good = valid and math.isfinite(speed) and 0 <= speed <= 80
    previous = self.previous_speed
    if previous and good and previous[2]:
      start, v0, _ = previous
      dt = timestamp - start
      if 0 < dt <= MAX_SAMPLE_GAP:
        self.total_meters += (v0 + speed) * 0.5 * dt
        self.observed_seconds += dt
        # Include the control state at interval start and every transition after it.
        controls = self.controls
        before = [c for c in controls if c[0] <= start]
        state = before[-1] if before else None
        changes = [c for c in controls if start < c[0] < timestamp]
        cursor = start
        for next_time, next_active in changes + [(timestamp, False)]:
          if state and state[1]:
            end = min(next_time, state[0] + CONTROL_FRESHNESS)
            if end > cursor:
              left = v0 + (speed - v0) * (cursor - start) / dt
              right = v0 + (speed - v0) * (end - start) / dt
              self.assisted_meters += (left + right) * 0.5 * (end - cursor)
              self.assisted_seconds += end - cursor
          cursor = next_time
          state = (next_time, next_active)
      else:
        self.skipped_intervals += 1
    elif previous:
      self.skipped_intervals += 1
    self.previous_speed = (timestamp, speed, good)
    # Retain only the state needed for the next interval, including an event at its boundary.
    self.controls = [self.last_control] if self.last_control else []

  def result(self):
    return {name: getattr(self, name) for name in (
      'total_meters', 'assisted_meters', 'observed_seconds', 'assisted_seconds',
      'skipped_intervals', 'speed_samples', 'control_samples')}
