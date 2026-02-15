package cmd

import (
	"fmt"
	"os"
	"strings"

	"github.com/maple-robotics/maple/storage"
	"github.com/spf13/cobra"
)

var showCmd = &cobra.Command{
	Use:   "show MODEL",
	Short: "Show model information",
	Args:  cobra.ExactArgs(1),
	Run: func(cmd *cobra.Command, args []string) {
		ref := args[0]
		name, tag := storage.ParseModelRef(ref)

		// Load manifest
		m, err := storage.LoadManifest(name, tag)
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error: model %s not found\n", ref)
			os.Exit(1)
		}

		// Calculate total size
		var totalSize int64
		for _, l := range m.Layers {
			totalSize += l.Size
		}

		fmt.Printf("  Model:    %s:%s\n", name, tag)
		fmt.Printf("  Size:     %s\n", formatSize(totalSize))
		fmt.Printf("  Layers:   %d\n", len(m.Layers))

		// Load and display config
		cfg, err := storage.LoadConfig(name, tag)
		if err == nil {
			fmt.Println()
			fmt.Printf("  Architecture:    %s\n", cfg.Architecture)
			fmt.Printf("  Family:          %s\n", cfg.Family)
			fmt.Printf("  Parameters:      %s\n", cfg.ParameterSize)
			fmt.Printf("  Action Dim:      %d\n", cfg.ActionDim)
			fmt.Printf("  Image Size:      %d\n", cfg.ImageSize)
			fmt.Printf("  Environments:    %s\n", strings.Join(cfg.Environments, ", "))
			if cfg.HFRepo != "" {
				fmt.Printf("  HuggingFace:     %s\n", cfg.HFRepo)
			}
		}

		// Show layers
		fmt.Println()
		fmt.Println("  Layers:")
		for _, l := range m.Layers {
			fmt.Printf("    %s  %s  %s\n", l.Digest[:19], formatSize(l.Size), l.MediaType)
		}
	},
}

func init() {
	rootCmd.AddCommand(showCmd)
}
