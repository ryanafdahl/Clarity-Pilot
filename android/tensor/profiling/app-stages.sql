-- Run locally: trace_processor query -f app-stages.sql recording.pftrace
-- All durations are wall time. CPU running and runnable waits are derived from
-- scheduler events, not inferred from low thread CPU time or TPU invocation.
-- Each stage's coverage must match its wall duration before interpreting it.
WITH stages AS (
  SELECT s.id, s.name, s.ts, s.dur, tt.utid, t.tid, t.upid
  FROM slice s JOIN thread_track tt ON s.track_id=tt.id
  JOIN thread t USING(utid) JOIN process p USING(upid)
  WHERE s.name GLOB 'jl.*' AND s.dur > 0
    AND p.name = 'io.zoompilot.jetlink.android'
), requests AS (
  SELECT * FROM stages WHERE name='jl.request'
), overlap AS (
  SELECT s.id, st.state,
    MAX(0, MIN(s.ts+s.dur, st.ts+st.dur)-MAX(s.ts, st.ts)) AS ns
  FROM stages s JOIN thread_state st ON s.utid=st.utid
    AND st.ts < s.ts+s.dur AND st.ts+st.dur > s.ts AND st.dur > 0
), frame_ids AS (
  SELECT c.ts, c.value, pct.upid
  FROM counter c JOIN process_counter_track pct ON c.track_id=pct.id
  WHERE pct.name='jl.frame_id'
)
SELECT s.id, s.tid, s.name, s.ts, s.dur/1e6 AS wall_ms,
  (SELECT CAST(f.value AS INT) FROM frame_ids f JOIN requests r ON f.upid=r.upid
    AND f.ts>=r.ts AND f.ts<r.ts+r.dur
    WHERE s.utid=r.utid AND s.ts>=r.ts AND s.ts+s.dur<=r.ts+r.dur
    ORDER BY f.ts LIMIT 1) AS frame_id,
  SUM(o.ns)/1e6 AS covered_ms,
  SUM(CASE WHEN o.state='Running' THEN o.ns ELSE 0 END)/1e6 AS running_ms,
  SUM(CASE WHEN o.state IN ('R','R+') THEN o.ns ELSE 0 END)/1e6 AS runnable_ms,
  SUM(CASE WHEN o.state NOT IN ('Running','R','R+') THEN o.ns ELSE 0 END)/1e6 AS blocked_ms
FROM stages s LEFT JOIN overlap o USING(id)
GROUP BY s.id ORDER BY s.ts, s.id;
