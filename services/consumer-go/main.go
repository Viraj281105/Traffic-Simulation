// Command consumer reads replayed observations from Redpanda/Kafka and logs per-link totals.
//
// Environment:
//
//	KAFKA_BROKERS   comma-separated brokers   (default localhost:19092)
//	KAFKA_TOPIC     topic                      (default urbanflow.observations)
//	KAFKA_GROUP     consumer group             (default urbanflow-consumer)
//	STATS_INTERVAL  how often to log totals    (default 10s)
package main

import (
	"context"
	"encoding/json"
	"log"
	"os"
	"os/signal"
	"strings"
	"syscall"
	"time"

	"urbanflow/consumer/internal/consumer"
	"urbanflow/consumer/internal/kafkasource"
)

func env(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func main() {
	brokers := strings.Split(env("KAFKA_BROKERS", "localhost:19092"), ",")
	topic := env("KAFKA_TOPIC", "urbanflow.observations")
	group := env("KAFKA_GROUP", "urbanflow-consumer")
	interval, err := time.ParseDuration(env("STATS_INTERVAL", "10s"))
	if err != nil || interval <= 0 {
		log.Fatalf("bad STATS_INTERVAL: %v", err)
	}

	src := kafkasource.New(brokers, topic, group)
	defer src.Close()
	c := consumer.New(src)

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()

	go func() {
		t := time.NewTicker(interval)
		defer t.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-t.C:
				logStats(c.Snapshot())
			}
		}
	}()

	log.Printf("consuming %s from %v as group %s", topic, brokers, group)
	err = c.Run(ctx, func(m consumer.Message, err error) {
		log.Printf("rejected partition=%d offset=%d: %v", m.Partition, m.Offset, err)
	})
	logStats(c.Snapshot())
	if err != nil {
		log.Fatalf("consumer stopped: %v", err)
	}
}

func logStats(s consumer.Stats) {
	b, _ := json.Marshal(s)
	log.Printf("stats %s", b)
}
