package main

import (
	"fmt"
	"io"
	"runtime/pprof"
	"sync/atomic"
	"time"
)

type runtimeWatchdog struct {
	stage atomic.Value
	timer *time.Timer
}

// The watchdog also covers cleanup, which cannot always honor an execution context.
func newRuntimeWatchdog(timeout time.Duration, diagnostics io.Writer, exit func(int)) *runtimeWatchdog {
	w := &runtimeWatchdog{}
	w.setStage("initialization")
	w.timer = time.AfterFunc(timeout, func() {
		fmt.Fprintf(diagnostics, "Compatibility runtime timed out after %s during %s\n", timeout, w.stage.Load())
		_ = pprof.Lookup("goroutine").WriteTo(diagnostics, 2)
		exit(124)
	})
	return w
}

func (w *runtimeWatchdog) setStage(stage string) {
	w.stage.Store(stage)
}

func (w *runtimeWatchdog) stop() {
	w.timer.Stop()
}
