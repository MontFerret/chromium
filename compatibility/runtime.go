package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"strings"

	"github.com/MontFerret/contrib/modules/web/html"
	"github.com/MontFerret/contrib/modules/web/html/drivers/cdp"
	"github.com/MontFerret/ferret/v2"
)

func main() {
	if err := run(); err != nil {
		fmt.Fprintln(os.Stderr, ferret.FormatError(err))
		os.Exit(1)
	}
}

// Lab sends the FQL on stdin and fixture URLs via repeated --param=name:json flags.
func run() (err error) {
	params := make(map[string]any)
	flag.Func("param", "query parameter", func(arg string) error {
		key, raw, ok := strings.Cut(arg, ":")
		if !ok {
			return fmt.Errorf("invalid Lab parameter %q", key)
		}

		var value any
		if err := json.Unmarshal([]byte(raw), &value); err != nil {
			return err
		}
		params[key] = value
		return nil
	})
	flag.Parse()

	query, err := io.ReadAll(os.Stdin)
	if err != nil {
		return err
	}

	engine, err := ferret.New(ferret.WithModules(html.New(
		html.WithDefaultDriver(cdp.New(cdp.WithAddress(os.Getenv("COMPAT_CDP_URL")))),
	)))
	if err != nil {
		return err
	}
	defer closeResult(engine, &err)

	ctx := context.Background()
	out, err := engine.Run(ctx, ferret.NewSource("compat.fql", string(query)), ferret.WithSessionParams(params))
	if err != nil {
		return err
	}
	defer closeResult(out, &err)

	content, err := out.Collect(ctx)
	if err != nil {
		return err
	}
	if content != nil {
		_, err = os.Stdout.Write(content.Data)
	}
	return err
}

// Keep Ferret's formatted source diagnostics when cleanup succeeds.
func closeResult(closer io.Closer, result *error) {
	if err := closer.Close(); err != nil {
		*result = errors.Join(*result, err)
	}
}
