// pbs-job runs proxmox-backup-client for the pbs-backup and pbs-restore Jobs. The image is
// distroless (no shell), so the optional flags the Jobs used to add in a `/bin/sh -c` wrapper are
// added here instead:
//
//	pbs-job <backup|restore> [args...]
//
// runs
//
//	proxmox-backup-client <backup|restore> [--ns $PBS_NAMESPACE] [--keyfile <file>] [args...]
//
// --ns is added when PBS_NAMESPACE is non-empty, --keyfile when the key file exists
// ($PBS_KEYFILE, default /etc/pbs/keyfile). Job args use Kubernetes $(VAR) expansion, which leaves
// $(VAR) as literal text when VAR is not set; such an argument stops the run, as `${VAR:?}` did.
package main

import (
	"fmt"
	"os"
	"regexp"
	"syscall"
)

const client = "/usr/bin/proxmox-backup-client"

var unexpanded = regexp.MustCompile(`\$\([A-Za-z_][A-Za-z0-9_]*\)`)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: pbs-job <backup|restore> [args...]")
		os.Exit(2)
	}
	for _, arg := range os.Args[1:] {
		if v := unexpanded.FindString(arg); v != "" {
			fmt.Fprintf(os.Stderr, "pbs-job: %s is not set (add it to the Job's Secret)\n", v)
			os.Exit(2)
		}
	}

	argv := []string{client, os.Args[1]}
	if ns := os.Getenv("PBS_NAMESPACE"); ns != "" {
		argv = append(argv, "--ns", ns)
	}
	keyfile := os.Getenv("PBS_KEYFILE")
	if keyfile == "" {
		keyfile = "/etc/pbs/keyfile"
	}
	if _, err := os.Stat(keyfile); err == nil {
		argv = append(argv, "--keyfile", keyfile)
	}
	argv = append(argv, os.Args[2:]...)

	err := syscall.Exec(client, argv, os.Environ())
	fmt.Fprintf(os.Stderr, "pbs-job: exec %s: %v\n", client, err)
	os.Exit(1)
}
