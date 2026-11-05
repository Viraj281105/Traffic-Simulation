// Package consumer reads replayed observation messages from a Source, aggregates them per
// link, and commits each message after it has been processed. The Source is an interface so
// the logic is tested without a broker (see consumer_test.go); the Kafka/Redpanda
// implementation lives in internal/kafkasource.
//
// Message shape (written by scripts/replay_to_redpanda.py):
//
//	{"link_id":"L1","interval_start":"0","count":12,"sensor_id":"s1","seq":0}
package consumer

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"sync"
)

// ErrEndOfStream is returned by a Source that has no more messages (used by tests and
// finite replays); Run then returns nil.
var ErrEndOfStream = errors.New("end of stream")

// Message is one record from the stream.
type Message struct {
	Key       []byte
	Value     []byte
	Partition int
	Offset    int64
}

// Source is where messages come from.
type Source interface {
	// Fetch blocks for the next message. It returns ctx.Err() when ctx is cancelled and
	// ErrEndOfStream when a finite source is exhausted.
	Fetch(ctx context.Context) (Message, error)
	// Commit marks m as processed.
	Commit(ctx context.Context, m Message) error
	Close() error
}

// Observation is the decoded message body.
type Observation struct {
	LinkID        string  `json:"link_id"`
	IntervalStart string  `json:"interval_start"`
	Count         float64 `json:"count"`
	SensorID      string  `json:"sensor_id,omitempty"`
	Seq           int64   `json:"seq"`
}

// Validate reports why an observation is unusable, or nil.
func (o Observation) Validate() error {
	if o.LinkID == "" {
		return errors.New("empty link_id")
	}
	if o.Count < 0 {
		return fmt.Errorf("negative count %v", o.Count)
	}
	return nil
}

// LinkStat is the running total for one link.
type LinkStat struct {
	LinkID   string  `json:"link_id"`
	Messages int64   `json:"messages"`
	Vehicles float64 `json:"vehicles"`
}

// Stats is a point-in-time copy of the consumer's counters.
type Stats struct {
	Processed int64      `json:"processed"`
	Invalid   int64      `json:"invalid"`
	Links     []LinkStat `json:"links"`
}

// Consumer aggregates observations. Safe for concurrent Snapshot calls while Run executes.
type Consumer struct {
	src Source

	mu        sync.Mutex
	processed int64
	invalid   int64
	links     map[string]*LinkStat
}

// New returns a Consumer reading from src.
func New(src Source) *Consumer {
	return &Consumer{src: src, links: map[string]*LinkStat{}}
}

// Handle processes one message body. Invalid messages are counted and skipped (they are still
// committed by Run, so one poison message cannot stall the partition).
func (c *Consumer) Handle(m Message) error {
	var obs Observation
	if err := json.Unmarshal(m.Value, &obs); err != nil {
		c.countInvalid()
		return fmt.Errorf("decode: %w", err)
	}
	if err := obs.Validate(); err != nil {
		c.countInvalid()
		return err
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	st := c.links[obs.LinkID]
	if st == nil {
		st = &LinkStat{LinkID: obs.LinkID}
		c.links[obs.LinkID] = st
	}
	st.Messages++
	st.Vehicles += obs.Count
	c.processed++
	return nil
}

func (c *Consumer) countInvalid() {
	c.mu.Lock()
	c.invalid++
	c.mu.Unlock()
}

// Run consumes until ctx is cancelled or the source ends. A message is committed only after
// Handle returned (success or a counted rejection); a Fetch or Commit failure ends Run with
// an error. onInvalid, if non-nil, is told about each rejected message.
func (c *Consumer) Run(ctx context.Context, onInvalid func(Message, error)) error {
	for {
		msg, err := c.src.Fetch(ctx)
		if err != nil {
			if errors.Is(err, ErrEndOfStream) || ctx.Err() != nil {
				return nil
			}
			return fmt.Errorf("fetch: %w", err)
		}
		if herr := c.Handle(msg); herr != nil && onInvalid != nil {
			onInvalid(msg, herr)
		}
		if err := c.src.Commit(ctx, msg); err != nil {
			if ctx.Err() != nil {
				return nil
			}
			return fmt.Errorf("commit offset %d: %w", msg.Offset, err)
		}
	}
}

// Snapshot returns a copy of the counters, links sorted by id.
func (c *Consumer) Snapshot() Stats {
	c.mu.Lock()
	defer c.mu.Unlock()
	out := Stats{Processed: c.processed, Invalid: c.invalid, Links: make([]LinkStat, 0, len(c.links))}
	for _, st := range c.links {
		out.Links = append(out.Links, *st)
	}
	sort.Slice(out.Links, func(i, j int) bool { return out.Links[i].LinkID < out.Links[j].LinkID })
	return out
}
