// Package store holds the ingest service's in-memory state. It has no
// dependency on the generated protobuf code so it builds and tests with the
// standard library alone.
package store

import (
	"errors"
	"hash/fnv"
	"sync"
)

// Event mirrors urbanflow.ingest.v1.Event.
type Event struct {
	RunID   string
	Seq     int64
	SimTime float64
	Kind    string
	Metrics map[string]float64
}

// Result of appending one event.
type Result int

const (
	Accepted Result = iota
	Duplicate
	Rejected
)

// ErrInvalid is returned by Validate for malformed events.
var ErrInvalid = errors.New("invalid event")

// Validate applies the contract rules from proto/ingest.proto.
func Validate(e *Event) error {
	if e == nil || e.RunID == "" || e.Seq < 0 || e.SimTime < 0 {
		return ErrInvalid
	}
	return nil
}

// Summary is the aggregate view of one run.
type Summary struct {
	RunID        string
	Found        bool
	Events       uint64
	LastSeq      int64
	FirstSimTime float64
	LastSimTime  float64
	MetricMeans  map[string]float64
}

type metricAcc struct {
	sum float64
	n   uint64
}

type run struct {
	seen         map[int64]struct{}
	events       uint64
	lastSeq      int64
	firstSimTime float64
	lastSimTime  float64
	metrics      map[string]*metricAcc
}

type shard struct {
	mu   sync.Mutex
	runs map[string]*run
}

// Store is safe for concurrent use. Runs are spread over shards by run id so
// producers for different runs do not contend on one lock. Only aggregates
// and the set of seen sequence numbers are kept, not the events themselves.
type Store struct {
	shards []shard
}

// New returns a Store with the given number of shards (minimum 1).
func New(shards int) *Store {
	if shards < 1 {
		shards = 1
	}
	s := &Store{shards: make([]shard, shards)}
	for i := range s.shards {
		s.shards[i].runs = make(map[string]*run)
	}
	return s
}

func (s *Store) shardFor(runID string) *shard {
	h := fnv.New32a()
	_, _ = h.Write([]byte(runID))
	return &s.shards[int(h.Sum32()%uint32(len(s.shards)))]
}

// Append stores e. It is idempotent per (RunID, Seq).
func (s *Store) Append(e *Event) Result {
	if Validate(e) != nil {
		return Rejected
	}
	sh := s.shardFor(e.RunID)
	sh.mu.Lock()
	defer sh.mu.Unlock()
	r, ok := sh.runs[e.RunID]
	if !ok {
		r = &run{
			seen:         make(map[int64]struct{}),
			lastSeq:      -1,
			firstSimTime: e.SimTime,
			lastSimTime:  e.SimTime,
			metrics:      make(map[string]*metricAcc),
		}
		sh.runs[e.RunID] = r
	}
	if _, dup := r.seen[e.Seq]; dup {
		return Duplicate
	}
	r.seen[e.Seq] = struct{}{}
	r.events++
	if e.Seq > r.lastSeq {
		r.lastSeq = e.Seq
	}
	if e.SimTime < r.firstSimTime {
		r.firstSimTime = e.SimTime
	}
	if e.SimTime > r.lastSimTime {
		r.lastSimTime = e.SimTime
	}
	for k, v := range e.Metrics {
		a := r.metrics[k]
		if a == nil {
			a = &metricAcc{}
			r.metrics[k] = a
		}
		a.sum += v
		a.n++
	}
	return Accepted
}

// Summary returns the aggregate for runID; Found is false if unknown.
func (s *Store) Summary(runID string) Summary {
	sh := s.shardFor(runID)
	sh.mu.Lock()
	defer sh.mu.Unlock()
	r, ok := sh.runs[runID]
	if !ok {
		return Summary{RunID: runID}
	}
	means := make(map[string]float64, len(r.metrics))
	for k, a := range r.metrics {
		means[k] = a.sum / float64(a.n)
	}
	return Summary{
		RunID: runID, Found: true, Events: r.events, LastSeq: r.lastSeq,
		FirstSimTime: r.firstSimTime, LastSimTime: r.lastSimTime, MetricMeans: means,
	}
}

// Stats returns the number of runs and stored events.
func (s *Store) Stats() (runs, events uint64) {
	for i := range s.shards {
		sh := &s.shards[i]
		sh.mu.Lock()
		runs += uint64(len(sh.runs))
		for _, r := range sh.runs {
			events += r.events
		}
		sh.mu.Unlock()
	}
	return runs, events
}
