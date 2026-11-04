// Package kafkasource adapts a segmentio/kafka-go consumer-group reader to consumer.Source.
// It talks to Redpanda through the Kafka API. WRITTEN, not run against a broker in the dev
// environment.
package kafkasource

import (
	"context"

	"github.com/segmentio/kafka-go"

	"urbanflow/consumer/internal/consumer"
)

// Source is a consumer-group reader. Offsets are committed explicitly via Commit.
type Source struct {
	reader *kafka.Reader
	raw    map[int64]kafka.Message
}

// New joins group on topic. With no committed offset the group starts at the beginning, so a
// replay is read in full.
func New(brokers []string, topic, group string) *Source {
	return &Source{
		reader: kafka.NewReader(kafka.ReaderConfig{
			Brokers:     brokers,
			Topic:       topic,
			GroupID:     group,
			MinBytes:    1,
			MaxBytes:    10 << 20,
			StartOffset: kafka.FirstOffset,
		}),
		raw: map[int64]kafka.Message{},
	}
}

// Fetch implements consumer.Source. Offsets are only unique per partition, so the key used
// for the pending-commit map combines partition and offset.
func (s *Source) Fetch(ctx context.Context) (consumer.Message, error) {
	m, err := s.reader.FetchMessage(ctx)
	if err != nil {
		return consumer.Message{}, err
	}
	s.raw[pendingKey(m.Partition, m.Offset)] = m
	return consumer.Message{Key: m.Key, Value: m.Value, Partition: m.Partition, Offset: m.Offset}, nil
}

// Commit implements consumer.Source.
func (s *Source) Commit(ctx context.Context, m consumer.Message) error {
	k := pendingKey(m.Partition, m.Offset)
	raw, ok := s.raw[k]
	if !ok {
		return nil
	}
	if err := s.reader.CommitMessages(ctx, raw); err != nil {
		return err
	}
	delete(s.raw, k)
	return nil
}

// Close implements consumer.Source.
func (s *Source) Close() error { return s.reader.Close() }

func pendingKey(partition int, offset int64) int64 {
	return int64(partition)<<48 | offset
}
