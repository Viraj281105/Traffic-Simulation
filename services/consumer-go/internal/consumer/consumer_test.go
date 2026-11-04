package consumer

import (
	"context"
	"errors"
	"testing"
)

// fakeSource serves a fixed list of messages, then ErrEndOfStream (or failErr).
type fakeSource struct {
	msgs       []Message
	next       int
	committed  []int64
	failFetch  error
	failAt     int64 // commit fails for this offset when failCommit is set
	failCommit bool
}

func (f *fakeSource) Fetch(ctx context.Context) (Message, error) {
	if err := ctx.Err(); err != nil {
		return Message{}, err
	}
	if f.next >= len(f.msgs) {
		if f.failFetch != nil {
			return Message{}, f.failFetch
		}
		return Message{}, ErrEndOfStream
	}
	m := f.msgs[f.next]
	f.next++
	return m, nil
}

func (f *fakeSource) Commit(_ context.Context, m Message) error {
	if f.failCommit && m.Offset == f.failAt {
		return errors.New("commit refused")
	}
	f.committed = append(f.committed, m.Offset)
	return nil
}

func (f *fakeSource) Close() error { return nil }

func msg(offset int64, body string) Message {
	return Message{Key: []byte("k"), Value: []byte(body), Offset: offset}
}

func TestRunAggregatesPerLinkAndCommitsEveryMessage(t *testing.T) {
	src := &fakeSource{msgs: []Message{
		msg(0, `{"link_id":"L2","interval_start":"0","count":5,"seq":0}`),
		msg(1, `{"link_id":"L1","interval_start":"0","count":12,"seq":1}`),
		msg(2, `{"link_id":"L1","interval_start":"30","count":7,"seq":2}`),
	}}
	c := New(src)
	if err := c.Run(context.Background(), nil); err != nil {
		t.Fatalf("Run: %v", err)
	}
	s := c.Snapshot()
	if s.Processed != 3 || s.Invalid != 0 {
		t.Fatalf("processed=%d invalid=%d", s.Processed, s.Invalid)
	}
	if len(s.Links) != 2 || s.Links[0].LinkID != "L1" || s.Links[0].Vehicles != 19 || s.Links[0].Messages != 2 {
		t.Fatalf("links = %+v", s.Links)
	}
	if len(src.committed) != 3 {
		t.Fatalf("committed %v, want all 3", src.committed)
	}
}

func TestInvalidMessagesAreCountedReportedAndStillCommitted(t *testing.T) {
	src := &fakeSource{msgs: []Message{
		msg(0, `not json`),
		msg(1, `{"link_id":"","count":1}`),
		msg(2, `{"link_id":"L1","count":-3}`),
		msg(3, `{"link_id":"L1","count":4}`),
	}}
	c := New(src)
	var reported int
	if err := c.Run(context.Background(), func(Message, error) { reported++ }); err != nil {
		t.Fatalf("Run: %v", err)
	}
	s := c.Snapshot()
	if s.Processed != 1 || s.Invalid != 3 || reported != 3 {
		t.Fatalf("processed=%d invalid=%d reported=%d", s.Processed, s.Invalid, reported)
	}
	if len(src.committed) != 4 {
		t.Fatalf("poison messages must be committed too, got %v", src.committed)
	}
}

func TestCommitFailureStopsRunWithError(t *testing.T) {
	src := &fakeSource{
		msgs:       []Message{msg(0, `{"link_id":"L1","count":1}`), msg(1, `{"link_id":"L1","count":1}`)},
		failCommit: true,
		failAt:     1,
	}
	err := New(src).Run(context.Background(), nil)
	if err == nil {
		t.Fatal("expected a commit error")
	}
	if len(src.committed) != 1 {
		t.Fatalf("committed %v", src.committed)
	}
}

func TestFetchErrorIsReturned(t *testing.T) {
	src := &fakeSource{failFetch: errors.New("broker down")}
	if err := New(src).Run(context.Background(), nil); err == nil {
		t.Fatal("expected fetch error")
	}
}

func TestCancelledContextEndsRunCleanly(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	src := &fakeSource{msgs: []Message{msg(0, `{"link_id":"L1","count":1}`)}}
	c := New(src)
	if err := c.Run(ctx, nil); err != nil {
		t.Fatalf("Run after cancel: %v", err)
	}
	if c.Snapshot().Processed != 0 {
		t.Fatal("nothing should have been processed")
	}
}
