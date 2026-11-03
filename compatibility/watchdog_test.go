package main

import (
	"context"
	"errors"
	"os"
	"os/exec"
	"strings"
	"testing"
	"time"
)

type stalledCloser struct{}

func (stalledCloser) Close() error {
	select {}
}

func TestRuntimeWatchdog(t *testing.T) {
	for _, stage := range []string{"execution", "output cleanup"} {
		t.Run(stage, func(t *testing.T) {
			ctx, cancel := context.WithTimeout(t.Context(), 5*time.Second)
			defer cancel()
			cmd := exec.CommandContext(ctx, os.Args[0], "-test.run=^TestRuntimeWatchdogProcess$")
			cmd.Env = append(os.Environ(), "COMPAT_TEST_STALL="+stage)
			out, err := cmd.CombinedOutput()
			var exit *exec.ExitError
			if !errors.As(err, &exit) || exit.ExitCode() != 124 {
				t.Fatalf("expected watchdog exit 124, got %v: %s", err, out)
			}
			for _, want := range []string{"Compatibility runtime timed out", "during " + stage, "goroutine 1", "TestRuntimeWatchdogProcess"} {
				if !strings.Contains(string(out), want) {
					t.Errorf("diagnostics missing %q: %s", want, out)
				}
			}
		})
	}
}

func TestRuntimeWatchdogProcess(t *testing.T) {
	stage := os.Getenv("COMPAT_TEST_STALL")
	if stage == "" {
		return
	}
	w := newRuntimeWatchdog(50*time.Millisecond, os.Stderr, os.Exit)
	defer w.stop()
	w.setStage("execution")
	if stage == "output cleanup" {
		var err error
		closeResult(stalledCloser{}, &err, w, stage)
	}
	select {}
}
