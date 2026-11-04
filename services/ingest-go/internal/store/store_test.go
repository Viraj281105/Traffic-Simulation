package store

import (
	"fmt"
	"math"
	"sync"
	"testing"
)

func TestAppendIdempotentAndValidated(t *testing.T) {
	s := New(4)
	e := &Event{RunID: "r1", Seq: 0, SimTime: 1, Metrics: map[string]float64{"speed": 10}}
	if got := s.Append(e); got != Accepted {
		t.Fatalf("first append = %v, want Accepted", got)
	}
	if got := s.Append(e); got != Duplicate {
		t.Fatalf("second append = %v, want Duplicate", got)
	}
	bad := []*Event{
		nil,
		{RunID: "", Seq: 0},
		{RunID: "r1", Seq: -1},
		{RunID: "r1", Seq: 1, SimTime: -0.5},
	}
	for i, b := range bad {
		if got := s.Append(b); got != Rejected {
			t.Errorf("bad[%d] = %v, want Rejected", i, got)
		}
	}
	if runs, events := s.Stats(); runs != 1 || events != 1 {
		t.Fatalf("stats = %d runs %d events, want 1 and 1", runs, events)
	}
}

func TestSummaryAggregates(t *testing.T) {
	s := New(2)
	s.Append(&Event{RunID: "r", Seq: 0, SimTime: 2, Metrics: map[string]float64{"v": 4}})
	s.Append(&Event{RunID: "r", Seq: 5, SimTime: 1, Metrics: map[string]float64{"v": 8, "q": 1}})
	got := s.Summary("r")
	if !got.Found || got.Events != 2 || got.LastSeq != 5 {
		t.Fatalf("summary = %+v", got)
	}
	if got.FirstSimTime != 1 || got.LastSimTime != 2 {
		t.Errorf("sim time range = %v..%v", got.FirstSimTime, got.LastSimTime)
	}
	if math.Abs(got.MetricMeans["v"]-6) > 1e-12 || got.MetricMeans["q"] != 1 {
		t.Errorf("means = %v", got.MetricMeans)
	}
	if s.Summary("nope").Found {
		t.Error("unknown run reported as found")
	}
}

func TestConcurrentAppendCountsExactly(t *testing.T) {
	s := New(8)
	const workers, per = 8, 500
	var wg sync.WaitGroup
	for w := 0; w < workers; w++ {
		wg.Add(1)
		go func(w int) {
			defer wg.Done()
			for i := 0; i < per; i++ {
				// Every worker writes the same 500 sequence numbers of a shared
				// run, so exactly `per` of the workers*per appends can win.
				s.Append(&Event{RunID: "shared", Seq: int64(i)})
				s.Append(&Event{RunID: fmt.Sprintf("own-%d", w), Seq: int64(i)})
			}
		}(w)
	}
	wg.Wait()
	if got := s.Summary("shared").Events; got != per {
		t.Fatalf("shared run has %d events, want %d", got, per)
	}
	if runs, events := s.Stats(); runs != workers+1 || events != uint64(per+workers*per) {
		t.Fatalf("stats = %d runs %d events", runs, events)
	}
}

func BenchmarkAppendParallel(b *testing.B) {
	s := New(16)
	var mu sync.Mutex
	next := int64(0)
	b.RunParallel(func(pb *testing.PB) {
		mu.Lock()
		id := next
		next++
		mu.Unlock()
		run := fmt.Sprintf("bench-%d", id)
		var seq int64
		m := map[string]float64{"speed": 12.5, "queue": 3}
		for pb.Next() {
			s.Append(&Event{RunID: run, Seq: seq, SimTime: float64(seq) * 0.1, Kind: "step", Metrics: m})
			seq++
		}
	})
}
