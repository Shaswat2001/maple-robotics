package cmd

import (
	"fmt"
	"os"
	"text/tabwriter"

	"github.com/maple-robotics/maple/storage"
	"github.com/spf13/cobra"
)

var listCmd = &cobra.Command{
	Use:     "list",
	Aliases: []string{"ls"},
	Short:   "List downloaded models and environments",
	Run: func(cmd *cobra.Command, args []string) {
		listPolicies()
	},
}

var listPolicyCmd = &cobra.Command{
	Use:   "policy",
	Short: "List downloaded policies",
	Run: func(cmd *cobra.Command, args []string) {
		listPolicies()
	},
}

var listEnvCmd = &cobra.Command{
	Use:   "env",
	Short: "List downloaded environments",
	Run: func(cmd *cobra.Command, args []string) {
		fmt.Println("NAME\t\t\tSIZE\t\tMODIFIED")
	},
}

func listPolicies() {
	refs, err := storage.ListManifests()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error: %v\n", err)
		return
	}

	if len(refs) == 0 {
		fmt.Println("No models downloaded")
		fmt.Println("Run: maple pull policy <model>")
		return
	}

	w := tabwriter.NewWriter(os.Stdout, 0, 0, 3, ' ', 0)
	fmt.Fprintln(w, "NAME\tSIZE\tARCHITECTURE")

	for _, ref := range refs {
		name, tag := storage.ParseModelRef(ref)

		// Try to get the size of manifest
		size := "-"
		arch := "-"

		if m, err := storage.LoadManifest(name, tag); err == nil {
			var total int64
			for _, l := range m.Layers {
				total += l.Size
			}
			size = formatSize(total)

			// Try to load config for architecture
			if cfg, err := storage.LoadConfig(name, tag); err == nil {
				arch = cfg.Architecture
			}

		}

		fmt.Fprintf(w, "%s\t%s\t%s\n", ref, size, arch)
	}
	w.Flush()
}

func formatSize(bytes int64) string {
	const (
		KB = 1024
		MB = KB * 1024
		GB = MB * 1024
	)
	switch {
	case bytes >= GB:
		return fmt.Sprintf("%.1f GB", float64(bytes)/GB)
	case bytes >= MB:
		return fmt.Sprintf("%.1f MB", float64(bytes)/MB)
	case bytes >= KB:
		return fmt.Sprintf("%.1f KB", float64(bytes)/KB)
	default:
		return fmt.Sprintf("%d B", bytes)
	}
}

func init() {
	listCmd.AddCommand(listPolicyCmd)
	listCmd.AddCommand(listEnvCmd)
	rootCmd.AddCommand(listCmd)
}
